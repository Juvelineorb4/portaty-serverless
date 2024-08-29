import json
import os
import boto3
from datetime import datetime

# Variables 
region = os.environ.get("AWS_REGION")
cognito = boto3.client('cognito-idp', region_name=region)
user_pool_id = os.environ.get("USER_POOL_ID")

def handler(event, context):
    print("EVENTO: ", event)
    params = event.get("queryStringParameters", {})
    print("PARAMS: ", params)

        
    try:


        return {
            'statusCode': 200,
            "body": json.dumps({
                "success": True,
                "message": "Mensajes Enviados con exito!",
            })
        }
    except Exception as e:
        error_message = str(e)
        return {'statusCode': 500, "body": json.dumps({
            "success": False,
            "message": "Error al obtener los usuarios",
            "error": error_message
        })}

# Ejemplo de uso:
# Suponiendo que esta función se invoca a través de un evento API Gateway con queryStringParameters 'limit' y opcionalmente 'nextToken'
