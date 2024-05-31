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
    query_age = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "eventname.keyword": "user_remove_business"
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
            "age_ranges": {
                "range": {
                    "script": {
                        "source": """
      LocalDate currentDate = Instant.ofEpochMilli(new Date().getTime()).atZone(ZoneId.of('Z')).toLocalDate();
      LocalDate birthDate = Instant.ofEpochMilli(doc['birthdate'].value.getMillis()).atZone(ZoneId.of('Z')).toLocalDate();
      long years = ChronoUnit.YEARS.between(birthDate, currentDate);
      return years;
    """,
                        "lang": "painless"
                    },
                    "ranges": [
                        {"from": 18, "to": 26, "key": "18-25"},
                        {"from": 26, "to": 31, "key": "26-30"},
                        {"from": 31, "to": 41, "key": "31-40"},
                        {"from": 41, "to": 51, "key": "41-50"},
                        {"from": 51, "key": "50+"}
                    ]
                }
            }
        }
    }
    r = opense.search(
        body=query_age,
        index=index
    )
    total = r["hits"]["total"]["value"]
    data = r["aggregations"]["age_ranges"]["buckets"]
    dataResult = []
    for item in data:
        percentage = 0
        if total > 0:
            percentage = (item["doc_count"]*100)/total
        dataResult.append({"rango_edad": item["key"], "cantidad": item["doc_count"],
                           "porcentaje": percentage})

    print("RESPUESTA DE BUSQUEDA: ", dataResult)
    body = json.dumps({"message": f'Total de Personas que quitaron de favorito tu negocio por rango de edad, obtenido con exito.',
                       "data": dataResult})
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
