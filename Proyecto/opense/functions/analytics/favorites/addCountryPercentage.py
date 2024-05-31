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
index = os.environ.get("OPENSE_ANALYTICS_INDEX")
url = f"{host}/{index}/_search"
awsauth = AWSV4SignerAuth(credentials, region, service)
# firma de aacceso a opensearch
opense = OpenSearch(
    hosts=[{'host': "search-portaty-opense-f2pru5qxiz73a53c7fstafplnu.us-east-1.es.amazonaws.com", 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20
)


def get_country(data=[], total=0):
    dataCountry = []
    if total <= 0:
        return dataCountry
    for item in data:
        percentage = (item["doc_count"] * 100)/total
        dataCountry.append({"pais": item["key"],
                            "numero_de_visitas": item["doc_count"], "porcentaje_visitas": percentage})
    return dataCountry


def get_city(data=[], total=0):
    dataCity = []
    if total <= 0:
        return dataCity
    for x in data:
        for j in x["city"]["buckets"]:
            dataCity.append({"pais": x["key"], "ciudad": j["key"],
                             "numero_de_visitas": j["doc_count"], "porcentaje_visitas": (j["doc_count"]*100)/total})
    return dataCity


def handler(event, context):
    params = event.get("queryStringParameters", {})
    businessID = params.get("businessID")
    userID = params.get("userID")

    if not businessID:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Error: No se ha proporcionado el businessID"}),
            "headers": {
                "Access-Control-Allow-Origin": '*'
            },
            "isBase64Encoded": False
        }
    if not userID:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Error: No se ha proporcionado el userID"}),
            "headers": {
                "Access-Control-Allow-Origin": '*'
            },
            "isBase64Encoded": False
        }
    query_country = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "eventname.keyword": "user_add_business"
                        }
                    },
                    {
                        "term": {
                            "businessid.keyword": str(businessID)
                        }
                    }
                ],
                "must_not": [
                    {
                        "term": {
                            "userid.keyword": {
                                "value": str(userID)
                            }
                        }
                    }
                ]
            }
        },
        "aggs": {
            "country": {
                "terms": {
                    "field": "country.keyword",
                    "order": {
                        "_count": "desc"
                    }
                },
                "aggs": {
                    "city": {
                        "terms": {
                            "field": "city.keyword",
                            "order": {
                                "_count": "desc"
                            }
                        }
                    }
                }
            }
        }
    }
    r = opense.search(
        body=query_country,
        index=index
    )
    total = r["hits"]["total"]["value"]
    data = r["aggregations"]["country"]["buckets"]
    dataCountry = get_country(data, total)

    dataCity = get_city(data, total)

    print("RESPUESTA DE BUSQUEDA: ", dataCity)
    body = json.dumps({"message": f'Total de Personas que agregaron de favorito tu negocio por pais-ciudad, obtenido con exito.',
                       "data": {
                           "city": dataCity,
                           "country": dataCountry
                       }})
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
