import boto3
import os
import requests
from datetime import datetime, timezone
from dateutil import parser
import json

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

# Función para actualizar el estado de la campaña a ACTIVE usando GraphQL
def update_coupons_campaign(id, status):
    mutation = """
    mutation UpdateCouponCampaign(
    $input: UpdateCouponCampaignInput!
    $condition: ModelCouponCampaignConditionInput
  ) {
    updateCouponCampaign(input: $input, condition: $condition) {
      id
      businessID
      status
    }
  }
    """
    variables = {"input": {
        "id": id,
        "status": status
    }}
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    try:
        response = requests.post(
            appsync_api_url,
            json={"query": mutation, "variables": variables},
            headers=headers
        )
        response_data = response.json()
        if "errors" in response_data:
            print(f"Error en la consulta de GraphQL: {response_data['errors']}")
            return None
        print("Update response:", response_data["data"])
        return response_data["data"]
    except Exception as e:
        print(f"Error al consultar AppSync: {e}")
        return None

# Función para obtener los datos del negocio desde AppSync usando GraphQL
def get_business(id):
    query = """
    query GetBusiness($id: ID!) {
        getBusiness(id: $id) {
            id
            userID
            user {
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
        print("Business data:", response_data["data"])
        return response_data["data"]
    except Exception as e:
        print(f"Error al consultar AppSync: {e}")
        return None

def handler(event, context):
    try:
        if event.get('Records') and event['Records'][0].get('eventSource') == 'aws:dynamodb':
            for record in event['Records']:
                print("RECORD: ", record)
                eventName = record["eventName"]
                newImage = record["dynamodb"].get("NewImage")
                oldImage = record["dynamodb"].get("OldImage")

                print("eventName:", eventName)
                print("newImage:", newImage)

                if newImage and eventName == "INSERT":
                    # Al crear una campaña, verifica si la fecha de inicio es hoy
                    campaign_id = newImage["id"]["S"]
                    business_id = newImage["businessID"]["S"]
                    start_date_str = newImage["startDate"]["S"]
                    status = newImage["status"]["S"]
                    start_date = parser.parse(start_date_str).date()
                    current_date = datetime.now(timezone.utc).date()

                    # Obtener datos del negocio
                    business_data = get_business(business_id)
                    user_email = business_data["getBusiness"]["user"]["email"]
                    user_id = business_data["getBusiness"]["userID"]
                    business_name = business_data["getBusiness"]["name"]
                    print("Usuario y correo del negocio:", user_id, user_email)
                    
                    if status == "ACTIVE":
                        title = "Campaña de cupones publicada con éxito"
                        message = f"Tu campaña de cupones para el negocio {business_name} ha sido publicada con éxito."
                        body_message = f"Tu campaña de cupones para el negocio {business_name} ha sido publicada exitosamente. La fecha de inicio es {start_date_str}."
                        subject = "Campaña de cupones publicada para tu negocio"
                    else:
                        title = "Campaña de cupones creada con éxito"
                        message = f"Tu campaña de cupones para el negocio {business_name} ha sido creada con éxito."
                        body_message = f"Tu campaña de cupones para el negocio {business_name} ha sido creada exitosamente. La fecha de inicio es {start_date_str}."
                        subject = "Campaña de cupones creada para tu negocio"
                        

                    # Notificación de creación de campaña
                    user_notification_message = json.dumps({
                        "userID": user_id,
                        "title": title,
                        "message": message,
                        "type": "campaign",
                        "data": None,
                        "owner": business_data["getBusiness"]["owner"]
                    })
                    send_topic(user_notification_message, subject="User Notification DB", channel="user_notification")
                    
                     # Notificación por correo electrónico (creación de campaña)
                    email_message = json.dumps({
                        "subject": subject,
                        "body": body_message,
                        "email": user_email
                    })
                    send_topic(email_message, subject="Email Notification", channel="email")
                    print("Correo electrónico enviado:", email_message)

                    

                elif newImage and eventName == "MODIFY":
                    # Al modificar una campaña, verifica cambios en el estado
                    campaign_id = newImage["id"]["S"]
                    business_id = newImage["businessID"]["S"]
                    old_status = oldImage["status"]["S"]
                    new_status = newImage["status"]["S"]
                    total_quantity = newImage["totalQuantity"]["N"]
                    redeemed_quantity = newImage["redeemedQuantity"]["N"]
                    if old_status != new_status:
                        print(f"El estado de la campaña {campaign_id} cambió de {old_status} a {new_status}.")
                        # Obtener datos del negocio
                        business_data = get_business(business_id)
                        user_email = business_data["getBusiness"]["user"]["email"]
                        user_id = business_data["getBusiness"]["userID"]
                        business_name = business_data["getBusiness"]["name"]
                        
                        print("Usuario y correo del negocio:", user_id, user_email)

                        # Enviar notificación según el cambio de estado
                        if old_status == "INACTIVE" and new_status == "ACTIVE":
                            notification_message = f"Tu campaña de cupones para el negocio {business_name} ha sido publicada con éxito."
                        elif old_status == "ACTIVE" and new_status == "FINALIZED":
                            if int(redeemed_quantity) >= int(total_quantity):
                                notification_message = f"Tu campaña de cupones para el negocio {business_name} se ha cerrado. Límite alcanzado."
                            else:
                                notification_message = f"Tu campaña de cupones para el negocio {business_name} ha expirado. Fecha alcanzada."

                        user_notification_message = json.dumps({
                            "userID": user_id,
                            "title": "Actualización de estado de campaña",
                            "message": notification_message,
                            "type": "campaign",
                            "data": None,
                            "owner": business_data["getBusiness"]["owner"]
                        })
                        send_topic(user_notification_message, subject="User Notification DB", channel="user_notification")

                         # Notificación por correo electrónico (creación de campaña)
                        email_message = json.dumps({
                            "subject": "Actualización de estado de campaña",
                            "body": notification_message,
                            "email": user_email
                        })
                        send_topic(email_message, subject="Email Notification", channel="email")
                        print("Correo electrónico enviado:", email_message)

                    else:
                        print("No hubo cambio en el estado.")

                else:
                    print('No se encontró un NewImage en el evento o el evento no es de tipo INSERT/MODIFY.')

            return "Proceso de actualización de campaña completado."
        else:
            print('El eventSource no es "aws:dynamodb".')
            return 'El eventSource no es "aws:dynamodb".'
    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e
