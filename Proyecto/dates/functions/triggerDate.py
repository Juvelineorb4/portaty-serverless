import boto3
import os
import json
import requests
from datetime import datetime, timedelta, timezone
from dateutil import parser

client = boto3.client('sns')
TOPIC_SEND_NOTIFICATION = os.environ.get("TOPIC_SEND_NOTIFICATION")
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

print("TOPIC_SEND_NOTIFICATION_ARN:", TOPIC_SEND_NOTIFICATION)

# Mapeo de días y meses en español
dias_semana = {
    'Monday': 'lunes',
    'Tuesday': 'martes',
    'Wednesday': 'miércoles',
    'Thursday': 'jueves',
    'Friday': 'viernes',
    'Saturday': 'sábado',
    'Sunday': 'domingo'
}

meses_ano = {
    'January': 'enero',
    'February': 'febrero',
    'March': 'marzo',
    'April': 'abril',
    'May': 'mayo',
    'June': 'junio',
    'July': 'julio',
    'August': 'agosto',
    'September': 'septiembre',
    'October': 'octubre',
    'November': 'noviembre',
    'December': 'diciembre'
}

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

def human_readable_date(iso_date):
    # Parsear la fecha ISO a un objeto datetime aware (con zona horaria)
    appointment_datetime = parser.isoparse(iso_date).date()  # Nos quedamos solo con la fecha (día, mes, año)
    # Obtener la fecha y hora actual en UTC, pero solo la fecha (sin horas ni minutos)
    now = datetime.now(timezone.utc).date()

    # Calcular la diferencia en días entre la fecha actual y la fecha de la cita
    diff_days = (appointment_datetime - now).days
    print("DIFERENCIA DE DÍAS: ", diff_days)
    
    # Traducir el día de la semana y mes al español
    day_in_spanish = dias_semana[appointment_datetime.strftime("%A")]
    month_in_spanish = meses_ano[appointment_datetime.strftime("%B")]

    # Obtener el día de la cita en formato humano
    if diff_days == 0:  # Hoy
        human_day = "hoy"
    elif diff_days == 1:  # Mañana
        human_day = "mañana"
    elif diff_days < 7:  # Dentro de la semana (martes, miércoles, etc.)
        human_day = f"este {day_in_spanish}"  # Obtiene el día de la semana
    else:  # Fecha futura
        human_day = f"el {appointment_datetime.strftime('%d')} de {month_in_spanish}"  # Formato "el 21 de octubre"

    # Obtener la hora de la cita en formato 12 horas
    human_time = parser.isoparse(iso_date).strftime("%I:%M %p")
    return f"{human_day} a las {human_time}"

def handler(event, context):
    try:
        if event.get('Records') and event['Records'][0].get('eventSource') == 'aws:dynamodb':
            for record in event['Records']:
                print("RECORD: ", record)
                eventName = record["eventName"]
                newImage = record["dynamodb"].get("NewImage")
                
                print("eventName:", eventName)
                print("newImage: ", newImage)

                if newImage and eventName == "INSERT":
                    business_id = newImage['businessID']['S']
                    appointment_date = newImage['date']['S']  # Extraemos la fecha de la cita en formato ISO
                    

                    # Convertimos la fecha de la cita a un formato más humano
                    human_readable_appointment = human_readable_date(appointment_date)

                    # Obtener el userID, nombre de negocios (name), y owner del negocio a través de la API de AppSync
                    business_data = get_business(business_id)
                    if not business_data:
                        print(f"No se encontró información del negocio con ID: {business_id}")
                        return

                    # Extraer los datos necesarios
                    business_name = business_data['getBusiness']['name']
                    user_id = business_data.get('getBusiness', {}).get("userID", None)
                    owner = business_data['getBusiness']['owner']
                    email = business_data['getBusiness']['email']
                    print(f"Negocio: {business_name}, UserID: {user_id}, Owner: {owner}, Fecha de la cita: {human_readable_appointment}")
                    
                    # Obtener los métodos de notificación
                    notification_methods = [method['S'] for method in newImage['notificationMethod']['L']]
                    print("Notification methods:", notification_methods)
                  
                    # Enviar mensaje para correo electrónico
                    if 'EMAIL' in notification_methods:
                        if email == "":
                            email = business_data.get("getBusiness").get("user").get("email")
                            print("EMAIL DE USUARIO: ", email)
                        email_message = json.dumps({
                            "subject": "Nueva cita programada para tu negocio",
                            "body": f"Se ha programado una nueva cita para tu negocio {business_name}. La cita es {human_readable_appointment}.",
                            "email": email  # Correo del negocio
                        })
                        print("EMAI SEND: ", email_message)
                        send_topic(email_message, subject="Email Notification", channel="email")

                    # Enviar notificación push (solo si se obtuvo el userID)
                    if 'PUSH_NOTIFICATION' in notification_methods and user_id:
                        user_notification_message = json.dumps({
                            "userID": user_id,
                            "title": "Nueva cita programada para tu negocio",
                            "message": f"Tienes una nueva cita programada para tu negocio {business_name} {human_readable_appointment}.",
                            "type": "date",
                            "data": None,
                            "owner": owner
                        })
                        send_topic(user_notification_message, subject="User Notification DB", channel="user_notification")
                    if newImage.get("userToken", {}).get("S", None):
                        notification_message = json.dumps({
                                "to": newImage.get("userToken", {}).get("S", None),
                                "title": f"Tu cita fue notificada al negocio {business_name} !",
                                "body": f"Tu sida ya fue agendada y notificada al negocio {business_name} {human_readable_appointment}.",
                                'data': {
                                    'data': {
                                        'type': "date"
                                    }
                                }
                            })
                            
                            # Enviar la notificación
                        send_topic(notification_message, subject="Push Notification", channel="push_notification")
                    print("Todos los mensajes han sido enviados correctamente.")
                    return "Mensajes enviados exitosamente."
                else:
                    print('No se encontró un NewImage en el evento o no es una inserción.')
                    return 'No se encontró un NewImage en el evento o no es una inserción.'
        else:
            print('El eventSource no es "aws:dynamodb".')
            return 'El eventSource no es "aws:dynamodb".'
    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e


# Función para obtener los datos del negocio desde AppSync usando GraphQL
def get_business(id):
    query = """
    query GetBusiness($id: ID!) {
        getBusiness(id: $id) {
            id
            userID
            user{
                id
                email
            }
            owner
            name
            email
            createdAt
            updatedAt
        }
    }
    """
    variables = {"id": id}
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
        if "errors" in response_data:
            print(f"Error en la consulta de GraphQL: {response_data['errors']}")
            return None
        print("get_business", response_data["data"])
        return response_data["data"]
    except Exception as e:
        print(f"Error al consultar AppSync: {e}")
        return None
