import json
import boto3
from PIL import Image
from io import BytesIO
import base64
import random
from datetime import datetime, timezone
import os
import uuid


def createBusiness(event, context):
    body = json.loads(event['body'])
    print("BODY:", body)
    try:
        # Primero obtenemos todos los datos que necesitaremos para la creacion de la imagen en el bucket y end dynamodb
        # datos para la imagen
        identityid = body.get("identityid")
        image = body.get("image")
        key = body.get("key")
        # datos para la base de datos
        


        # response = {
        # "statusCode": 200,
        # "body": json.dumps(body)
        # }

        return response
    except Exception as e:
        return {
        "statusCode": 500,
        "error": json.dumps(e)
        }

   





