import boto3
import json
import requests
from requests_aws4auth import AWS4Auth
import os
import math

region = os.environ.get("REGION")
service = "es"
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_INDEX")
url = f"{host}/{index}/_search"

# Cliente de AWS Location para reverse geocoding
location_client = boto3.client('location', region_name=region)

# Cliente S3 para obtener el geojson
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

def handler(event, context):
    print("EVENT:", event)
    print("URL:", url)
    distance = 0
    # obtenemos los valores de queryStringParameters
    params = event["queryStringParameters"]
    print("PARAMS: ", params)
    locationString = params["location"]
    km = params["km"]
    text = params["text"]
    limit = params["limit"]
    fromTo = params["from"]
    location = json.loads(locationString)
    lat = location["lat"]
    lon = location["lon"]
    if (km):
        distance = km

    # Obtener el país desde las coordenadas
    country = get_country(lat, lon)
    if not country:
        return error_response("No se pudo determinar el país de la ubicación proporcionada.")

    # Obtener el polígono del país desde S3
    polygon_coordinates = get_country_polygon(country)
    if not polygon_coordinates:
        return error_response(f"No se pudo obtener el polígono del país {country}.")

    query ={
  "from": fromTo,
  "size": limit,
  "_source": ["id", "name", "activity", "coordinates", "thumbnail", "images"],
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must": [
            {
              "nested": {
                "path": "tags",
                "query": {
                  "bool": {
                    "should": [
                      {
                        "match": {
                          "tags.value": {
                            "query": f"{text}",
                            "fuzziness": "AUTO",
                            "operator": "and"
                          }
                        }
                      },
                      {
                        "wildcard": {
                          "tags.value.keyword": {
                            "value": f"*{text}*"
                          }
                        }
                      }
                    ]
                  }
                }
              }
            },
            {
              "geo_polygon": {
                "coordinates": {
                  "points": polygon_coordinates[0]
                }
              }
            }
          ]
        }
      },
      "functions": [
        {
          "filter": {
            "exists": {
              "field": "tags.priority"
            }
          },
          "field_value_factor": {
            "field": "tags.priority",
            "modifier": "log1p",
            "missing": 1
          },
          "weight": 2
        },
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
          },
          "weight": 1  
        }
      ],
      "score_mode": "sum",
      "boost_mode": "multiply"
    }
  }
}




    # Elasticsearch 6.x requires an explicit Content-Type header
    headers = {"Content-Type": "application/json"}

    # Make the signed HTTP request
    r = requests.get(url, auth=awsauth, headers=headers, data=json.dumps(query))
    print("RESPUESTA:", r.text)

    # transforma string en json
    objecto = json.loads(r.text)
    # arreglo donde se guardan los resultados
    newArray = []
    # total de items extraidos
    total = objecto["hits"]["total"]["value"]

    # recorremos arreglo
    for item in objecto["hits"]["hits"]:
        distanceAprox = distance_two_points(
            lat,
            lon,
            item["_source"]["coordinates"]["lat"],
            item["_source"]["coordinates"]["lon"]
        )
        
        # Condiciones para ciudad o país según la distancia
        if distanceAprox > 1000:
            country = get_country(item["_source"]["coordinates"]["lat"], item["_source"]["coordinates"]["lon"])
            distance_formatted = country
        elif distanceAprox > 100:
            city_country = get_city_country(item["_source"]["coordinates"]["lat"], item["_source"]["coordinates"]["lon"])
            distance_formatted = city_country
        else:
            # Si la distancia es menor a 1 km, mostrarla en metros
            if distanceAprox < 1:
                distance_formatted = f"{int(distanceAprox * 1000)} mts"
            else:
                distance_formatted = f"{round(distanceAprox, 2)} km"
        
        objectoArray = {
            "id": item["_source"]["id"],
            "distance": distance_formatted,
            "activity": item["_source"]["activity"],
            "name": item["_source"]["name"],
            "thumbnail": item["_source"]["thumbnail"],
            "images": item["_source"]["images"]
        }
        newArray.append(objectoArray)
    
    print("ARREGLO RESULTANTE", newArray)

    body = json.dumps({
        "items": newArray,
        "total": len(newArray),
        "limit": len(newArray)
    })
    # Create the response and add some extra content to support CORS
    response = {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": '*'
        },
        "isBase64Encoded": False
    }

    # Add the search results to the response
    response['body'] = body
    return response


def get_country_polygon(country_code):
    try:
        # Obtener el archivo geo.json desde S3
        file_key = f"public/countries/{country_code}.geo.json"
        response = s3.get_object(Bucket=bucketName, Key=file_key)
        geojson_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Extraer las coordenadas del polígono
        coordinates = geojson_data["features"][0]["geometry"]["coordinates"]
        return coordinates
    except Exception as e:
        print(f"Error obteniendo el geojson del país: {str(e)}")
        return None


def distance_two_points(latR, lonR, lat, lon):
    radio_tierra_km = 6371  # Radio de la Tierra en kilómetros
    d_lat = to_radians(lat - latR)
    d_lon = to_radians(lonR - lon)
    a = (math.sin(d_lat / 2) * math.sin(d_lat / 2) +
         math.cos(to_radians(latR)) * math.cos(to_radians(lat)) *
         math.sin(d_lon / 2) * math.sin(d_lon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distancia = radio_tierra_km * c
    return distancia


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
