import boto3
import os
import json
import logging

# Configurar el logger
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('sns')
topic_users_opense = os.environ.get("TOPIC_USERS_OPENSE_ARN")
topic_users_change_location = os.environ.get("TOPIC_USERS_CHANGE_LOCATION_ARN")
topic_users_send_email = os.environ.get("TOPIC_USERS_SEND_EMAIL_ARN")

def sendTopic(record, priority):
    try:
        logger.info(f"Prioridad es: {priority}")
        TOPIC_ARN = topic_users_opense
        result = client.publish(
            TopicArn=TOPIC_ARN,
            Message=json.dumps(record),
            MessageGroupId=priority
        )
        return result
    except Exception as e:
        logger.error(f"Error enviando al topic: {e}")
        raise e

def topic_send_email(record):
    try:
        TOPIC_ARN = topic_users_send_email
        result = client.publish(
            TopicArn=TOPIC_ARN,
            Message=json.dumps(record),
        )
        return result
    except Exception as e:
        logger.error(f"Error enviando el email: {e}")
        raise e

def sendTopic_change_location(record):
    try:
        TOPIC_ARN = topic_users_change_location
        result = client.publish(
            TopicArn=TOPIC_ARN,
            Message=json.dumps(record),
        )
        return result
    except Exception as e:
        logger.error(f"Error enviando cambio de ubicación: {e}")
        raise e

def handler(event, context):
    try:
        priority_message = "2"
        records = event.get("Records", [])
        if not records:
            logger.warning("No records found in the event")
            return 'No records to process'
        
        for record in records:
            logger.info(f"RECORD: {record}")
            eventSource = record.get("eventSource")
            eventName = record.get("eventName")
            
            if not eventSource or not eventName:
                logger.warning(f"Event source or event name is missing in record: {record}")
                continue
            
            logger.info(f"Event Source: {eventSource}")
            logger.info(f"eventName: {eventName}")
            
            # Validación para el evento de INSERT
            if eventSource == "aws:dynamodb" and eventName == "INSERT":
                priority_message = "1"
                if 'dynamodb' in record and 'NewImage' in record['dynamodb']:
                    new_image = record['dynamodb']['NewImage']
                    try:
                        result_topic_send_email = topic_send_email(new_image) 
                        logger.info(f"Result of Send Email Topic: {result_topic_send_email}")
                    except Exception as e:
                        logger.error(f"Error al enviar el email: {e}")
                else:
                    logger.warning("No se encontró el campo 'NewImage' en el evento de INSERT")
                
            # Enviar mensaje al topic general
            resultSendTopic = sendTopic(record, priority_message)
            logger.info(f"Result of sendTopic: {resultSendTopic}")
       
            # Verificar si hay un cambio de ubicación (evento MODIFY)
            if eventSource == "aws:dynamodb" and eventName == "MODIFY":
                if 'dynamodb' in record and 'NewImage' in record['dynamodb'] and 'OldImage' in record['dynamodb']:
                    new_image = record['dynamodb']['NewImage']
                    old_image = record['dynamodb']['OldImage']
                    
                    # Validar si las coordenadas existen antes de acceder a ellas
                    if ('lastLocation' in new_image and 'lastLocation' in old_image and 
                        'M' in new_image['lastLocation'] and 'M' in old_image['lastLocation']):
                        
                        new_location = new_image['lastLocation']['M']
                        old_location = old_image['lastLocation']['M']
                        
                        if ('lat' in new_location and 'lon' in new_location and
                            'lat' in old_location and 'lon' in old_location):
                            
                            if (new_location['lat']['N'] != old_location['lat']['N'] or
                                new_location['lon']['N'] != old_location['lon']['N']):
                                logger.info("Cambio de ubicación detectado")
                                try:
                                    resultSendTopicChangeLocation = sendTopic_change_location(record)
                                    logger.info(f"Result of sendTopic_change_location: {resultSendTopicChangeLocation}")
                                except Exception as e:
                                    logger.error(f"Error al enviar cambio de ubicación: {e}")
                        else:
                            logger.warning("Latitud o longitud faltante en los datos de ubicación")
                    else:
                        logger.warning("No se encontraron los datos de 'lastLocation' en las imágenes")
                else:
                    logger.warning("No se encontraron los campos 'NewImage' o 'OldImage' en el evento MODIFY")
        
        return 'Trigger UsersDB exitoso'
                       
    except Exception as e:
        logger.error(f'Error al procesar el mensaje: {e}', exc_info=True)
        raise e
