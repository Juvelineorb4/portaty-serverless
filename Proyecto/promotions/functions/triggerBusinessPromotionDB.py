import boto3
import os
import json

client = boto3.client('sns')
TOPIC_BUSINESS_PROMOTION_ARN = os.environ.get("TOPIC_BUSINESS_PROMOTION_ARN")
print("TOPIC_BUSINESS_PROMOTION_ARN:", TOPIC_BUSINESS_PROMOTION_ARN)

def sendTopic(msg):
    TOPIC_ARN = TOPIC_BUSINESS_PROMOTION_ARN
    result = client.publish(
        TopicArn=TOPIC_ARN,
        Message=msg,
    )
    print("RESPONSE SEND TOPIC:", result)
    return result

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
                # esto quiere decir que es la primera vez que se crea
                if newImage and eventName == "INSERT": 
                    promotion_id = newImage.get('id', {}).get('S')
                    business_id = newImage.get('businessID', {}).get('S')
                    status = newImage.get('status', {}).get('S')
                    userID = newImage.get('userID', {}).get('S')
                    title = newImage.get('title', {}).get('S')
                    image_url = newImage.get('image', {}).get('S')
                    if status == "PUBLISHED":
                        print("ENVIAR NOTIFICACIONES A TODOS LOS USUARIOS")
                        msg_object = {
                            "data": {
                                "id": promotion_id,
                                "businessID": business_id,
                                "status": status,
                                "userID": userID,
                                "title":title,
                                "image_url":image_url
                            }
                        }
                        msg = json.dumps(msg_object)
                        sendTopic(msg)
                        print('Trigger Business Promotion exitoso')
                        return 'Trigger Business Promotion exitoso'
                    else:
                        print('El estado no es "PUBLISHED", no se envían notificaciones.')
                        return 'El estado no es "PUBLISHED", no se envían notificaciones.'
                else:
                    print('No se encontró un NewImage en el evento.')
                    return 'No se encontró un NewImage en el evento.'
            print('No se procesaron registros en el evento.')
            return 'No se procesaron registros en el evento.'
        else:
            print('El eventSource no es "aws:dynamodb".')
            return 'El eventSource no es "aws:dynamodb".'
    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e
