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

def sendTopic(record, priority):
    logger.info(f"Prioridad es: {priority}")
    TOPIC_ARN = topic_users_opense
    result = client.publish(
        TopicArn=TOPIC_ARN,
        Message=json.dumps(record),
        MessageGroupId=priority
    )
    return result

def sendTopic_change_location(record):
    TOPIC_ARN = topic_users_change_location
    result = client.publish(
        TopicArn=TOPIC_ARN,
        Message=json.dumps(record),
    )
    return result

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
            logger.info(f"Event Source: {eventSource}")
            logger.info(f"eventName: {eventName}")
            
            if eventSource == "aws:dynamodb" and eventName == "INSERT":
                priority_message = "1"
                    
            resultSendTopic = sendTopic(record, priority_message)
            logger.info(f"Result of sendTopic: {resultSendTopic}")
            
            # Verificar si hay un cambio de location
            if eventSource == "aws:dynamodb" and eventName == "MODIFY":
                new_image = record['dynamodb']['NewImage']
                old_image = record['dynamodb']['OldImage']
                
                new_location = new_image['lastLocation']['M']
                old_location = old_image['lastLocation']['M']
                
                if (new_location['lat']['N'] != old_location['lat']['N'] or
                    new_location['lon']['N'] != old_location['lon']['N']):
                    logger.info("Cambio de ubicación detectado")
                    resultSendTopicChangeLocation = sendTopic_change_location(record)
                    logger.info(f"Result of sendTopic_change_location: {resultSendTopicChangeLocation}")
            
        return 'Trigger UsersDB exitoso'
                       
    except Exception as e:
        logger.error(f'Error al procesar el mensaje: {e}', exc_info=True)
        raise e
