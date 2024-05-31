import json
import boto3
from PIL import Image
from io import BytesIO
import base64
import random
from datetime import datetime, timezone
import os
import uuid
from boto3.dynamodb.types import TypeSerializer
from decimal import Decimal


AWS_REGION = "us-east-1"
s3 = boto3.client("s3", region_name=AWS_REGION)
db = boto3.client("dynamodb", region_name=AWS_REGION)
bucketName = os.environ.get("S3_BUCKET_NAME")
tableNameDB= os.environ.get("TABLE_BUSINESS_NAME")
serializer = TypeSerializer()


def resize_image(image, size):
    img = Image.open(image)
    img.thumbnail(size)
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return buffered.getvalue()

def create_db_business(items):  
    print("A VER:", items)
    resultDB =db.put_item(
            TableName=tableNameDB,
            Item =items
        )
    return resultDB
    
def getDateIso():
    # Obtener la fecha y hora actual en formato UTC
    fechaUTC = datetime.now(timezone.utc)

    # Formatear la fecha en formato ISO 8601 hasta los minutos
    fechaIso8601 = fechaUTC.strftime('%Y-%m-%dT%H:%M') + 'Z'

    return fechaIso8601  
# Función para serializar un objeto Python a un objeto DynamoDB JSON
def serialize(item):
    # Convertir valores float a Decimal
    item = convert_float_to_decimal(item)
    # Serializar el objeto
    serialized_item = serializer.serialize(item)
    return item if 'M' not in serialized_item else serialized_item['M']

# Función para convertir valores float a Decimal
def convert_float_to_decimal(data):
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = convert_float_to_decimal(value)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            data[i] = convert_float_to_decimal(item)
    elif isinstance(data, float):
        data = Decimal(str(data))
    return data
def handler(event, context):
    body = json.loads(event['body'])
    print("BODY:", body)
    try:
        # Primero obtenemos todos los datos que necesitaremos para la creacion de la imagen en el bucket y end dynamodb
        data = body.get("dataBusiness", "")
        imageb64 = body.get("image", "")
        key = 0
        if(data == "" or imageb64 == ""):
            return {
            "statusCode": 400,
            "message": json.dumps({"error":"Variables vacias"})
            }
        identityid = data.get("identityID")
        description = body.get("description", "")
        businessid = str(uuid.uuid4())
        # despues de este punto tenemos toda la infromacion que necesitamos
        print("DATA: ", data)
        print("IMAGE: ", imageb64)
        print("identityID: ", identityid)
        print("Business ID: ", businessid)
        response = {
        "statusCode": 200,
        "body": json.dumps({"message": "functions ejecutada correctamente."})
        }
        # Decodifica la imagen base64
        imageData = ""
        originalData = ""
        if imageb64 != "" :  
            imageData = base64.b64decode(imageb64)
            # tenemos la imagen con el nuevo tama;o
            originalData = resize_image(BytesIO(imageData), (1024, 1024))
            print("IMAGEN ORIGINAL: ",originalData)
        # hacemos un condicional por si sigue siewndo vacio el original data
        # Guardamos la imagen en el storage 
        originalKey = f"protected/{identityid}/business/{businessid}/profile.jpg"
        thumbnailData = resize_image(BytesIO(originalData), (1024, 1024))
        thumbnailKey = f"protected/{identityid}/business/{businessid}/profile_thumbnail.jpg"
        s3.put_object(Body=originalData, Bucket=bucketName, Key=originalKey, ContentType="image/jpeg", Metadata={"businessid": businessid})
        s3.put_object(Body=thumbnailData, Bucket=bucketName, Key=thumbnailKey, ContentType="image/jpeg", Metadata={"businessid": businessid})
        # datos para guardar base de datos que crearemos 
        thumbnail = f"https://{bucketName}.s3.amazonaws.com/{thumbnailKey}"
        date = getDateIso()
        image = [{"key": key, "url":f"https://{bucketName}.s3.amazonaws.com/{originalKey}", "description": description, "businessid": businessid, "date": date }]
        data["id"] = businessid
        data["images"] = [json.dumps(objeto) for objeto in image]
        data["thumbnail"] = thumbnail
        data["createdAt"] =date
        data["createdAt"]= date
        data["updatedAt"]= date
        data["__typename"]= "Business"
        print("NEW DATA: ", data)
        # Serializar el objeto

        result = create_db_business(serialize(data))
        print("RESULT DB: ", result)
        
        response = {
        "statusCode": 200,
        "body": json.dumps({"message": "functions ejecutada correctamente."})
        }

        return response
        
  
    except Exception as e:
        return {
        "statusCode": 500,
        "error": json.dumps(e)
        }

