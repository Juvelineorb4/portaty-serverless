import boto3
import json
import requests
from requests_aws4auth import AWS4Auth
import os
from datetime import datetime, timedelta, timezone

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
# Función Lambda principal (actualizada para polígonos desde OpenSearch)
def handler(event, context):
    try:
       # Obtener los parámetros de la solicitud
        params = event.get("queryStringParameters", {})
        country = params.get("country", None)  # El campo country es opcional
        period = params.get("range", "12M")  # Puede ser '7D', '30D', '12M', 'TODAY', 'YESTERDAY'
        limit = int(params.get("limit", 10))  # Limitar el número de resultados (por defecto 10)
        fromTo = int(params.get("fromTo", 0))  # Paginación (por defecto desde 0)
        print("PARAMS: ", params)

        # Calcular las fechas basadas en el periodo seleccionado
        current_date = datetime.now(timezone.utc)
        end_date = current_date.strftime('%Y-%m-%dT23:59:59Z')  # Fecha actual (hoy)
        
        if period == "7D":
            start_date = (current_date - timedelta(days=6)).strftime('%Y-%m-%dT00:00:00Z')
        elif period == "30D":
            start_date = (current_date - timedelta(days=29)).strftime('%Y-%m-%dT00:00:00Z')
        elif period == "TODAY":
            start_date = current_date.strftime('%Y-%m-%dT00:00:00Z')
        elif period == "YESTERDAY":
            yesterday = current_date - timedelta(days=1)
            start_date = yesterday.strftime('%Y-%m-%dT00:00:00Z')
            end_date = yesterday.strftime('%Y-%m-%dT23:59:59Z')
        else:  # Asumimos que el periodo es '12M'
            start_date = (current_date - timedelta(days=365)).strftime('%Y-%m-%dT00:00:00Z')

        # Construir la consulta base (sin filtro de país)
        query = {
            "from": fromTo,
            "size": limit,
            "_source": [
                "id", "name", "activity", "thumbnail", 
                "createdAt", "email", "facebook", "identityID","userID", "phone", "coordinates","tags"
            ],
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        }
                    ],
                    # Filtro para rango de fechas basado en `createdAt`
                    "filter": [
                        {
                            "range": {
                                "createdAt": {
                                    "gte": start_date,
                                    "lt": end_date,
                                    "format": "strict_date_optional_time"
                                }
                            }
                        }
                    ]
                }
            },
              "sort": [
                {
                    "createdAt": {
                        "order": "desc"  # Ordenar por la fecha de creación en orden descendente
                    }
                }
            ]
        }


        # Si se proporciona el parámetro 'country', agregar el filtro geo_polygon
        if country:
            # Obtener el polígono del país desde OpenSearch
            polygon_coordinates = get_country_polygon_from_opensearch(country)
            if not polygon_coordinates:
                return error_response(f"No se pudo obtener el polígono del país {country}.")

            # Añadir el filtro geo_polygon a la consulta
            query["query"]["bool"]["filter"].append(
                {
                    "geo_polygon": {
                        "coordinates": {
                            "points": polygon_coordinates[0]  # Usar las coordenadas del polígono del país
                        }
                    }
                }
            )
        # Realizar la consulta en OpenSearch
        headers = {"Content-Type": "application/json"}
        r = requests.get(url, auth=awsauth, headers=headers, data=json.dumps(query))

        # Procesar la respuesta
        response_data = json.loads(r.text)
        total = response_data["hits"]["total"]["value"]
        businesses = []
        # Crear una lista con todos los IDs de negocio
        business_ids = [{"id":hit["_source"].get("id"),"userID":hit["_source"].get("userID")} for hit in response_data["hits"]["hits"]]
        print("BUSINESS IDS: ", business_ids)
        resultTotal = total_views_for_all_businesses(business_ids)
        print("VIEWS TOTAL: ", resultTotal)
        # Recorrer los resultados
        for hit in response_data["hits"]["hits"]:
            hit_coords = hit["_source"]["coordinates"]
            countryBusiness = get_country_from_coordinates(hit_coords["lon"], hit_coords["lat"])
            total_fav = total_favorites(hit["_source"].get("id"))
           # Uso dentro de tu función
            tags = hit["_source"].get("tags", [])
            addressBusiness = extract_address_from_tags(tags)

            if addressBusiness is None:
                addressBusiness = countryBusiness  # Usa el valor alternativo si no encuentras una dirección

            # Obtener las vistas desde el diccionario resultTotal usando el business_id
            business_id = hit["_source"].get("id")
            viewsBusiness = resultTotal.get(business_id, 0)

            business = {
                "id": hit["_source"].get("id"),
                "name": hit["_source"].get("name"),
                "activity": hit["_source"].get("activity"),
                "thumbnail": hit["_source"].get("thumbnail"),
                "createdAt": hit["_source"].get("createdAt"),
                "email": hit["_source"].get("email"),
                "identityID": hit["_source"].get("identityID"),
                "userID": hit["_source"].get("userID"),
                "phone": hit["_source"].get("phone"),
                "favorites": total_fav,
                "country": countryBusiness,
                "views": viewsBusiness,
                "address": addressBusiness
            }
            print(business)
            businesses.append(business)

        # Retornar éxito con los datos obtenidos
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Búsqueda de negocio exitosa.",
                "items": businesses,  # negocios
                "limit": limit,  # límite dado
                "from": fromTo,  # inicio de paginación
                "total": total  # número total de negocios
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
def total_views_for_all_businesses(business_ids):
    try:
        # Crear el filtro para excluir eventos donde el userID sea igual al businessID específico
        must_not_clauses = []
        
        for business in business_ids:
            if "userID" in business and business["userID"]:
                must_not_clauses.append({
                    "bool": {
                        "must": [
                            {"term": {"businessid.keyword": business["id"]}},
                            {"term": {"userid.keyword": business["userID"]}}
                        ]
                    }
                })
        
        # Construir la consulta con agregaciones para contar vistas de todos los negocios
        query = {
            "size": 0,  # No necesitamos los documentos, solo la agregación
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "eventname.keyword": "user_viewed_business"
                            }
                        },
                        {
                            "terms": {
                                "businessid.keyword": [business["id"] for business in business_ids]  # Lista de todos los IDs de negocios
                            }
                        }
                    ],
                    "must_not": must_not_clauses  # Agregar las exclusiones por businessID y userID
                }
            },
            "aggs": {
                "business_views": {
                    "terms": {
                        "field": "businessid.keyword",
                        "size": len(business_ids)  # Número máximo de IDs a devolver
                    }
                }
            }
        }

        headers = {"Content-Type": "application/json"}
        # Realizar la consulta en OpenSearch
        print("QUERY VIEWS: ", query)
        r = requests.get(f"{host}/events/_search", auth=awsauth, headers=headers, data=json.dumps(query))
        response_data = json.loads(r.text)
        print("RESULT DE VISTAS: ", response_data)
        # Recoger las agregaciones para cada negocio
        business_views = {bucket['key']: bucket['doc_count'] for bucket in response_data['aggregations']['business_views']['buckets']}
        
        return business_views  # Retorna un diccionario con {business_id: total_views}
    
    except Exception as e:
        print(f"Error obteniendo las vistas de los negocios desde OpenSearch: {str(e)}")
        return {}

