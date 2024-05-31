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
    query_gender = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "eventname.keyword": "user_viewed_business"
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
            "gender": {
                "terms": {
                    "field": "gender.keyword",
                    "order": {
                        "_count": "desc"
                    }
                }
            }
        }
    }
    r = opense.search(
        body=query_gender,
        index=index
    )
    total = r["hits"]["total"]["value"]
    data = r["aggregations"]["gender"]["buckets"]
    dataResult = []
    # Crear un diccionario con todos los géneros posibles y un conteo inicial de cero
    gender_counts = {"Male": 0, "Female": 0, "Others": 0}

    # Actualizar el conteo para los géneros que están presentes en los resultados de la consulta
    for item in data:
        if item["key"] in ["Masculino", "Male"]:
            gender_counts["Male"] += item["doc_count"]
        elif item["key"] in ["Femenino", "Female"]:
            gender_counts["Female"] += item["doc_count"]
        elif item["key"] in ["Otros", "Others"]:
            gender_counts["Others"] += item["doc_count"]

    dataResult = []
    for gender, count in gender_counts.items():
        percentage = 0
        if total > 0:
            percentage = (count * 100)/total
        dataResult.append({"genero": gender,
                           "cantidad_visitas": count, "porcentaje_visitas": percentage})

    print("RESPUESTA DE BUSQUEDA: ", dataResult)
    body = json.dumps({"message": f'Vistas por Genero obtenidas con exito',
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
