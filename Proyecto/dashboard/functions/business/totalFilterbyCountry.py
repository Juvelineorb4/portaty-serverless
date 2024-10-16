import boto3
import json
import requests
from requests_aws4auth import AWS4Auth
import os

# Configuración inicial
region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_INDEX")
url = f"{host}/{index}/_search"

# Cliente S3 para obtener el geojson
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

# Función Lambda principal
def handler(event, context):
    try:
       # Obtener los parámetros de la solicitud
        params = event.get("queryStringParameters", {})
        country = params.get("country", None)  # El campo country es opcional
        limit = int(params.get("limit", 100))  # Limitar el número de resultados (por defecto 100)
        fromTo = int(params.get("fromTo", 0))    # Paginación (por defecto desde 0)
        print("PARAMS: ", params)
        # Construir la consulta base (sin filtro de país)
        query = {
            "from": fromTo,
            "size": limit,
            "_source": [
                "id", "name", "activity", "thumbnail", "images", 
                "createdAt", "description", "email", "facebook", "identityID", 
                "instagram", "owner", "updatedAt", "userID", "whatsapp","phone", "coordinates","tags"
            ],
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        }
                    ]
                }
            }
        }
      

        # Si se proporciona el parámetro 'country', agregar el filtro geo_polygon
        if country:
            # Obtener el polígono del país desde S3
            polygon_coordinates = get_country_polygon(country)
            if not polygon_coordinates:
                return error_response(f"No se pudo obtener el polígono del país {country}.")

            # Añadir el filtro geo_polygon a la consulta
            query["query"]["bool"]["filter"] = [
                {
                    "geo_polygon": {
                        "coordinates": {
                            "points": polygon_coordinates[0]  # Usar el primer conjunto de coordenadas del polígono
                        }
                    }
                }
            ]

        # Realizar la consulta en OpenSearch
        headers = {"Content-Type": "application/json"}
        r = requests.get(url, auth=awsauth, headers=headers, data=json.dumps(query))

        # Procesar la respuesta
        response_data = json.loads(r.text)
        total = response_data["hits"]["total"]["value"]
        businesses = []

        # Recorrer los resultados
        for hit in response_data["hits"]["hits"]:
            hit_coords = hit["_source"]["coordinates"]
            countryBusiness = get_country_from_coordinates(hit_coords["lon"], hit_coords["lat"])
            viewsBusiness = total_views(hit["_source"].get("id"),hit["_source"].get("userID") )
            # total_fav = total_favorites(hit["_source"].get("id"))
            tags = hit["_source"].get("tags")
            addressString = tags[5].get("value", None)
            if addressString:
                addressBusiness = json.loads(addressString)
                countryB = addressBusiness.get("country", "")
                cityB = addressBusiness.get("city","")
                addressBusiness = f"{cityB}, {countryB}"
            else:
                addressBusiness = countryBusiness
                
            print(addressBusiness)
            business = {
                "id": hit["_source"].get("id"),
                "name": hit["_source"].get("name"),
                "activity": hit["_source"].get("activity"),
                "thumbnail": hit["_source"].get("thumbnail"),
                "images": hit["_source"].get("images"),
                "createdAt": hit["_source"].get("createdAt"),
                "description": hit["_source"].get("description"),
                "email": hit["_source"].get("email"),
                "facebook": hit["_source"].get("facebook"),
                "identityID": hit["_source"].get("identityID"),
                "instagram": hit["_source"].get("instagram"),
                "owner": hit["_source"].get("owner"),
                "updatedAt": hit["_source"].get("updatedAt"),
                "userID": hit["_source"].get("userID"),
                "whatsapp": hit["_source"].get("whatsapp"),
                "phone": hit["_source"].get("phone"),
                "favorites": 0,
                "country": countryBusiness,
                "tags": hit["_source"].get("tags"),
                "views": viewsBusiness,
                "address": addressBusiness
            }
            businesses.append(business)
        print("TOTAL DE BUSIENSS: ", len(businesses))
        print("NEGOCIOS: ", businesses)
        print("RESULTSADOS TOTALESÑ ", total)
        # Retornar éxito con los datos obtenidos
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Búsqueda de negocio exitosa.",
                "items": businesses,
                "limit": limit,
                "from": fromTo,
                "total": total
            })
        }

    except Exception as e:
        # Manejo de error
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error de búsqueda de negocios.",
                "error": str(e)
            })
        }

