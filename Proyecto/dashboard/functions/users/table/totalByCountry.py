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
index_users = os.environ.get("OPENSE_INDEX_USERS")
index_business = os.environ.get("OPENSE_INDEX")
url_users = f"{host}/{index_users}/_search"
url_business = f"{host}/{index_business}/_search"



# Función Lambda principal
# Función Lambda principal (actualizada)
def handler(event, context):
    try:
        # Obtener los parámetros de la solicitud
        params = event.get("queryStringParameters", {})
        print("PARAMS: ", params)
        period = params.get("range", "30D")  # Puede ser '7D', '30D', '12M', "TODAY", 'YESTERDAY'
        country = params.get("country", None)  # El campo country es opcional
        limit = int(params.get("limit", 100))  # Limitar el número de resultados (por defecto 100)
        fromTo = int(params.get("fromTo", 0))  # Paginación (por defecto desde 0)
        
        
        
        # Calcular las fechas basadas en el periodo seleccionado
        current_date = datetime.now(timezone.utc)
        end_date = current_date.strftime('%Y-%m-%dT23:59:59Z')  # Fecha actual (hoy)
        
        if period == "7D":
            start_date = (current_date - timedelta(days=6)).strftime('%Y-%m-%dT00:00:00Z')
        elif period == "30D":
            start_date = (current_date - timedelta(days=29)).strftime('%Y-%m-%dT00:00:00Z')
        elif period == "TODAY":
            start_date = (current_date).strftime('%Y-%m-%dT00:00:00Z')
        elif period == "YESTERDAY":
            yesterday = current_date - timedelta(days=1)
            start_date = yesterday.strftime('%Y-%m-%dT00:00:00Z')
            end_date = yesterday.strftime('%Y-%m-%dT23:59:59Z')
        else:  # Asumimos que el periodo es '12M'
            start_date = (current_date - timedelta(days=365)).strftime('%Y-%m-%dT00:00:00Z')

        # Obtener la lista de userID con negocios
        user_ids_with_businesses = get_users_with_business()

        # Construir la consulta base (sin filtro de país) para usuarios
        query_users = {
            "from": fromTo,
            "size": limit,
            "_source": [
                "id", "name", "lastName", "lastLocation", "email", "createdAt",
            ],
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        }
                    ],
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
                        "order": "desc"
                    }
                }
            ],
            "script_fields": {
                "hasBusiness": {
                    "script": {
                        "source": """
                            def business_ids = params.business_ids;
                            return business_ids.contains(doc['id.keyword'].value);
                        """,
                        "params": {
                            "business_ids": user_ids_with_businesses  # Lista de IDs con negocios
                        }
                    }
                }
            }
        }

        # Si se proporciona el parámetro 'country', agregar el filtro geo_polygon
        if country:
            polygon_coordinates = get_country_polygon_from_opensearch(country)
            if not polygon_coordinates:
                return error_response(f"No se pudo obtener el polígono del país {country}.")
            
            query_users["query"]["bool"]["filter"].append(
                {
                    "geo_polygon": {
                        "lastLocation": {
                            "points": polygon_coordinates[0]  # Usar las coordenadas del polígono del país
                        }
                    }
                }
            )
        print("QUERY OPENSE",query_users )
        # Realizar la consulta en OpenSearch para obtener usuarios
        headers = {"Content-Type": "application/json"}
        r_users = requests.get(url_users, auth=awsauth, headers=headers, data=json.dumps(query_users))
        # Procesar la respuesta de los usuarios
        response_data_users = json.loads(r_users.text)
        print("RESULTADO OPENSE: ", response_data_users)
        total = response_data_users["hits"]["total"]["value"]
        users = []

        
        
        # Recorrer los resultados y construir los usuarios con el campo hasBusiness
        for hit in response_data_users["hits"]["hits"]:
            user_coords = hit["_source"].get("lastLocation")
            
            # Si el campo lastLocation no existe o es null, asignar "Desconocido"
            if user_coords is None:
                countryUser = "Desconocido"
            else:
                countryUser = get_country_from_coordinates(user_coords["lon"], user_coords["lat"])
            user = {
                "id": hit["_source"].get("id"),
                "name": hit["_source"].get("name"),
                "lastName": hit["_source"].get("lastName"),
                "email": hit["_source"].get("email"),
                "createdAt": hit["_source"].get("createdAt"),
                "country": countryUser,
                "hasBusiness": hit["fields"]["hasBusiness"][0]  # True o False si el usuario tiene al menos un negocio
            }
            users.append(user)
        body = {
                "success": True,
                "message": "Búsqueda de usuarios exitosa.",
                "items": users,  # usuarios que trae
                "limit": limit,  # usuarios traidos default 100
                "from": fromTo,  # inicio de paginacion default 0
                "total": total  # total de negocios existentes
        }
        print("BODY: ", body)
        # Retornar éxito con los datos obtenidos
        return {
            'statusCode': 200,
            'body': json.dumps(body)
        }

    except Exception as e:
        # Manejo de error
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error de búsqueda de usuarios.",
                "error": str(e)
            })
        }

# Función optimizada para obtener el polígono del país desde OpenSearch
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



def get_users_with_business():
    try:
        query_business = {
            "size": 0,  # No queremos resultados, solo agregaciones
            "aggs": {
                "users_with_businesses": {
                    "terms": {
                        "field": "userID.keyword",
                        "size": 10000  # Ajustar el tamaño si esperas más usuarios
                    }
                }
            }
        }

        headers = {"Content-Type": "application/json"}
        r_business = requests.get(url_business, auth=awsauth, headers=headers, data=json.dumps(query_business))
        business_data = json.loads(r_business.text)

        # Obtener la lista de userID con negocios
        user_ids_with_businesses = [bucket['key'] for bucket in business_data['aggregations']['users_with_businesses']['buckets']]
        return user_ids_with_businesses

    except Exception as e:
        print(f"Error obteniendo usuarios con negocios: {str(e)}")
        return []

# Función para obtener el país basado en las coordenadas del usuario
def get_country_from_coordinates(lon, lat):
    try:
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
        r = requests.get(f"{host}/countries/_search", auth=awsauth, headers=headers, data=json.dumps(query))
        response_data = json.loads(r.text)
        if response_data["hits"]["total"]["value"] == 0:
            return "Desconocido"  # No se encontró un país para esas coordenadas
        country_name = response_data["hits"]["hits"][0]["_source"]["name"]
        return country_name
    except Exception as e:
        print(f"Error obteniendo el país desde OpenSearch: {str(e)}")
        return "Desconocido"

# Función para verificar si el usuario tiene al menos un negocio
def user_has_business(user_id):
    try:
        query = {
            "_source": ["id"],
            "query": {
                "bool": {
                    "must": [
                        {"term": {"userID.keyword": user_id}}
                    ]
                }
            }
        }

        headers = {"Content-Type": "application/json"}
        r_business = requests.get(url_business, auth=awsauth, headers=headers, data=json.dumps(query))
        response_data_business = json.loads(r_business.text)
        
        # Verificar si el usuario tiene al menos un negocio
        return len(response_data_business["hits"]["hits"]) > 0

    except Exception as e:
        print(f"Error verificando negocios del usuario {user_id}: {str(e)}")
        return False

# Función para construir la respuesta de error
def error_response(message):
    return {
        'statusCode': 400,
        'body': json.dumps({
            "success": False,
            "message": message
        })
    }
