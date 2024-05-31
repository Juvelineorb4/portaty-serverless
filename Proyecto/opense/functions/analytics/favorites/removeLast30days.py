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
    query_last_30_days = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {
                        "term": {
                            "eventname.keyword": "user_remove_business"
                        }
                    },
                    {
                        "term": {
                            "businessid.keyword": {
                                "value": str(businessID)
                            }
                        }
                    },
                    {
                        "range": {
                            "timestamp": {
                                "gte": "now-29d/d",
                                "lte": "now/d"
                            }
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
            "last_30_days": {
                "date_histogram": {
                    "field": "timestamp",
                    "interval": "day",
                    "format": "yyyy-MM-dd",
                    "min_doc_count": 0,
                    "extended_bounds": {
                        "min": "now-29d/d",
                        "max": "now/d"
                    }
                }
            }
        }
    }
    r = opense.search(
        body=query_last_30_days,
        index=index
    )
    data = r["aggregations"]["last_30_days"]["buckets"]
    dataResult = {item["key_as_string"]: item["doc_count"] for item in data}
    print("RESPUESTA DE BUSQUEDA: ", dataResult)
    body = json.dumps({"message": f'Personas que quitaron de favorito tu negocio los ultimos 30 dias obtenidas con exito',
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
