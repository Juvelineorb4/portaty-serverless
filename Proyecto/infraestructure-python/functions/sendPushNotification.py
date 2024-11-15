import json
import boto3
import os
import requests

expo_push_url = "https://exp.host/--/api/v2/push/send"  # URL de Expo para enviar notificaciones

def handler(event, context):
    print("EVENT:", event)
    
    # Procesa cada mensaje recibido desde la cola SQS
    for record in event.get('Records', []):
        body = record.get('body')
        if body:
            try:
                # Carga el mensaje y extrae los datos necesarios
                json_body = json.loads(body)
                print("BODY:", json_body)
                
                # Extraer los datos necesarios para la notificación push
                to = json_body.get('to')  # Token de notificación del usuario
                title = json_body.get('title', 'Notificación')
                body_message = json_body.get('body', 'Tienes una nueva notificación')
                data = json_body.get('data', {})  # Datos adicionales

                # Construir el mensaje push
                push_message = {
                    "to": to,
                    "title": title,
                    "body": body_message,
                    "data": data
                }

                # Enviar la notificación push
                send_push_notification(push_message)

            except Exception as e:
                print(f"Error procesando el mensaje: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Mensajes procesados exitosamente')
    }


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
