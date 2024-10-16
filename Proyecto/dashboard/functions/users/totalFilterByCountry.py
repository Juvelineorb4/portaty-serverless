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
index_users = os.environ.get("OPENSE_INDEX_USERS")
index_business = os.environ.get("OPENSE_INDEX")
url_users = f"{host}/{index_users}/_search"
url_business = f"{host}/{index_business}/_search"

# Cliente S3 para obtener el geojson (si es necesario)
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

# Función Lambda principal
def handler(event, context):
    try:
        # Obtener los parámetros de la solicitud
        params = event.get("queryStringParameters", {})
        country = params.get("country", None)  # El campo country es opcional
        limit = int(params.get("limit", 100))  # Limitar el número de resultados (por defecto 100)
        fromTo = int(params.get("fromTo", 0))  # Paginación (por defecto desde 0)
        # country = None  # El campo country es opcional
        # limit = 100  # Limitar el número de resultados (por defecto 100)
        # fromTo = 0  # Paginación (por defecto desde 0)

        # Construir la consulta base (sin filtro de país) para usuarios
        query_users = {
            "from": fromTo,
            "size": limit,
            "_source": [
                "id", "name", "lastName","lastLocation", "email", "createdAt",
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
            polygon_coordinates = get_country_polygon(country)
            if not polygon_coordinates:
                return error_response(f"No se pudo obtener el polígono del país {country}.")
            
            query_users["query"]["bool"]["filter"] = [
                {
                    "geo_polygon": {
                        "lastLocation": {
                            "points": polygon_coordinates[0]  # Usar el primer conjunto de coordenadas del polígono
                        }
                    }
                }
            ]

        # Realizar la consulta en OpenSearch para obtener usuarios
        headers = {"Content-Type": "application/json"}
        r_users = requests.get(url_users, auth=awsauth, headers=headers, data=json.dumps(query_users))

        # Procesar la respuesta de los usuarios
        response_data_users = json.loads(r_users.text)
        total = response_data_users["hits"]["total"]["value"]
        users = []

        # Recorrer los resultados y obtener los negocios relacionados
        for hit in response_data_users["hits"]["hits"]:
            user_id = hit["_source"].get("id")
            user_coords = hit["_source"].get("lastLocation")
            
            # Si el campo lastLocation no existe o es null, asignar "Desconocido"
            if user_coords is None:
                countryUser = "Desconocido"
            else:
                countryUser = get_country_from_coordinates(user_coords["lon"], user_coords["lat"])

            # Obtener los negocios asociados al userID
            businesses = get_businesses_by_user(user_id)

            user = {
                "id": hit["_source"].get("id"),
                "name": hit["_source"].get("name"),
                "lastName": hit["_source"].get("lastName"),
                "email": hit["_source"].get("email"),
                "createdAt": hit["_source"].get("createdAt"),
                "country": countryUser,
                "business": businesses  # Agregar los negocios relacionados al usuario
            }
            users.append(user)
        print(users)
        # Retornar éxito con los datos obtenidos
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Búsqueda de usuarios exitosa.",
                "items": users,
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
                "message": "Error de búsqueda de usuarios.",
                "error": str(e)
            })
        }

# Función para obtener geo.json del S3 con el polígono del país (si es necesario)
def get_country_polygon(country_code):
    try:
        file_key = f"public/countries/{country_code}.geo.json"
        response = s3.get_object(Bucket=bucketName, Key=file_key)
        geojson_data = json.loads(response['Body'].read().decode('utf-8'))
        coordinates = geojson_data["features"][0]["geometry"]["coordinates"]
        return coordinates
    except Exception as e:
        print(f"Error obteniendo el geojson del país: {str(e)}")
        return None

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

# Función para obtener los negocios relacionados con un usuario por su userID
def get_businesses_by_user(user_id):
    try:
        query = {
            "_source": ["id", "name", "activity", "phone", "thumbnail", "tags"],
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

        businesses = []
        for hit in response_data_business["hits"]["hits"]:
            tags = hit["_source"].get("tags")
            addressString = tags[5].get("value", None)
            if addressString:
                addressBusiness = json.loads(addressString)
                countryB = addressBusiness.get("country", "")
                cityB = addressBusiness.get("city","")
                addressBusiness = f"{cityB}, {countryB}"
            else:
                addressBusiness = "Desconocido"
            business = {
                "id": hit["_source"].get("id"),
                "name": hit["_source"].get("name"),
                "activity": hit["_source"].get("activity"),
                "phone":  hit["_source"].get("phone"),
                "thumbnail":  hit["_source"].get("thumbnail"),
                "address": addressBusiness
            }
            businesses.append(business)

        return businesses
    except Exception as e:
        print(f"Error obteniendo negocios del usuario {user_id}: {str(e)}")
        return []

# Función para construir la respuesta de error
def error_response(message):
    return {
        'statusCode': 400,
        'body': json.dumps({
            "success": False,
            "message": message
        })
    }
