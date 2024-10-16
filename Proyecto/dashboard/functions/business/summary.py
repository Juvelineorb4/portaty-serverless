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

host = os.environ.get("OPENSE_ENDPONIT")
index_business = os.environ.get("OPENSE_INDEX")
url_business = f"{host}/{index_business}/_search"

# Cliente S3 para obtener el geojson del país (si es necesario)
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

# Función Lambda principal
def handler(event, context):
    try:
        # Obtener los parámetros de la solicitud
        params = event.get("queryStringParameters", {})
        country = params.get("country", None)  # El campo country es opcional

        # Construcción de la consulta base
        query = {
            "size": 0,  # No necesitamos los documentos, solo agregaciones
            "query": {
                "bool": {
                    "must": [
                        {"match_all": {}}  # Coincidir con todos los negocios
                    ]
                }
            },
            "aggs": {
                "total_businesses": {
                    "value_count": {
                        "field": "id.keyword"  # Contar negocios por su ID
                    }
                },
                "today_businesses": {
                    "filter": {
                        "range": {
                            "createdAt": {
                                "gte": "now/d"  # Negocios creados hoy
                            }
                        }
                    }
                },
                "yesterday_businesses": {
                    "filter": {
                        "range": {
                            "createdAt": {
                                "gte": "now-1d/d",
                                "lt": "now/d"  # Negocios creados ayer
                            }
                        }
                    }
                },
                "last_7_days_businesses": {
                    "filter": {
                        "range": {
                            "createdAt": {
                                "gte": "now-6d/d",
                                "lt": "now+1d/d"
                            }
                        }
                    }
                },
                "last_30_days_businesses": {
                    "filter": {
                        "range": {
                            "createdAt": {
                                "gte": "now-29d/d",
                                "lt": "now+1d/d"
                            }
                        }
                    }
                },
                "last_12_months_businesses": {
                    "filter": {
                        "range": {
                            "createdAt": {
                                "gte": "now-12M/d"  # Negocios creados en los últimos 12 meses
                            }
                        }
                    }
                }
            }
        }

        # Si se proporciona el parámetro 'country', agregar el filtro geo_polygon
        if country:
            polygon_coordinates = get_country_polygon(country)
            if not polygon_coordinates:
                return error_response(f"No se pudo obtener el polígono del país {country}.")
            
            # Añadir el filtro geo_polygon al query
            query["query"]["bool"]["filter"] = [
                {
                    "geo_polygon": {
                        "coordinates": {
                            "points": polygon_coordinates[0]  # Usar el primer conjunto de coordenadas del polígono
                        }
                    }
                }
            ]

        # Realizar la consulta en OpenSearch para obtener los agregados
        headers = {"Content-Type": "application/json"}
        r_business = requests.get(url_business, auth=awsauth, headers=headers, data=json.dumps(query))
        
        # Procesar la respuesta
        response_data = json.loads(r_business.text)
        print("EJEMPLO: ", response_data)
        total_businesses = response_data["aggregations"]["total_businesses"]["value"]
        today_businesses = response_data["aggregations"]["today_businesses"]["doc_count"]
        yesterday_businesses = response_data["aggregations"]["yesterday_businesses"]["doc_count"]
        last_7_days_businesses = response_data["aggregations"]["last_7_days_businesses"]["doc_count"]
        last_30_days_businesses = response_data["aggregations"]["last_30_days_businesses"]["doc_count"]
        last_12_months_businesses = response_data["aggregations"]["last_12_months_businesses"]["doc_count"]

        # Retornar éxito con los totales obtenidos
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "total_businesses": total_businesses,
                "data":[
                {
                    "title":"Hoy",
                    "total": today_businesses
                },
                {
                    "title":"Ayer",
                    "total": yesterday_businesses
                },
                {
                    "title":"Ultimos 7 dias",
                    "total": last_7_days_businesses
                },
                {
                    "title":"Ultimos 30 dias",
                    "total": last_30_days_businesses
                },
                {
                    "title":"Ultimos 12 meses",
                    "total": last_12_months_businesses
                },
                ]
               
            })
        }

    except Exception as e:
        # Manejo de error
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error en la búsqueda de negocios.",
                "error": str(e)
            })
        }

# Función para obtener geo.json del S3 con el polígono del país
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

# Función para construir la respuesta de error
def error_response(message):
    return {
        'statusCode': 400,
        'body': json.dumps({
            "success": False,
            "message": message
        })
    }
