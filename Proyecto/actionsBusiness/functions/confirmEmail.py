import json
from email.message import EmailMessage
import smtplib
import boto3
import hashlib

import os
from boto3.dynamodb.types import TypeSerializer


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


def update_db_business(businessID):
    print("BUSINESSID:", businessID)
    # Actualizar el campo emailConfirmationCode en la base de datos
    response = db.update_item(
        TableName=tableNameDB,
        Key={'id': {'S': businessID}},
        UpdateExpression='SET emailVerified = :v',
        ExpressionAttributeValues={':v': {'BOOL': True}}
    )
    return response


def handler(event, context):
    body = json.loads(event['body'])
    print("BODY:", body)
    businessID = body.get("businessID", "")
    code = body.get("code", "")

    # Encriptar el código proporcionado por el usuario
    encrypted_code = hashlib.sha256(code.encode()).hexdigest()

    # Obtener el negocio de la base de datos
    response = get_db_business(businessID)
    business = response['Item']
    print("BUSINESS: ", business)
    # Comparar los códigos
    if business['emailConfirmationCode']['S'] == encrypted_code:
        # Marcar el negocio como verificado
        update_db_business(businessID)

        return {'statusCode': 200,  "body": json.dumps({
                "success": True,
                "message": "Código de confirmación correcto"
                })}
    else:
        return {'statusCode': 400, "body": json.dumps({
                "success": False,
                "message": 'Código de confirmación incorrecto',

                })}


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
