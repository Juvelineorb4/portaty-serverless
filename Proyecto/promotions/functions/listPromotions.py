import boto3
import json
import requests
from requests_aws4auth import AWS4Auth
import os
import math
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")


region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_BUSINESS_INDEX")
url = f"{host}/{index}/_search"

def list_promotions(business_ids):
    # Definir el query GraphQL para obtener las promociones de negocio
    # Construir el filtro dinámico para los IDs de negocios
    business_id_filters = [{"businessID": {"eq": id}} for id in business_ids]
    query = """
    query ListBusinessPromotions(
    $filter: ModelBusinessPromotionFilterInput
    $limit: Int
    $nextToken: String
  ) {
        listBusinessPromotions(
      filter: $filter
      limit: $limit
      nextToken: $nextToken
    ) {
            items {
                id
                title
                image
                businessID
                business {
                    id
                    name
                    images
                    thumbnail
                    activity
                    coordinates{
                        lat
                        lon
                    }
                }
            }
        }
    }
    """
    variables = {
        "filter": {
            "and": [
                {"status": {"eq": "PUBLISHED"}},
                {"or": business_id_filters}
            ]
        }
    }
    print("FILTER: ", variables)
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    response = requests.post(
        appsync_api_url,
        json={"query": query, "variables": variables},
        headers=headers,
    )
    return response.json()["data"]["listBusinessPromotions"]["items"]

def list_business_by_distance(location, user_id):
    lat = location["lat"]
    lon = location["lon"]
    query = {
  "from": 0, 
  "size": 100, 
  "_source": ["id", "thumbnail"],
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
    # Elasticsearch 6.x requires an explicit Content-Type header
    headers = {"Content-Type": "application/json"}

    # Make the signed HTTP request
    r = requests.get(url, auth=awsauth, headers=headers, data=json.dumps(query))
    search_results = json.loads(r.text)

    # Extraer los IDs de los resultados
    hits = search_results.get('hits', {}).get('hits', [])
    ids = [hit['_source']['id'] for hit in hits]
    
    print("IDs de los negocios encontrados:", ids)
    return ids

def handler(event, context):
    print("EVENTO: ", event)
    params = event["queryStringParameters"]
    print("PARAMS: ", params)
    locationString = params["location"]
    location = json.loads(locationString)
    user_id = params["userID"]

    try:
        # Realizar búsqueda de negocios por distancia 
        business_ids_distance = list_business_by_distance(location, user_id)
        
        # Si no hay negocios cercanos, devolver una respuesta vacía
        if not business_ids_distance:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    "success": True,
                    "data": [],
                    "message": "No hay negocios cercanos a 100km."
                })
            }
        
        # Realizar la consulta para obtener información de las promociones
        promotions_info = list_promotions(business_ids_distance)
        print("Información de las promociones:", promotions_info)
  
        # Procesar la información para construir el array de stories
        stories = []
        user_business_stories = []
        other_business_stories = []

        for promotion in promotions_info:
            business_id = promotion['business'].get('id', '')
            business_name = promotion['business'].get('name', '')
            business_thumbnail = promotion['business'].get('thumbnail', '')
            promotion_id = promotion.get('id', '')
            promotion_image_url = promotion.get('image', '')
            promotion_title = promotion.get('title', '')
            business_activity = promotion['business'].get('activity', '')
            business_images = promotion['business'].get('images', '')
            business_coordinates = promotion['business'].get('coordinates', '')
            
            # Construir el objeto de historia (story)
            story = {
                'id': promotion_id,
                'source': {
                    'uri': promotion_image_url
                },
                "text": promotion_title 
            }
            
            # Verificar si el negocio ya existe en stories
            business_obj = next((b for b in stories if b['id'] == business_id), None)
            if business_obj:
                business_obj['stories'].append(story)
            else:
                # Si no existe, agregar el negocio con su primera historia
                business_obj = {
                    'id': business_id,
                    'name': f'{business_name[:5]}...',
                    'imgUrl': business_thumbnail,
                    'stories': [story],
                    "data": {
                        "id": business_id,
                        "activity": business_activity,
                        "name": business_name,
                        "thumbnail": business_thumbnail,
                        "images": business_images,
                        "coordinates": business_coordinates
                    }
                }

            # Verificar si este negocio pertenece al usuario
            if promotion['business'].get('userID') == user_id:
                user_business_stories.append(business_obj)
            else:
                other_business_stories.append(business_obj)

        # Combinar las historias de los negocios del usuario primero y luego los demás
        stories = user_business_stories + other_business_stories

        # Devolver la respuesta exitosa con los datos consultados
        print("stories", stories)
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "data": stories,
                "message": "Promociones consultadas con éxito."
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
