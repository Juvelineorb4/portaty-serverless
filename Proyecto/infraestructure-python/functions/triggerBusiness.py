import json
import boto3
import os
client = boto3.client('sns')

TOPIC_OPENSEARCH = os.environ.get("SNS_TOPIC_OPENSEARCH_ARN")
TOPIC_TRIGGER = os.environ.get("SNS_TOPIC_ARN")


def sendTopic(email):
    objecto = {"email": email}

    TOPIC_ARN = TOPIC_TRIGGER
    result = client.publish(
    TopicArn= TOPIC_ARN,
    Message=json.dumps(objecto),
    )

    print("RESPONSE:", result)
    return result

def openSearchTopic(record, priority):
    print("Prioridad es:",priority)
    TOPIC_ARN = TOPIC_OPENSEARCH
    result = client.publish(
    TopicArn= TOPIC_ARN,
    Message=json.dumps(record),
    MessageGroupId=priority
    )

    return result

def handler(event, context):
    print("EVENT:", event)
    priority_message = "2"
    records = event.get("Records")
    for record in records:
        eventSource = record["eventSource"]
        eventName = record["eventName"]
        # establemos que la fuentes en dynamodb
        if eventSource == "aws:dynamodb":
            # si el disparo es por un insert enviamos mensaje
            if (eventName == "INSERT"): 
                priority_message = "1"
                datos = record["dynamodb"]["NewImage"]
                email =  datos["email"]["S"]
                sendTopic(email)
            # Enviar evento para ser analizado
            resultOpenseTocip = openSearchTopic(record, priority_message)
            print("RESULTADO DE ENVIAR MENSAJE A TOPICO: ",resultOpenseTocip)
        

            

        
            
           


    response = {
        "statusCode": 200,
        "body": json.dumps("LAMBDA SEND")
    }

    return response




