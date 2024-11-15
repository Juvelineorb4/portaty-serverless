import json
import boto3
import os

client = boto3.client('sns')

TOPIC_OPENSEARCH = os.environ.get("SNS_TOPIC_OPENSEARCH_ARN")
TOPIC_TRIGGER = os.environ.get("SNS_TOPIC_ARN")

def sendTopic(record):
    TOPIC_ARN = TOPIC_TRIGGER  # actualmente para enviar email al negocio
    try:
        result = client.publish(
            TopicArn=TOPIC_ARN,
            Message=json.dumps(record),
        )
        print("RESPONSE:", result)
        return result
    except Exception as e:
        print(f"Error enviando mensaje a TOPIC_TRIGGER: {e}")
        return {"Error": str(e)}

def openSearchTopic(record, priority):
    TOPIC_ARN = TOPIC_OPENSEARCH  # sincronizar con OpenSearch
    try:
        result = client.publish(
            TopicArn=TOPIC_ARN,
            Message=json.dumps(record),
            MessageGroupId=priority
        )
        print("RESPONSE OpenSearchTopic:", result)
        return result
    except Exception as e:
        print(f"Error enviando mensaje a TOPIC_OPENSEARCH: {e}")
        return {"Error": str(e)}

def handler(event, context):
    print("EVENT:", event)
    priority_message = "2"
    records = event.get("Records", [])
    
    for record in records:
        try:
            eventSource = record.get("eventSource", "")
            eventName = record.get("eventName", "")
            
            # Establecemos que la fuente es DynamoDB
            if eventSource == "aws:dynamodb":
                # Verificar si existe NewImage para evitar errores en REMOVE
                newImage = record["dynamodb"].get("NewImage")
                
                if newImage:
                    status = newImage["status"]["S"]
                    statusOwner = newImage["statusOwner"]["S"]
                    print(f"status: {status} statusOwner: {statusOwner}")
                    
                    if eventName == "INSERT" and status == "ENABLED" and statusOwner == "OWNER":
                        priority_message = "1"
                        sendTopic(newImage)

                # Enviar evento a OpenSearch, independientemente de INSERT o REMOVE
                resultOpenseTopic = openSearchTopic(record, priority_message)
                print("RESULTADO DE ENVIAR MENSAJE A TOPICO:", resultOpenseTopic)

        except KeyError as e:
            print(f"Error KeyError en el registro: {record}. Detalle: {e}")
        except Exception as e:
            print(f"Error procesando el registro: {record}. Detalle: {e}")
    
    response = {
        "statusCode": 200,
        "body": json.dumps("LAMBDA SEND")
    }
    
    return response
