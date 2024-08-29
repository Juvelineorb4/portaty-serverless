import boto3
import json
import requests
from requests_aws4auth import AWS4Auth
import os
import smtplib
from email.message import EmailMessage
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")


expo_push_url = 'https://exp.host/--/api/v2/push/send'
# Configura tus credenciales y región
AWS_REGION = os.environ.get("AWS_REGION")
table_device_notification = os.environ.get("TABLE_DEVICE_NOTIFICATION_TOKEN_NAME")
table_users = os.environ.get("TABLE_USERS_NAME")
table_business = os.environ.get("TABLE_BUSINESS_NAME") 
table_promotion = os.environ.get("TABLE_BUSINESS_PROMOTION_NAME") 
# Crea una instancia del cliente de DynamoDB
dynamodb = boto3.client("dynamodb", region_name=AWS_REGION)


# configuracion opense 
region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_USERS_INDEX")
url = f"{host}/{index}/_search"


def get_business_coor(id):
    response = dynamodb.get_item(
        TableName=table_business,
        Key={'id': {'S': id}},
    )
    print("RESPONSE: ", response)
    if "Item" in response:
        item = response['Item']
        print(f"Elemento encontrado: {item}")
        coordinates = item["coordinates"]["M"]
        lat = coordinates["lat"]["N"]
        lon = coordinates["lon"]["N"]
        return {
            "lat": lat,
            "lon": lon
        }
    else:
        return None

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
    
def get_token_users_opense(coor, id):
    lat = coor["lat"]
    lon = coor["lon"]
    query = {
        "_source": ["id", "notificationToken", "email", "owner"],
        "query": {
            "bool": {
                "must": {
                    "match_all": {}
                },
                "filter": {
                    "geo_distance": {
                        "distance": "100km",
                        "lastLocation": {
                            "lat": f"{lat}",
                            "lon": f"{lon}"
                        }
                    }
                }
            }
        }
    }

    # Elasticsearch 6.x requires an explicit Content-Type header
    headers = {"Content-Type": "application/json"}

    # Make the signed HTTP request
    r = requests.get(url, auth=awsauth, headers=headers, data=json.dumps(query))
    search_results = json.loads(r.text)
    print("RESULTADO: ", search_results)
    
    # Extraer los IDs y tokens de los resultados
    hits = search_results.get('hits', {}).get('hits', [])
   
    tokens = []
    user_ids = []
    ownerEmail = None
    ownerToken = None
    owner = None
    for hit in hits:
        source = hit['_source']
        user_ids.append(source['id'])
        if source['id'] == id:
            ownerToken = source['notificationToken'][0]
            ownerEmail = source['email']
            owner = source['owner']
        else:
            tokens.append(source['notificationToken'][0])
    
    print("Tokens de los usuarios encontrados:", tokens)
    print("Token del propietario:", ownerToken)
    
    return tokens, ownerToken, user_ids,ownerEmail, owner



def update_db_promotion(promotion_id, ids):
    # Convertir los ids a un formato compatible con DynamoDB
    ids_to_add = [{'S': str(id)} for id in ids]
    
    # Actualizar el campo ids en la base de datos
    response = dynamodb.update_item(
        TableName= table_promotion,
        Key={'id': {'S': promotion_id}},
        UpdateExpression="SET notifiedUserIDs = list_append(if_not_exists(notifiedUserIDs, :empty_list), :new_ids)",
        ExpressionAttributeValues={
            ':new_ids': {'L': ids_to_add},
            ':empty_list': {'L': []}
        },
        ReturnValues="UPDATED_NEW"
    )
    
    print("Actualización de la promoción:", response)
    return response


