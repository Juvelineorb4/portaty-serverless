import boto3
import requests
import os
import json
from datetime import datetime

AWS_REGION = os.environ.get("AWS_REGION")
db = boto3.client("dynamodb", region_name=AWS_REGION)

# nombre de tabla 
table_promotion = os.environ.get("TABLE_BUSINESS_PROMOTION_NAME")

def update_db_promotion(ids):
    # Actualizar el campo emailConfirmationCode en la base de datos
    responses = []
    for id in ids:
        response = db.update_item(
            TableName=table_promotion,
            Key={'id': {'S': id}},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': {'S': "EXPIRED"}}
        )
        responses.append(response)
    return responses

def handler(event, context):
    print("EVENTO: ", event)
    try:
        # Procesa cada registro del evento
        for record in event['Records']:
            print("RECORD: ", record)
            message_body = record['body']
            ids = json.loads(message_body)
            print(f'Mensaje recibido: {message_body}')
            print(ids)
            # ahora enviar el params que son los arreglos de ids que se le cambiara el status 
            responses = update_db_promotion(ids)
            print(f'Respuestas de actualización: {responses}')
        return 'Procesamiento exitoso'

    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e
