import boto3
import json
import os
import requests

# Variables de entorno y configuración
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

def handler(event, context):
    try:
        # Procesa cada registro del evento
        for record in event['Records']:
            print("RECORD: ", record)
            message_body = record['body']
            print(f'Mensaje recibido: {message_body}')
            
            body_json = json.loads(message_body)
            
            # Obtener los datos necesarios para la notificación
            userID = body_json.get('userID')
            title = body_json.get('title')
            message = body_json.get('message')
            owner = body_json.get('owner', userID)  # Si no se proporciona 'owner', usa 'userID' como predeterminado
            notification_type = body_json.get('type', 'general')  # Tipo de notificación (por defecto 'general')
            data = body_json.get('data', '{}')  # Datos adicionales (por defecto cadena vacía)

            if not userID or not title or not message:
                print("Error: Faltan datos requeridos para crear la notificación (userID, title, message).")
                continue

            # Crear el objeto de notificación para insertar en la tabla
            notification_data = {
                "userID": userID,
                "title": title,
                "message": message,
                "type": notification_type,
                "data": data,
                "owner": owner
            }
            print(f"Datos de la notificación a crear: {notification_data}")

            # Llamar a la función para crear la notificación en AppSync
            create_notification_user(notification_data)
        print('Notificaciones creadas exitosamente')
        return {
            'statusCode': 200,
            'body': json.dumps('Notificaciones creadas exitosamente')
        }

    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e


def create_notification_user(data):
    """
    Función para crear una notificación de usuario en DynamoDB usando la API de AppSync.
    """
    query = """
        mutation CreateUserNotification($input: CreateUserNotificationInput!) {
            createUserNotification(input: $input) {
                id
                userID
                title
                message
                type
                data
                owner
                createdAt
                updatedAt
                __typename
            }
        }
    """
    
    variables = {
        "input": data
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    try:
        response = requests.post(
            appsync_api_url,
            json={"query": query, "variables": variables},
            headers=headers
        )
        response_data = response.json()
        if 'errors' in response_data:
            print(f"Error al crear la notificación: {response_data['errors']}")
        else:
            print(f"Notificación creada: {response_data['data']}")
    except Exception as e:
        print(f"Error al enviar la solicitud de AppSync: {str(e)}")
