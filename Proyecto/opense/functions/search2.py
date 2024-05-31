import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from requests_aws4auth import AWS4Auth
import json
import os
import math

region = os.environ.get("REGION")
service = "es"
credentials = boto3.Session().get_credentials()
# awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_INDEX")
url = f"{host}/{index}/_search"
awsauth = AWSV4SignerAuth(credentials, region, service)

opense = OpenSearch(
    hosts=[{'host': "search-portaty-opense-f2pru5qxiz73a53c7fstafplnu.us-east-1.es.amazonaws.com", 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20
)

query = {
    "query": {
        "match_all": {}
    }
}


def handler(event, context):

    try:
        print("EVENT:", event)
        print("URL:", url)
        distance = 0
        # obtenemos los valores de queryStringParameters
        params = event["queryStringParameters"]
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

        r = opense.search(
            body=query,
            index=index
        )

        print("RESPUESTA DE BUSQUEDA: ", r)

        # arreglo donde se aguardar los resultados
        newArray = []
        # total de items extraidos
        total = r["hits"]["total"]["value"]
        print("TOTAL: ", total)
        for item in r["hits"]["hits"]:
            sourceItem = item.get("_source")
            if (sourceItem["thumbnail"] is None):
                continue
            else:
                distanceAprox = distance_two_points(
                    lat,
                    lon,
                    item["_source"]["coordinates"]["lat"],
                    item["_source"]["coordinates"]["lon"]
                )
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
            "total": total,
            "limit": len(newArray)
        })

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
    except Exception as e:
        body_error = {
            "message": "Error al ejecutar lambda!",
        }
        print("Error al ejecutar lambda!: ", e)
        return {
            "statusCode": 400,
            "body": json.dumps(body_error)
        }


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
