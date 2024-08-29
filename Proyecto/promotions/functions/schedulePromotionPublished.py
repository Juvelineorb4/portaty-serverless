import boto3
import json
import os
from datetime import datetime, timedelta, timezone
import base64
import requests
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")
QUEUE_URL = os.environ.get("QUEUE_PROMOTION_PUBLISDHED_URL")
AWS_REGION = os.environ.get("AWS_REGION")
sqs = boto3.client('sqs')
# s3 = boto3.client("s3", region_name=AWS_REGION)
# bucketName = os.environ.get("S3_BUCKET_NAME")


listBusinessPromotions = """
        query listBusinessPromotions(
                $filter: ModelBusinessPromotionFilterInput
                $limit: Int
                $nextToken: String
            ) {
            listBusinessPromotions( 
                filter: $filter
                limit: $limit
                nextToken: $nextToken
            ) {
               items{
                id
                title
                dateInitial
               }
               nextToken
               
            }
        }
    """

def send_message(msg):
    response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=msg
    )
    return response


def get_today_range():
    # Obtener la fecha actual en UTC con zona horaria
    fecha_actual = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    fecha_actual = fecha_actual - timedelta(days=1)
    fecha_actual_str = fecha_actual.strftime('%Y-%m-%dT%H:%M:%SZ')
   
    # Obtener el siguiente día y restarle un segundo
    final_dia = (fecha_actual + timedelta(days=1)) - timedelta(seconds=1)
    final_dia_str = final_dia.strftime('%Y-%m-%dT%H:%M:%SZ')

    
    return fecha_actual_str, final_dia_str


def get_promotion_inreview_today(today, today_final):
    promotions = []
    next_token = None

    while True:
        # variables = {
        #     "filter": {
        #             "status": {"eq": "PUBLISHED"},
        #     },
        #     "nextToken": next_token
        # }
        variables = {
            "filter": {
                "and": [
                    {"status": {"eq": "PUBLISHED"}},
                    {"dateFinal": {"between": [today, today_final]}}
                ]
            },
            "nextToken": next_token
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": appsync_api_key
        }

        response = requests.post(
            appsync_api_url,
            json={"query": listBusinessPromotions, "variables": variables},
            headers=headers,
        )
        data = response.json()["data"]["listBusinessPromotions"]
        promotions.extend(data["items"])

        next_token = data.get("nextToken")
        if not next_token:
            break

    return promotions

def handler(event, context):
    # obtener el inicio y final del dia para el rango de fechas en el filtro
    date_today, date_today_final = get_today_range()
    
    try:
        print("Fecha actual:", date_today)
        print("Final del día:", date_today_final)
        
       # buscar las promociones de hoy en inreview
        promotions = get_promotion_inreview_today(date_today, date_today_final)
        print("INFO ENCONTRADA: ", promotions)
        
        # Crear un arreglo con todos los IDs de las promociones
        promotion_ids = [promotion["id"] for promotion in promotions]
        print("IDs de promociones:", promotion_ids)
        
        
       # Enviar el arreglo de IDs
        send_message(json.dumps(promotion_ids))

        print("Promoción enviada con éxito, se está procesando!")
        return "Promoción enviada con éxito, se está procesando!"
    except Exception as e:
        message_error = str(e)
        print("Error al crear la promoción:", message_error)
