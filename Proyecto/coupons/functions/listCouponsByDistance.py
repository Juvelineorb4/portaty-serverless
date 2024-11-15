import boto3
import json
import os
import requests
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()
host = os.environ.get("OPENSE_HOST")
index = os.environ.get("OPENSE_BUSINESS_INDEX")

awsauth = AWSV4SignerAuth(credentials, region, service)

opense = OpenSearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20
)

query_list_coupon_campaigns = """
    query ListCouponCampaigns(
    $filter: ModelCouponCampaignFilterInput
    $limit: Int
    $nextToken: String
  ) {
    listCouponCampaigns(filter: $filter, limit: $limit, nextToken: $nextToken) {
      items {
        id
        businessID
        type
        discountValue
        description
        startDate
        endDate
        image 
        terms
      }
      nextToken
    }
  }
"""

    
def list_business_by_distance(fromTo, limit, location, user_id):
    lat = location["lat"]
    lon = location["lon"]
    query = {
  "from": fromTo, 
  "size": limit, 
  "_source": ["id", "thumbnail", "name", "images", "coordinates", "activity"],
  "query": {
    "bool": {
      "must": [
        {
          "match_all": {}
        }
      ],
      "filter": [
        {
          "bool": {
            "should": [
              {
                "geo_distance": {
                  "distance": "100km",
                  "coordinates": {
                    "lat": f"{lat}",
                    "lon": f"{lon}"
                  }
                }
              },
              {
                "match": {
                  "userID": f"{user_id}"
                }
              }
            ],
            "minimum_should_match": 1
          }
        }
      ]
    }
  }
}
    
    
    print("QUERY list_business_by_distance", query)

    # Ejecutar consulta paginada en OpenSearch
    r = opense.search(
            body=query,
            index=index
        )
    print("Respuesta Opense: ", r)
    total = r["hits"]["total"]["value"]
    # Extraer los IDs y detalles de los negocios
    hits = r.get('hits', {}).get('hits', [])
    businesses = [
        {   
            'id': hit['_source']['id'], 
            'thumbnail': hit['_source'].get('thumbnail'), 
            'name': hit['_source'].get('name'),
            'activity': hit['_source'].get('activity'),
            'images':hit['_source'].get('images'),
            'coordinates': hit['_source'].get('coordinates')
        } for hit in hits]
    
    return businesses, total


def get_all_coupon_campaigns(business_ids):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }
    all_campaigns = []
    next_token = None
    
    # Construir el filtro de consulta para AppSync
    business_id_filters = [{"businessID": {"eq": id}} for id in business_ids]
    variables = {
        "filter": {
            "and": [
                {"status": {"eq": "ACTIVE"}},
                {"or": business_id_filters}
            ]
        },
        "limit": 100,
        "nextToken": next_token
    }
    print("VARIABLES: ", variables)
    try:
        while True:
            response = requests.post(
                appsync_api_url,
                json={"query": query_list_coupon_campaigns, "variables": variables},
                headers=headers
            )
            response_data = response.json()
            if "errors" in response_data:
                print(f"Error en la consulta de GraphQL: {response_data['errors']}")
                return None

            # Obtener items y nextToken de la respuesta
            data = response_data.get("data", {}).get("listCouponCampaigns", {})
            items = data.get("items", [])
            next_token = data.get("nextToken", None)

            # Acumular los items obtenidos
            all_campaigns.extend(items)

            # Actualizar el nextToken para la siguiente iteración
            variables["nextToken"] = next_token

            # Salir del bucle si no hay más `nextToken`
            if not next_token:
                break

        return all_campaigns
    
    except Exception as e:
        print(f"Error al consultar AppSync: {e}")
        return None


def handler(event, context):
    print("EVENTO: ", event)
    params = event.get("queryStringParameters", {})
    print("PARAMS:", params)

    # Validación de parámetros de entrada
    locationString = params.get("location")
    if not locationString:
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "El parámetro 'location' es requerido."
            })
        }

    try:
        location = json.loads(locationString)
        if "lat" not in location or "lon" not in location:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "La 'location' debe contener 'lat' y 'lon'."
                })
            }
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "Formato JSON inválido en el parámetro 'location'."
            })
        }

    user_id = params.get("userID")
    if not user_id:
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "El parámetro 'userID' es requerido."
            })
        }

    # Validación de paginación y límite
    fromTo = int(params.get("from", 0))
    limit = int(params.get("limit", 100))
    if limit <= 0:
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "El parámetro 'limit' debe ser mayor a 0."
            })
        }

    try:
        # Realizar búsqueda de negocios por distancia 
        businesses, total = list_business_by_distance(fromTo, limit, location, user_id)
        print("Negocios: ", businesses)
        business_ids_distance = [business['id'] for business in businesses if 'id' in business]
        print("Id de negocio", business_ids_distance)
        
        if not business_ids_distance:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    "success": True,
                    "data": [],
                    "message": "No hay negocios cercanos a 100km."
                })
            }
        
        # Obtener campañas activas para los negocios filtrados por distancia
        campaigns = get_all_coupon_campaigns(business_ids_distance)
        if campaigns is None:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al obtener campañas activas."
                })
            }
        
        print("CAMPAÑAS FILTRADAS POR NEGOCIO", campaigns)
        
        # Filtrar negocios con al menos una campaña activa y emparejarlos
        business_with_campaigns = []
        for business in businesses:
            for campaign in campaigns:
                if campaign.get('businessID') == business.get('id'):
                    business_with_campaigns.append({
                        "coupon": {
                            "id": campaign.get("id"),
                            "type": campaign.get("type"),
                            "discountValue": campaign.get("discountValue"),
                            "description": campaign.get("description"),
                            "startDate": campaign.get("startDate"),
                            "endDate": campaign.get("endDate"),
                            "image": campaign.get("image", None),
                            "terms": campaign.get("terms")
                        },
                        "data": {
                            "id": business.get("id"),
                            "thumbnail": business.get("thumbnail"),
                            "name": business.get("name"),
                            "activity": business.get("activity"),
                            "images": business.get("images"),
                            "coordinates": business.get("coordinates")
                        }
                    })
        
        print("business_with_campaigns", business_with_campaigns)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Cupones obtenidos con éxito.",
                "items": business_with_campaigns,
                "limit": limit,
                "from": fromTo,
                "total": total  # número total de negocios con campañas activas
            })
        }
    
    except Exception as e:
        error_message = str(e)
        print("ERROR DE PROMOCIONES: ", error_message)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al consultar promociones.",
                "error": error_message
            })
        }

