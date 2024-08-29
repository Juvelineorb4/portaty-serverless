import boto3
import os
import json
from boto3.dynamodb.types import TypeDeserializer
import requests


# Configura tus credenciales y región
AWS_REGION = os.environ.get("AWS_REGION")
table_device_notification = os.environ.get("TABLE_DEVICE_NOTIFICATION_TOKEN_NAME")
table_users = os.environ.get("TABLE_USERS_NAME")
table_business = os.environ.get("TABLE_BUSINESS_NAME") 
# Crea una instancia del cliente de DynamoDB
dynamodb = boto3.client("dynamodb", region_name=AWS_REGION)

# Crea una instancia de TypeDeserializer
deserializer = TypeDeserializer()

expo_push_url = 'https://exp.host/--/api/v2/push/send'

# Personaliza la serialización de conjuntos (sets) en JSON
class DDBTypesEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)





def scan_table_device(table_name):
    response = dynamodb.scan(TableName=table_name, ProjectionExpression="notificationToken")
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = dynamodb.scan(TableName=table_name, ExclusiveStartKey=response["LastEvaluatedKey"], ProjectionExpression="notificationToken")
        items.extend(response.get("Items", []))

    print("ITEMS: ", items)
 
 
   # Deserializa los valores dentro de la lista 'L' o el campo 'S'
    notification_tokens = []
    for item in items:
        token_value = None
        if "L" in item.get("notificationToken", {}):
            # Si es una lista, deserializa cada elemento
            token_list = item["notificationToken"]["L"]
            for token in token_list:
                token_value = token.get("S")
                if token_value:
                    notification_tokens.append(token_value)
        elif "S" in item.get("notificationToken", {}):
            # Si es un solo valor, simplemente obtén el campo 'S'
            token_value = item["notificationToken"]["S"]
            if token_value:
                notification_tokens.append(token_value)

    print("Tokens deserializados:", notification_tokens)
   
    return notification_tokens

def scan_table_user(table_name, excluded_user_id):
    response = dynamodb.scan(TableName=table_name, ProjectionExpression="notificationToken, id")
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = dynamodb.scan(TableName=table_name, ExclusiveStartKey=response["LastEvaluatedKey"], ProjectionExpression="notificationToken, id")
        items.extend(response.get("Items", []))


    
    # Filtra los registros excluyendo el userID específico
    filtered_items = [{"notificationToken": item.get("notificationToken")} for item in items if item.get("id", {}).get("S") != excluded_user_id]
    print("ITEMS EXCLUDE: ", filtered_items)
 
 
   # Deserializa los valores dentro de la lista 'L' o el campo 'S'
    notification_tokens = []
    for item in filtered_items:
        token_value = None
        if "L" in item.get("notificationToken", {}):
            # Si es una lista, deserializa cada elemento
            token_list = item["notificationToken"]["L"]
            for token in token_list:
                token_value = token.get("S")
                if token_value:
                    notification_tokens.append(token_value)
        elif "S" in item.get("notificationToken", {}):
            # Si es un solo valor, simplemente obtén el campo 'S'
            token_value = item["notificationToken"]["S"]
            if token_value:
                notification_tokens.append(token_value)

    print("Tokens deserializados:", notification_tokens)
   
    return notification_tokens



def get_db(table_name, id):
    response = dynamodb.get_item(
        TableName=table_name,
        Key={'id': {'S': id}},
    )
    print("RESPONSE: ", response)
    if "Item" in response:
        item = response['Item']
        print(f"Elemento encontrado: {item}")
        return item
    else:
        return None
def handler(event, context):
    try:
        notification_promises = []
           # traer los token de la tablas de notificaciones sin registrarse
        tokens_device_notifications = scan_table_device(table_device_notification)

        

        # Procesa cada registro del evento
        for record in event['Records']:
            print("RECORD: ", record)
            message_body = record['body']
            print(f'Mensaje recibido: {message_body}')
            body_json = json.loads(message_body)
            data = body_json["data"]
            title= data.get("title", "")
            print("DATA:", data)
            userID = data.get("userID")
            businessID = data.get("businessID")
            # obtener negocio
            business = get_db(table_business, businessID)
            nombre = business.get("name").get("S", "")
            
             # traer los token de cognito de los usuarios registrados
            if userID:
                print("FUE EXCLUDE")
                tokens_users = scan_table_user(table_users, userID)
            else:
                tokens_users = scan_table_device(table_users)
                
                
                
            print("tokens_device_notifications",tokens_device_notifications)
            print("tokens_users",tokens_users)
            
             # filtrar que no hayan token repetidos 
            # Combina los tokens en un conjunto para eliminar duplicados
            all_tokens_set = set(tokens_device_notifications + tokens_users)

            # Convierte el conjunto nuevamente a una lista
            all_tokens_list = list(all_tokens_set)

            print("Todos los tokens:", all_tokens_list)
            
            # enviar notificacion
            # crear mensaje
            messages = []
            for token in all_tokens_list:
               if token:
                    messages.append({
                        'to': token,
                        'title': f"¡Nueva promocion de {nombre}!",
                        'body': title
                    })
                   
            print("MENSAJES A ENVIAR: ", messages)
       
            for msg in messages:
                notification = msg.copy()

                try:
                    response = requests.post(
                        expo_push_url,
                        json=notification,
                        headers={
                            'Accept': 'application/json',
                            'Accept-encoding': 'gzip, deflate',
                            'Content-Type': 'application/json'
                        }
                    )

                    response.raise_for_status()
                    notification_promises.append(
                        f"Push notification successfully sent to '{notification['to']}' via Expo's Push API."
                    )

                except requests.exceptions.HTTPError as e:
                    notification_promises.append(
                        f"Error sending push notification to '{notification['to']}'. Is this Expo push token valid?"
                    )
            results = notification_promises
            print(f'RESULTS: {results}')
        

      
        
        return 'Trigger Business Promotion exitoso'

    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e