# Función para obtener el polígono del país desde OpenSearch (reutilizada)
def get_country_polygon_from_opensearch(country_code):
    try:
        query = {
            "query": {
                "term": {
                    "id": {
                        "value": country_code
                    }
                }
            }
        }

        headers = {"Content-Type": "application/json"}
        r = requests.get(f"{host}/countries/_search", auth=awsauth, headers=headers, data=json.dumps(query))
        response_data = json.loads(r.text)

        if response_data["hits"]["total"]["value"] == 0:
            return None  # No se encontró el país

        # Obtener las coordenadas del polígono
        polygon_coordinates = response_data["hits"]["hits"][0]["_source"]["geometry"]["coordinates"]
        return polygon_coordinates

    except Exception as e:
        print(f"Error obteniendo el polígono del país desde OpenSearch: {str(e)}")
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

    return len(total_items)

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

# Función para extraer la dirección del tag que contiene el JSON con la dirección
def extract_address_from_tags(tags):
    for tag in tags:
        try:
            # Intentar convertir el valor del tag a JSON
            address_data = json.loads(tag.get("value", "{}"))
            
            # Verificar que contiene los campos que esperas, como "city" o "country"
            if "city" in address_data and "country" in address_data:
                cityB = address_data.get("city", "")
                countryB = address_data.get("country", "")
                address = f"{cityB}, {countryB}"
                return address  # Si encuentras la dirección, la devuelves
        except (json.JSONDecodeError, KeyError):
            # Si no es un JSON válido o no tiene los campos esperados, continúas
            continue
    return None  # Retorna None si no encuentras una dirección válida