def sendEmail(datos):
    des = datos["des"]
    subject = datos['subject']
    mensaje = datos['message']
    remitente = "no-responder@portaty.com"
    destinatario = des


    # configuracion
    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = subject
    email.set_content(mensaje)
    try:
        smtp = smtplib.SMTP_SSL("smtp.zoho.com", 465)  # Ajusta el puerto según la configuración de tu proveedor
        smtp.login(remitente, "HdCmgawsJZbN")  # Utiliza variables de entorno o un sistema de gestión de secretos
        smtp.sendmail(remitente, destinatario, email.as_string())
        smtp.quit()
    except Exception as e:
        print("Error al enviar el correo electrónico:", str(e))
        


def create_notification_user(data):
   
    query = """
       mutation CreateUserNotification(
            $input: CreateUserNotificationInput!
        ) {
            createUserNotification(input: $input) {
            id
            userID
            title
            message
            type
            data
            owner
            createdAt
            updatedAt
            __typename
            }
        }
    """
    variables = {
      "input": data
    }
    print("FILTER: ", variables)
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    response = requests.post(
        appsync_api_url,
        json={"query": query, "variables": variables},
        headers=headers,
    )
    print("RESPONSE GRAPHQL:", response.json())
    return response.json()["data"]


def handler(event, context):
    try:
        notification_promises = []
        # Procesa cada registro del evento
        for record in event['Records']:
            print("RECORD: ", record)
            message_body = record['body']
            print(f'Mensaje recibido: {message_body}')
            body_json = json.loads(message_body)
            data = body_json["data"]
            businessID = data.get("businessID")
            userID = data.get("userID")
            title = data.get("title", "")
            promotion_id = data.get("id", "")
            image_url = data.get("image_url", "")
       
            # obtener negocio
            business = get_db(table_business, businessID)
            nombre = business.get("name").get("S", "")
            # Buscamos las coordenadas del business
            business_coor = get_business_coor(businessID)
            print("Coordinates Business: ", business_coor)
            # buscamos a los usuarios que tenga en lastConnection a 100km y obtenemos su notificationToken
            tokens, ownerToken, user_ids, ownerEmail, owner = get_token_users_opense(business_coor, userID)
            # enviar notificacion
            # crear mensajes para usuarios
            messages = []
            for token in tokens:
                if token:
                    messages.append({
                        'to': token,
                        'title': f"¡Nueva promoción de {nombre}!",
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

            # Enviar notificación al propietario
            if ownerToken and ownerEmail:
                ownerMsg = {
                    'to': ownerToken,
                    'title': f"¡Tu promoción ha sido publicada {nombre}!",
                    'body': f"La promocion {title} fue publicada con exito!",
                    'priority': 'high',
                    'data': {
                        'data': {
                            'type': "promotion",
                            'promotionID': promotion_id
                        }
                    }
                }
                try:
                    response = requests.post(
                        expo_push_url,
                        json=ownerMsg,
                        headers={
                            'Accept': 'application/json',
                            'Accept-encoding': 'gzip, deflate',
                            'Content-Type': 'application/json'
                        }
                    )

                    response.raise_for_status()
                    sendEmail({'des': ownerEmail,  'subject': f"¡Tu promoción ha sido publicada {nombre}!", 'message': f"La promocion {title} fue publicada con exito!"})
                    inputData = {
                        "userID": userID,
                        "title": f"¡Tu promoción ha sido publicada {nombre}!" ,
                        "message": f"La promocion {title} fue publicada con exito!",
                        "type":"promotion",
                        "data": json.dumps({
                            'promotionID': businessID,
                            "image": image_url
                        }),
                        "owner": owner
                    }
                    create_notification_user(inputData)
                    notification_promises.append(
                        f"Push notification successfully sent to the business owner via Expo's Push API."
                    )

                except requests.exceptions.HTTPError as e:
                    notification_promises.append(
                        f"Error sending push notification to the business owner. Is this Expo push token valid?"
                    )

            results = notification_promises
            update_db_promotion(promotion_id,user_ids)
            print(f'RESULTS: {results}')

        return 'Trigger Business Promotion exitoso'
    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e

