import boto3
import os
import json
import requests
from email.message import EmailMessage
import smtplib

# Configuración de AppSync y S3
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")
expo_push_url = "https://exp.host/--/api/v2/push/send"  # URL de Expo para enviar notificaciones
region = os.environ.get("AWS_REGION")
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

def handler(event, context):
    try:
        # Verifica si el eventSource es "aws:dynamodb"
        if event.get('Records') and event['Records'][0].get('eventSource') == 'aws:dynamodb':
            # Procesa cada registro del evento
            for record in event['Records']:
                print("RECORD: ", record)
                eventName = record["eventName"]
                newImage = record["dynamodb"].get("NewImage")
                print("eventName:", eventName)
                print("newImage: ", newImage)

                # Verifica si es un INSERT con NewImage
                if newImage and eventName == "INSERT":
                    # Validar y extraer los datos dinámicamente
                    title_notification = newImage.get("title", {}).get("S", "")
                    message_notification = newImage.get("message", {}).get("S", "")
                    user_id = newImage.get('userID', {}).get("S", "")
                    type_notification = newImage.get('type', {}).get("S", "general")  # Valor por defecto 'general'

                    print("TITLE:", title_notification)
                    print("MESSAGE:", message_notification)
                    print("USERID:", user_id)
                    print("TYPE:", type_notification)

                    # Verifica si el campo 'data' no es NULL y está presente
                    data_field = newImage.get('data', {})
                    if data_field and data_field.get("NULL") != True:
                        data_json = json.loads(data_field.get('S', '{}'))  # Si es NULL, no lo procesa
                    else:
                        data_json = {}

                    print("DATA JSON: ", data_json)
                    extra = data_json.get('extra', {})
                    promotion_id = extra.get('id', '')
                    user_id_extra = extra.get('userID', '')

                    # Paso 1: Buscar el notification token del usuario mediante userID
                    user_token, user_email = get_user_token(user_id)

                    if user_token:
                        # Construir el mensaje dinámicamente según el tipo de notificación
                        if type_notification == "promotion":
                            msg = {
                                'to': user_token,
                                'title': title_notification,
                                'body': message_notification,
                                'data': {
                                    'data': {
                                        'type': type_notification,
                                        'promotionID': promotion_id  # Agrega promotionID si es tipo promotion
                                    }
                                }
                            }
                        else:
                            msg = {
                                'to': user_token,
                                'title': title_notification,
                                'body': message_notification,
                                'data': {
                                    'data': {
                                        'type': type_notification  # Solo incluye el type si no es promotion
                                    }
                                }
                            }

                        # Paso 2: Enviar push notification
                        send_push_notification(msg)
                        print(f"Notificación enviada correctamente al usuario: {user_id}")
        
                    print('Trigger Notification Promotion exitoso')
                    return 'Trigger Notification Promotion exitoso'
                else:
                    print('No se encontró un NewImage en el evento o no es un INSERT.')
                    return 'No se encontró un NewImage en el evento o no es un INSERT.'

            print('No se procesaron registros en el evento.')
            return 'No se procesaron registros en el evento.'
        else:
            print('El eventSource no es "aws:dynamodb".')
            return 'El eventSource no es "aws:dynamodb".'
    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e

# Función para buscar el token de notificación del usuario usando userID
def get_user_token(user_id):
    query = """
    query GetUsers($id: ID!) {
        getUsers(id: $id) {
            id
            notificationToken
            email
        }
    }
    """
    variables = {
        "id": user_id
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    response = requests.post(appsync_api_url, json={"query": query, "variables": variables}, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print("RESULT GRAPHQL")
        user_token = data.get('data', {}).get('getUsers', {}).get('notificationToken', '')
        user_email = data.get('data', {}).get('getUsers', {}).get('email', '')
        return user_token, user_email
    else:
        print(f"Error al obtener el token de notificación del usuario: {response.text}")
        return None, None

# Función para enviar notificación push
def send_push_notification(push_message):
    try:
        response = requests.post(
            expo_push_url,
            json=push_message,
            headers={
                'Accept': 'application/json',
                'Accept-encoding': 'gzip, deflate',
                'Content-Type': 'application/json'
            }
        )

        response.raise_for_status()
        print("Push notification successfully sent.")
    except requests.exceptions.HTTPError as e:
        print(f"Error sending push notification: {str(e)}")
