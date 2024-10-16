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
                    title_notification = newImage.get("title").get("S","")
                    print("TITLE:", title_notification)
                    message_notification = newImage.get("message").get("S","")
                    print("MEssage:", message_notification)
                    user_id = newImage.get('userID').get("S","")
                    print("USERID:", user_id)
                    type_notification = newImage.get('userID').get("S","")
                    # Extraer el campo 'extra' de 'data' que contiene la información JSON
                    data_json = json.loads(newImage['data']['S'])
                    print("DATA JSON: ", data_json)
                    extra = data_json.get('extra', {})
                    print("extra ", extra)
                    promotion_id = extra.get('id', '')
                    print("promotion_id", promotion_id)
                    user_id_extra = extra.get('userID', '')
                    
                    # Paso 1: Buscar el notification token del usuario mediante userID
                    user_token, user_email = get_user_token(user_id)

                    if user_token:
                        # Paso 2: Enviar push notification
                        msg = {
                                'to': user_token,
                                'title': title_notification,
                                'body': message_notification,
                                'data': {
                                    'data': {
                                        'type': "promotion",
                                        'promotionID': promotion_id
                                    }
                                }
                            }
                        send_push_notification(msg)
                        print("Notificación enviada correctamente al propietario.")
        
                 
                    print( 'Trigger Notification Promotion exitoso')
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
      cognitoID
      name
      lastName
      email
      identityID
      gender
      notificationToken
      owner
      createdAt
      updatedAt
      __typename
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
        return None

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


