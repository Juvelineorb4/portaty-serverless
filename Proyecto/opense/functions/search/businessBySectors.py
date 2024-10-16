import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
import json
import os
import math

# Definir Region
region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_INDEX")
awsauth = AWSV4SignerAuth(credentials, region, service)

# Cliente de AWS Location para reverse geocoding
location_client = boto3.client('location', region_name=region)

# Cliente S3 
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

# Lista de sectores
sector_names = [
    "Construcción y Mantenimiento", "Salud", "Legal y Financiero", "Ingeniería y Tecnología",
    "Comercio", "Alimentación", "Transporte", "Hospedaje y Vivienda", "Deporte y Recreación",
    "Educación", "Evaluación y Consultoría"
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
    try:
        params = event["queryStringParameters"]
        print("PARAMS: ", params)
        locationString = params["location"]
        km = params["km"]
        location = json.loads(locationString)
        lat = location["lat"]
        lon = location["lon"]
        distance = km if km else 0
        
        # Obtener el país desde la función de reverse geocoding
        locationCountry = get_country(lat, lon)
        print("PAIS DE LA PERSONA: ", locationCountry)

        # Obtener el polígono del país desde S3
        polygon_coordinates = get_country_polygon(locationCountry)
        print("POLYGON COORDINATES: ", polygon_coordinates)
        if not polygon_coordinates:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    "success": False,
                    "message": f"No se encontró el polígono del país {locationCountry}."
                })
            }
        
        filters = {sector: {"wildcard": {"activity.keyword": f"*{sector}*"}} for sector in sector_names}

        query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {
                            "function_score": {
                                "query": {"match_all": {}},
                                "functions": [
                                    {
                                        "gauss": {
                                            "coordinates": {
                                                "origin": {"lat": lat, "lon": lon},
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
                "sectors": {
                    "filters": {"filters": filters},
                    "aggs": {
                        "top_businesses": {
                            "top_hits": {
                                "size": 6,
                                "_source": ["id", "activity", "name", "thumbnail", "images", "coordinates"],
                                "sort": [{"_score": {"order": "desc"}}]
                            }
                        },
                        "max_score": {"max": {"script": "_score"}},
                        "sector_sort": {"bucket_sort": {"sort": [{"max_score": {"order": "desc"}}]}}
                    }
                }
            }
        }

        # Ejecutar la consulta en OpenSearch
        response = opense.search(body=query, index=index)
        total = response["hits"]["total"]["value"]
        sectors_data = []
        buckets = response['aggregations']['sectors']['buckets']

        for sector_name, sector_info in buckets.items():
            results = []
            for hit in sector_info["top_businesses"]["hits"]["hits"]:
                hit_coords = hit["_source"]["coordinates"]
                distanceAprox = distance_two_points(lat, lon, hit_coords["lat"], hit_coords["lon"])

                # Si la distancia es mayor a 1000 km, obtener solo el país
                if distanceAprox > 1000:
                    country = get_country(hit_coords["lat"], hit_coords["lon"])
                    hit["_source"]["distance"] = country
                # Si la distancia es mayor a 100 km, obtener ciudad
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

            sector_data = {
                "name": sector_name,
                "total": sector_info["doc_count"],
                "results": results
            }
            sectors_data.append(sector_data)
        
        print(sectors_data)

        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Búsqueda de negocio por sectores exitosa.",
                "items": sectors_data,
                "total_items": total
            })
        }
    except Exception as e:
        print(str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error de búsqueda de negocio por sectores.",
                "error": str(e)
            })
        }

# Función para calcular la distancia entre dos puntos (en kilómetros) sin formatear
def distance_two_points(latR, lonR, lat, lon):
    radio_tierra_km = 6371  # Radio de la Tierra en kilómetros
    d_lat = to_radians(lat - latR)
    d_lon = to_radians(lonR - lon)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(to_radians(latR)) * math.cos(to_radians(lat)) *
         math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distancia_km = radio_tierra_km * c
    return distancia_km

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
