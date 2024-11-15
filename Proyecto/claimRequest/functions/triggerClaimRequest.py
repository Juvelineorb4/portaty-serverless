import boto3
import os
import json
import requests

client = boto3.client('sns')
TOPIC_SEND_NOTIFICATION = os.environ.get("TOPIC_SEND_NOTIFICATION")
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

print("TOPIC_SEND_NOTIFICATION_ARN:", TOPIC_SEND_NOTIFICATION)




def send_topic(msg, subject, channel):
    try:
        result = client.publish(
            TopicArn=TOPIC_SEND_NOTIFICATION,
            Message=msg,
            Subject=subject,
            MessageAttributes={
                'channel': {
                    'DataType': 'String',
                    'StringValue': channel
                }
            }
        )
        print(f"Message sent to {channel}: {result}")
        return result
    except Exception as e:
        print(f"Error sending message: {e}")
        raise e


def handler(event, context):
    try:
        if event.get('Records') and event['Records'][0].get('eventSource') == 'aws:dynamodb':
            for record in event['Records']:
                print("RECORD: ", record)
                eventName = record["eventName"]
                newImage = record["dynamodb"].get("NewImage")
                oldImage = record["dynamodb"].get("OldImage", None)
                print("eventName:", eventName)
                print("newImage: ", newImage)

                if newImage and eventName == "INSERT" and newImage["status"]["S"] == "PENDING":
                    user_id = newImage.get("userID", {}).get("S", None)
                    
                    # Validar si el userID existe
                    if not user_id:
                        print("El userID no existe en el evento.")
                        return "El userID no existe en el evento."

                   # Paso 1: Buscar el notification token del usuario mediante userID
                    user_token, user_email = get_user(user_id)
                    if not user_token and user_email:
                        print(f"No se encontró ningun parametro para notificarle al usuario userID: {user_id}.")
                        return f"No se encontró ningun parametro para notificarle al usuario userID: {user_id}."

                    if user_token:
                            notification_message = json.dumps({
                                "to": user_token,
                                "title": "Solicitud de reclamo de negocio registrada con éxito",
                                "body": "Solicitud registrada con éxito, estaremos en contacto",
                                'data': {
                                    'data': {
                                        'type': "claimRequest"
                                    }
                                }
                            })
                            
                            # Enviar la notificación
                            send_topic(notification_message, subject="Push Notification", channel="push_notification")
                            print("PUSH NOTIFICATION PENDING ENVIANDO CON EXITO")
                    if user_email:
                            email_message = json.dumps({
                            "subject": "Solicitud de reclamo de negocio registrada con éxito",
                            "body": f"Solicitud registrada con éxito, estaremos en contacto.",
                            "email": user_email  # Correo del negocio
                            })
                            send_topic(email_message, subject="Email Notification", channel="email")
                            print("EMAIL PENDING ENVIANDO CON EXITO")
                    print("Mensaje de reclamo PENDING enviada exitosamente.")
                    return "Mensaje de reclamo PENDING enviada exitosamente."
                elif newImage and oldImage and eventName == "MODIFY" and oldImage["status"]["S"] == "PENDING":
                    if newImage["status"]["S"] == "ACCEPTED":
                        user_id = newImage.get("userID", {}).get("S", None)
                    
                        # Validar si el userID existe
                        if not user_id:
                            print("El userID no existe en el evento.")
                            return "El userID no existe en el evento."

                        # Paso 1: Buscar el notification token del usuario mediante userID
                        user_token, user_email = get_user(user_id)
                        if not user_token and user_email:
                            print(f"No se encontró ningun parametro para notificarle al usuario userID: {user_id}.")
                            return f"No se encontró ningun parametro para notificarle al usuario userID: {user_id}."
                        if user_token:
                            notification_message = json.dumps({
                                "to": user_token,
                                "title": "Solicitud de reclamo de negocio aceptada con éxito",
                                "body": "Solicitud aceptada con éxito, el negocio que reclamaste se te fue asignado",
                                'data': {
                                    'data': {
                                        'type': "claimRequest"
                                    }
                                }
                            })
                            
                            # Enviar la notificación
                            send_topic(notification_message, subject="Push Notification", channel="push_notification")
                            print("PUSH NOTIFICATION ACCEPTED ENVIANDO CON EXITO")
                        if user_email:
                            email_message = json.dumps({
                            "subject": "Solicitud de reclamo de negocio aceptada con éxito",
                            "body": f"Solicitud aceptada con éxito, el negocio que reclamaste se te fue asignado.",
                            "email": user_email  # Correo del negocio
                            })
                            send_topic(email_message, subject="Email Notification", channel="email")
                            print("EMAIL ACCEPTED ENVIANDO CON EXITO")
                        print("Mensaje de reclamo PENDING enviada exitosamente.")
                        return "Mensaje de reclamo PENDING enviada exitosamente."
                    elif newImage["status"]["S"] == "REJECTED":
                        user_id = newImage.get("userID", {}).get("S", None)
                    
                        # Validar si el userID existe
                        if not user_id:
                            print("El userID no existe en el evento.")
                            return "El userID no existe en el evento."

                        # Paso 1: Buscar el notification token del usuario mediante userID
                        user_token, user_email = get_user(user_id)
                        if not user_token and user_email:
                            print(f"No se encontró ningun parametro para notificarle al usuario userID: {user_id}.")
                            return f"No se encontró ningun parametro para notificarle al usuario userID: {user_id}."
                        if user_token:
                            notification_message = json.dumps({
                                "to": user_token,
                                "title": "Solicitud de reclamo de negocio rechazada.",
                                "body": "Solicitud rechzada, comunicate con soporte tecnico",
                                'data': {
                                    'data': {
                                        'type': "claimRequest"
                                    }
                                }
                            })
                            
                            # Enviar la notificación
                            send_topic(notification_message, subject="Push Notification", channel="push_notification")
                            print("PUSH NOTIFICATION REJECTED ENVIANDO CON EXITO")
                        if user_email:
                            email_message = json.dumps({
                            "subject": "Solicitud de reclamo de negocio rechazada.",
                            "body": f"Solicitud rechzada, comunicate con soporte tecnico",
                            "email": user_email  # Correo del negocio
                            })
                            send_topic(email_message, subject="Email Notification", channel="email")
                            print("EMAIL REJECTED ENVIANDO CON EXITO")
                        print("Mensaje de reclamo REJECTED enviada exitosamente.")
                        return "Mensaje de reclamo REJECTED enviada exitosamente."
                else:
                    print('No se encontró un NewImage en el evento o no es una inserción.')
                    return 'No se encontró un NewImage en el evento o no es una inserción.'
        else:
            print('El eventSource no es "aws:dynamodb".')
            return 'El eventSource no es "aws:dynamodb".'
    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e


# Función para buscar el token de notificación del usuario usando userID
def get_user(user_id):
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
        user_token = data.get('data', {}).get('getUsers', {}).get('notificationToken', None)
        user_email = data.get('data', {}).get('getUsers', {}).get('email', None)
        return user_token, user_email
    else:
        print(f"Error al obtener el token de notificación del usuario: {response.text}")
        return None
