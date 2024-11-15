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
index_users = os.environ.get("OPENSE_INDEX_USERS")
url_users = f"{host}/{index_users}/_search"

# Función Lambda principal
def handler(event, context):
    try:
        # Construcción de la consulta para usuarios actualizados hoy
        query = {
            "size": 0,  # No necesitamos obtener documentos, solo el conteo
            "query": {
                "range": {
                    "updatedAt": {
                        "gte": "now/d",  # Usuarios actualizados desde el comienzo del día actual
                        "lt": "now+1d/d"  # Hasta el comienzo del próximo día
                    }
                }
            }
        }

        # Realizar la consulta en OpenSearch para obtener el conteo
        headers = {"Content-Type": "application/json"}
        r = requests.get(url_users, auth=awsauth, headers=headers, data=json.dumps(query))

        # Procesar la respuesta
        response_data = json.loads(r.text)
        today_users_count = response_data["hits"]["total"]["value"]

        # Retornar éxito con el total de usuarios actualizados hoy
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "today_count": today_users_count
            })
        }

    except Exception as e:
        # Manejo de error
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error en la búsqueda de usuarios actualizados hoy.",
                "error": str(e)
            })
        }
