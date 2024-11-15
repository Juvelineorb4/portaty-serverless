import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
import json
import os
import math

# Definir Region
region = os.environ.get("AWS_REGION")
# Servicio
service = "es"
# Credentials
credentials = boto3.Session().get_credentials()
# Parámetros para configurar OpenSearch
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_INDEX")
url = f"{host}/{index}/_search"
awsauth = AWSV4SignerAuth(credentials, region, service)

print(f"Host: {host}, Index: {index}, url: {url}")

# Cliente de AWS Location para reverse geocoding
location_client = boto3.client('location', region_name=region)

# Cliente S3
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

# Lista de sectores
sector_names = [
    "Construcción y Mantenimiento",
    "Salud",
    "Legal y Financiero",
    "Ingeniería y Tecnología",
    "Comercio",
    "Alimentación",
    "Transporte",
    "Hospedaje y Vivienda",
    "Deporte y Recreación",
    "Educación",
    "Evaluación y Consultoría",
    "Iglesias"
]

# Configuración de OpenSearch
opense = OpenSearch(
    hosts=[{'host': host.replace("https://", ""), 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20
)

# Función para obtener geo.json del S3
def get_country_polygon(country_code):
    try:
        # Obtener el archivo geo.json desde S3
        file_key = f"public/countries/{country_code}.geo.json"  # Aquí puedes adaptar la ruta si es necesario
        response = s3.get_object(Bucket=bucketName, Key=file_key)
        geojson_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Extraer las coordenadas del polígono
        coordinates = geojson_data["features"][0]["geometry"]["coordinates"]
        return coordinates
    except Exception as e:
        print(f"Error obteniendo el geojson del país: {str(e)}")
        return None

def handler(event, context):
    print("EVENT:", event)
    print("URL:", url)
    
    # obtener los valores de queryStringParameters
    params = event.get("queryStringParameters", {})
    
    # Validaciones
    if not params:
        return error_response("Los parámetros de consulta están vacíos o no se proporcionaron.")
    
    locationString = params.get("location", None)
    if not locationString:
        return error_response("El parámetro 'location' no se proporcionó.")
    
    try:
        location = json.loads(locationString)
    except json.JSONDecodeError:
        return error_response("El parámetro 'location' no tiene un formato JSON válido.")
    
    lat = location.get("lat", None)
    lon = location.get("lon", None)
    if lat is None or lon is None:
        return error_response("Faltan 'lat' o 'lon' en el parámetro 'location'.")

    km = params.get("km", 0)
    sector = params.get("sector", None)
    if not sector:
        return error_response("El parámetro 'sector' no se proporcionó.")
    
    # Validar si el sector está en la lista de sectores permitidos
    if sector not in sector_names:
        return error_response(f"El sector '{sector}' no es válido. Los sectores permitidos son: {', '.join(sector_names)}")
    
    distance = km or 0

    # Obtener el país desde la función de reverse geocoding
    country = get_country(lat, lon)
    if not country:
        return error_response("No se pudo determinar el país de la ubicación proporcionada.")

    # Obtener el polígono del país desde S3
    polygon_coordinates = get_country_polygon(country)
    if not polygon_coordinates:
        return error_response(f"No se pudo obtener el polígono del país {country}.")
    
    try:
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {
                            "function_score": {
                                "query": {
                                    "wildcard": {
                                        "activity.keyword": f"*{sector}*"
                                    }
                                },
                                "functions": [
                                    {
                                        "gauss": {
                                            "coordinates": {
                                                "origin": {
                                                    "lat": lat, 
                                                    "lon": lon  
                                                },
                                                "scale": f"{distance}km",
                                                "offset": f"{distance}km",
                                                "decay": 0.5
                                            }
                                        }
                                    }
                                ],
                                "score_mode": "multiply",
                                "boost_mode": "replace"
                            }
                        },
                        {
                            "geo_polygon": {
                                "coordinates": {
                                    "points": polygon_coordinates[0]  # Utilizamos el primer conjunto de coordenadas
                                }
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "by_sub_activity": {
                    "terms": {
                        "field": "activity.keyword",
                        "size": 10
                    },
                    "aggs": {
                        "top_businesses": {
                            "top_hits": {
                                "from": 0,
                                "size": 6,
                                "sort": [
                                    {
                                        "_score": {
                                            "order": "desc"
                                        }
                                    }
                                ],
                                "_source": ["id", "name", "activity", "coordinates", "thumbnail", "images"]
                            }
                        }
                    }
                }
            }
        }

        # Ejecutar la consulta en OpenSearch
        response = opense.search(body=query, index=index)
        # total de items extraidos
        total = response["hits"]["total"]["value"]
        print("TOTAL: ", total)
        # Procesar los datos y extraer la información deseada
        activities_data = []
        buckets = response['aggregations']['by_sub_activity']['buckets']    
        for item in buckets:
            results = []
            activity_obj = json.loads(item["key"])
            sub = activity_obj.get("sub", None)
            print("SUB: ", sub)
            for hit in item["top_businesses"]["hits"]["hits"]:
                hit_coords = hit["_source"]["coordinates"]
                distanceAprox = distance_two_points(lat, lon, hit_coords["lat"], hit_coords["lon"])
                
                # Si la distancia es mayor a 1000 km, obtener solo el país
                if distanceAprox > 1000:
                    country = get_country(hit_coords["lat"], hit_coords["lon"])
                    hit["_source"]["distance"] = country
                # Si la distancia es mayor a 100 km, obtener ciudad y país
                elif distanceAprox > 100:
                    city_country = get_city_country(hit_coords["lat"], hit_coords["lon"])
                    hit["_source"]["distance"] = city_country
                else:
                    # Si la distancia es menor a 1 km, mostrarla en metros
                    if distanceAprox < 1:
                        hit["_source"]["distance"] = f"{int(distanceAprox * 1000)} mts"
                    # Si es mayor o igual a 1 km, mostrarla en kilómetros con dos decimales
                    else:
                        hit["_source"]["distance"] = f"{round(distanceAprox, 2)} km"

                results.append(hit["_source"])
            activity_data = {
                "name": sub,
                "total": item["doc_count"],
                "results": results
            }
            activities_data.append(activity_data)
        print("activities_data: ", activities_data)
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Búsqueda de negocio por actividades exitosa.",
                "items": activities_data,
                "total_items": total
            })
        }
    except Exception as e:
        error_message = str(e)
        return error_response(f"Error de búsqueda de negocio por sectores: {error_message}")

