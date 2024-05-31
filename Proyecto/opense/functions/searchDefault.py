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


def handler(event, context):
    print("EVENT:", event)
    print("URL:", url)
    distance = 0
    # obtenemos los valores de queryStringParameters
    params = event["queryStringParameters"]
    print("PARAMS: ", params)
    locationString = params["location"]
    km = params["km"]
    limit = params["limit"]
    fromTo = params["from"]
    location = json.loads(locationString)
    lat = location["lat"]
    lon = location["lon"]
    if (km):
        distance = km

    query = {
        "from": fromTo,
        "size": limit,
        "query": {
            "function_score": {
                "query": {
                    "match_all": {}
                },
                "functions": [
                    {
                        "filter": {
                            "exists": {
                                "field": "coordinates"
                            }
                        },
                        "gauss": {
                            "coordinates": {
                                "origin": f"{lat},{lon}",
                                "offset": f"{distance}km",
                                "scale":  f"{distance}km",
                                "decay": 0.25
                            }
                        }
                    }
                ],
                "score_mode": "sum"
            }
        },
        "sort": [
            {
                "_score": {
                    "order": "desc"
                }
            }
        ]
    }

   # Elasticsearch 6.x requires an explicit Content-Type header
    headers = {"Content-Type": "application/json"}

    # Make the signed HTTP request
    r = requests.get(url, auth=awsauth, headers=headers,
                     data=json.dumps(query))
    print("RESPUESTA:", r.text)
    # transforma stirng en json
    objecto = json.loads(r.text)
    # arreglo donde se aguardar los resultados
    newArray = []
    # total de items extraidos
    total = objecto["hits"]["total"]["value"]
    # recorremos arreglo
    for item in objecto["hits"]["hits"]:
        # if item["_score"] < 0.1:
        #     continue
        distanceAprox = distance_two_points(
            lat,
            lon,
            item["_source"]["coordinates"]["lat"],
            item["_source"]["coordinates"]["lon"]
        )
        sourceItem = item.get("_source")
        imagesSource = sourceItem.get("images")
        thumbnail = sourceItem.get("thumbnail", imagesSource[0])
        print("QUE OBTENEDRE DE YHUMBNAIL ", thumbnail)
        objectoArray = {
            "id": item["_source"]["id"],
            "distance": distanceAprox,
            "activity": item["_source"]["activity"],
            "name": item["_source"]["name"],
            "thumbnail": item["_source"]["thumbnail"],
            "images": item["_source"]["images"],
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