# Función para obtener geo.json del S3 con el polígono del país
def get_country_polygon(country_code):
    try:
        # Ruta del archivo geo.json en el bucket S3
        file_key = f"public/countries/{country_code}.geo.json"
        response = s3.get_object(Bucket=bucketName, Key=file_key)
        geojson_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Extraer las coordenadas del polígono
        coordinates = geojson_data["features"][0]["geometry"]["coordinates"]
        return coordinates
    except Exception as e:
        print(f"Error obteniendo el geojson del país: {str(e)}")
        return None

# Función para construir la respuesta de error
def error_response(message):
    return {
        'statusCode': 400,
        'body': json.dumps({
            "success": False,
            "message": message
        })
    }

def total_views(business_id, user_id):
    try:
        # Construir la consulta geo_shape para buscar en qué país están las coordenadas
        query = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "eventname.keyword": "user_viewed_business"
                        }
                    },
                    {
                        "term": {
                            "businessid.keyword": f"{business_id}"
                        }
                    }
                ],
                "must_not": [
                    {
                        "term": {
                            "userid.keyword": {
                                "value": f"{user_id}"
                            }
                        }
                    }
                ]
            }
        }
    }
        
        
        headers = {"Content-Type": "application/json"}
        # Realizar la consulta en OpenSearch
        r = requests.get(f"{host}/events/_search", auth=awsauth, headers=headers, data=json.dumps(query))
        
        response_data = json.loads(r.text)
        
        # Obtener el nombre del país del resultado
        total_views = response_data["hits"]["total"]["value"]
        
        return total_views
    except Exception as e:
        print(f"Error obteniendo las vistas del negocio {business_id} desde OpenSearch: {str(e)}")
        return None
    
def total_favorites(business_id):
    query = """
    query ListFavorites(
    $filter: ModelFavoritesFilterInput
    $limit: Int
    $nextToken: String
  ) {
    listFavorites(filter: $filter, limit: $limit, nextToken: $nextToken) {
      items {
        id
        businessID
        userID
        position
        owner
        createdAt
        updatedAt
        __typename
      }
      nextToken
      __typename
    }
  }
    """
    
    variables = {
        "filter": {
           "businessID": {"eq": business_id}
        },
        "limit": 100  # Puedes ajustar el límite según sea necesario
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    total_items = []
    next_token = None

    while True:
        if next_token:
            variables["nextToken"] = next_token
        else:
            variables.pop("nextToken", None)

        response = requests.post(
            appsync_api_url,
            json={"query": query, "variables": variables},
            headers=headers,
        )
        
        data = response.json()
        
        if "errors" in data:
            raise Exception(f"Error en la consulta de AppSync: {data['errors']}")
        
        favorites = data["data"]["listFavorites"]["items"]
        total_items.extend(favorites)
        
        next_token = data["data"]["listFavorites"].get("nextToken")
        
        # Si no hay nextToken, terminamos el ciclo
        if not next_token:
            break

    return total_items

# Función para obtener el país basado en las coordenadas del negocio
def get_country_from_coordinates(lon, lat):
    try:
        # Construir la consulta geo_shape para buscar en qué país están las coordenadas
        query = {
  "_source": ["name"],
  "query": {
    "geo_shape": {
      "geometry": {
        "shape": {
          "type": "point",
          "coordinates": [lon, lat]
        }
      }
    }
  }
}
        
        
        headers = {"Content-Type": "application/json"}
        # Realizar la consulta en OpenSearch
        r = requests.get(f"{host}/countries/_search", auth=awsauth, headers=headers, data=json.dumps(query))
        
        response_data = json.loads(r.text)
        
        # Asegurarse de que la consulta devolvió al menos un país
        if response_data["hits"]["total"]["value"] == 0:
            return None  # No se encontró un país para esas coordenadas
        
        # Obtener el nombre del país del resultado
        country_name = response_data["hits"]["hits"][0]["_source"]["name"]
        
        return country_name
    except Exception as e:
        print(f"Error obteniendo el país desde OpenSearch: {str(e)}")
        return None
