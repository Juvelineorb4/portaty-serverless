import boto3
import json
import os
import datetime
import base64
import requests
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")
QUEUE_URL = os.environ.get("QUEUE_PROMOTION_URL")
AWS_REGION = os.environ.get("AWS_REGION")
sqs = boto3.client('sqs')
s3 = boto3.client("s3", region_name=AWS_REGION)
bucketName = os.environ.get("S3_BUCKET_NAME")


def send_message(msg):
    response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=msg
    )

def validate_date(date_str):
    print("VALIDAR DATE: ", date_str)
    try:
        # Intentamos convertir la fecha con fracciones de segundo
        datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        return True
    except ValueError:
        try:
            # Si falla, intentamos sin fracciones de segundo
            datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
            return True
        except ValueError:
            return False

def extract_date(date_str):
    # Extrae solo la parte de la fecha (sin la hora)
    return date_str[:10]

def validate_field(field_value):
    # Verifica si el campo no está vacío o es None
    return field_value is not None and field_value.strip() != ""

def save_image_to_s3(image_data, file_name):
    try:
        s3.put_object(Body=image_data, Bucket=bucketName, Key=file_name)
        return True
    except Exception as e:
        print(f"Error al guardar la imagen en S3: {str(e)}")
        return False
def is_existing_file_s3(path):
    try:
       
        return True
    except Exception as e:
        print(f"Error al guardar la imagen en S3: {str(e)}")
        return False



def get_promotion_id(id):
    # Definir la mutación de GraphQL para obtener usuarios
    query = """
        query GetBusinessPromotion($id: ID!) {
            getBusinessPromotion(id: $id) {
                id
                userID
                businessID
                title
                dateInitial
                dateFinal
                image
            }
        }
    """

    variables = {"id": id}

    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    response = requests.post(
        appsync_api_url,
        json={"query": query, "variables": variables},
        headers=headers,
    )

    return response.json()["data"]["getBusinessPromotion"]



def handler(event, context):
    
    
  
 
    
  


    # Validamos si la promocion existe y si el url existe la imagen 
    # No id presente 
    # validamos campos vacios 
    # guardamos imagen en s3 
    # enviamos informacion a la cola
    
    
    # Recibir el evento
    print("EVENTO: ", event)
    # Obtener la fecha y hora actual
    now = datetime.datetime.now()
    # Recibir Body 
    body = event.get("body", None)
    if not body:
        print("ERROR:", "body no aceptado")
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "Error al enviar promoción",
                "error": "El cuerpo (body) no puede estar vacío"
            })
        }

    try:
        # PArsear Body
        data = json.loads(body)
        if not data.get("data"):
            print("ERROR:", "data no aceptada")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al enviar promoción",
                    "error": "Data es undefined"
                })
            }
        # Obtener campos de Body
        promotion_id = data["data"].get("promotionID")
        date_initial = data["data"].get("dateInitial")
        date_final = data["data"].get("dateFinal")
        title = data["data"].get("title")
        image = data["data"].get("image")
        business_id = data["data"].get("businessID")
        identity_id = data["data"].get("identityID")
        user_id = data["data"].get("userID")
        
        # Si promotion_id esta presente
        if validate_field(promotion_id):
            # buscamos la promocion 
            promotion = get_promotion_id(promotion_id)
            # sustituimos valores por los encontrados
            title = promotion.get("title")
            image = promotion.get("image")
            business_id = promotion.get("businessID")
            user_id = promotion.get("userID")
        
        # Valida los campos para que no esten vacios los que se necesitan
        if not validate_field(title) or not validate_field(image) or not validate_field(business_id) or not (validate_field(identity_id) or validate_field(promotion_id) ) or not validate_field(user_id):
            print("ERROR:", "campos vacíos")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al enviar promoción",
                    "error": "Los campos title, image y userTableID no pueden estar vacíos"
                })
            }
        # validamos que los campos de fechas sean los adecuados
        if not validate_date(date_initial) or not validate_date(date_final):
            print("ERROR:", "fechas inválidas")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al enviar promoción",
                    "error": "Fechas inválidas (deben estar en formato ISO 8601)"
                })
            }

        # Convierte las fechas a objetos datetime
        initial_date_obj = datetime.datetime.strptime(extract_date(date_initial), '%Y-%m-%d')
        final_date_obj = datetime.datetime.strptime(extract_date(date_final), '%Y-%m-%d')
        now_date_obj = datetime.datetime.strptime(extract_date(str(now)), '%Y-%m-%d')

        # Verifica las condiciones de las fechas
        if initial_date_obj > final_date_obj:
            print("ERROR:", "fecha inicial mayor que fecha final")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al enviar promoción",
                    "error": "Fecha inicial no puede ser mayor que fecha final"
                })
            }

        if initial_date_obj < now_date_obj or final_date_obj < now_date_obj:
            print("ERROR:", "fechas menores que fecha actual")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al enviar promoción",
                    "error": "Fechas deben ser mayores o iguales a la fecha actual"
                })
            }
        # si existe promotion_id no se guarda nada en s3
        if not validate_field(promotion_id):
            # Guardar la imagen en S3
            image_data = base64.b64decode(image)
            file_name = f"promotions/promotion_{business_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            file_path = f"protected/{identity_id}/business/{business_id}/{file_name}"
            image_url = f"https://{bucketName}.s3.amazonaws.com/{file_path}"
            print(file_path)
            if not save_image_to_s3(image_data, file_path):
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        "success": False,
                        "message": "Error al enviar promoción",
                        "error": "Error al guardar la imagen en S3"
                    })
                }
        else:
            # se guarda en image url el image que se obtiene de la consulta de promotion
            image_url= image

           

        # ENviar params par ala creaion de registro en dDB
        params = {
            "userID": user_id,
            "businessID": business_id,
            "title": title,
            "dateInitial": extract_date(date_initial),
            "dateFinal": extract_date(date_final),
            "image": image_url,
        }
        print("PARAMS SQS: ", params)
        # Enviar mensaje a la cola SQS
        send_message(json.dumps(params))

        return {
            "statusCode": 200,
            "body": json.dumps({"success": True, "message": "Promoción enviada con éxito, se está procesando!"})
        }
    except Exception as e:
        message_error = str(e)
        print("Error al crear la promoción:", message_error)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al enviar promoción",
                "error": message_error
            })
        }
