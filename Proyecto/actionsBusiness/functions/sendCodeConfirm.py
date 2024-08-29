import json
from email.message import EmailMessage
import smtplib
import boto3
import hashlib
import random
from PIL import Image
from io import BytesIO

from datetime import datetime, timezone
import os
from boto3.dynamodb.types import TypeSerializer
from decimal import Decimal


AWS_REGION = "us-east-1"
s3 = boto3.client("s3", region_name=AWS_REGION)
db = boto3.client("dynamodb", region_name=AWS_REGION)
bucketName = os.environ.get("S3_BUCKET_NAME")
tableNameDB = os.environ.get("TABLE_BUSINESS_NAME")
serializer = TypeSerializer()


def get_db_business(businessID):
    print("BUSINESSID:", businessID)
    response = db.get_item(
        TableName=tableNameDB,
        Key={'id': {'S': businessID}}
    )
    return response


def update_db_business(businessID, code):
    print("BUSINESSID:", businessID)
    # Actualizar el campo emailConfirmationCode en la base de datos
    response = db.update_item(
        TableName=tableNameDB,
        Key={'id': {'S': businessID}},
        UpdateExpression='SET emailConfirmationCode = :c',
        ExpressionAttributeValues={':c': {'S': code}}
    )
    return response


def handler(event, context):
    body = json.loads(event['body'])
    print("BODY:", body)
    businessID = body.get("businessID", "")
    # Obtener datos de tabla
    response = get_db_business(businessID)
    print("BUSINESS: ", response)
    # Extraer los datos del negocio
    business = response['Item']
    email = business['email']['S']
    name = business['name']['S']
    # Generar un código de confirmación de 6 dígitos
    code = str(random.randint(100000, 999999))

    # Encriptar el código de confirmación
    encrypted_code = hashlib.sha256(code.encode()).hexdigest()
    print("CODIGO ENCRY: ", encrypted_code)
    # GUARDAR CODIGO EN CORREO
    update_db_business(businessID, encrypted_code)
    # ENVIAR CONDIGO A EMAIL
    try:
        sendEmail(email, name, code)
        response = {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "message": "Función Lambda ejecutada correctamente"
            })
        }
    except Exception as e:
        print("Error al enviar el correo electrónico:", str(e))
        response = {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "message": "Error al enviar el correo electrónico",
                "error": str(e)
            })
        }

    return response


def sendEmail(des, name, code):
    remitente = "no-responder@portaty.com"
    destinatario = des
    mensaje = f"Codigo de confirmacion {code}"
    subject = f"Codigo de confirmacion  del correo de tu negocio {name}"
    # configuracion
    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = subject
    email.set_content(mensaje)
    # Ajusta el puerto según la configuración de tu proveedor
    smtp = smtplib.SMTP_SSL("smtp.zoho.com", 465)
    # Utiliza variables de entorno o un sistema de gestión de secretos
    smtp.login(remitente, "HdCmgawsJZbN")
    smtp.sendmail(remitente, destinatario, email.as_string())
    smtp.quit()