# Función para calcular la distancia entre dos puntos (en kilómetros)
def distance_two_points(latR, lonR, lat, lon):
    radio_tierra_km = 6371  # Radio de la Tierra en kilómetros
    d_lat = to_radians(lat - latR)
    d_lon = to_radians(lonR - lon)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(to_radians(latR)) * math.cos(to_radians(lat)) *
         math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distancia_km = radio_tierra_km * c
    return distancia_km  # Retornamos la distancia como un número flotante

def to_radians(degrees):
    return degrees * (math.pi / 180)

# Función para obtener la ciudad y el país (reverse geocoding)
def get_city_country(lat, lon):
    try:
        response = location_client.search_place_index_for_position(
            IndexName=os.environ.get("PLACE_INDEX_NAME"),
            Position=[lon, lat],
            MaxResults=1
        )
        if response['Results']:
            place = response['Results'][0]['Place']
            return f"{place.get('Municipality', 'Desconocido')}"
        else:
            return "Desconocido"
    except Exception as e:
        print(f"Error en reverse geocoding: {str(e)}")
        return "Desconocido"

# Función para obtener solo el país
def get_country(lat, lon):
    try:
        response = location_client.search_place_index_for_position(
            IndexName=os.environ.get("PLACE_INDEX_NAME"),
            Position=[lon, lat],
            MaxResults=1
        )
        if response['Results']:
            place = response['Results'][0]['Place']
            return place.get('Country', 'Desconocido')
        else:
            return "Desconocido"
    except Exception as e:
        print(f"Error en reverse geocoding: {str(e)}")
        return "Desconocido"

def error_response(message):
    return {
        'statusCode': 400,
        'body': json.dumps({
            "success": False,
            "message": message
        })
    }
