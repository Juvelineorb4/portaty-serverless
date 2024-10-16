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
s3 = boto3.client("s3", region_name=AWS_REGION)
bucketName = os.environ.get("S3_BUCKET_NAME")

# configuracion opense 
region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_USERS_INDEX")
url = f"{host}/{index}/_search"
print("URL:", url)

def get_db(table_name, id):
    response = dynamodb.get_item(
        TableName=table_name,
        Key={'id': {'S': id}},
    )
    if "Item" in response:
        item = response['Item']
        coordinates = item.get("coordinates").get("M", "")
        lat = coordinates.get("lat").get("N")
        lon = coordinates.get("lon").get("N")
        name = item.get("name").get("S", "")
        coordinates = {"lat": lat, "lon":lon}
        email = item.get("email").get("S", "")
    
        return name, coordinates,email
    else:
        return None
    
def get_token_users_opense(coor, id):
    lat = coor["lat"]
    lon = coor["lon"]
    query =     {
  "_source": ["id", "owner"],
  "query": {
    "bool": {
      "should": [
        {
          "bool": {
            "must": {
              "match_all": {}
            },
            "filter": {
              "geo_distance": {
                "distance": "100km",
                "lastLocation": {
                  "lat": f"{lat}",
                  "lon":  f"{lon}"
                }
              }
            }
          }
        },
        {
          "term": {
            "id.keyword":  f"{id}"
          }
        }
      ],
      "minimum_should_match": 1
    }
  }
}
    


    # Elasticsearch 6.x requires an explicit Content-Type header
    headers = {"Content-Type": "application/json"}

    # Make the signed HTTP request
    r = requests.get(url, auth=awsauth, headers=headers, data=json.dumps(query))
    search_results = json.loads(r.text)
    
    # Extraer los IDs y tokens de los resultados
    hits = search_results.get('hits', {}).get('hits', [])
    user_ids = []
    for hit in hits:
        source = hit['_source']
        user_ids.append({"userID":source['id'], "owner": source['owner'] })
        
            
            
    return user_ids



def update_db_promotion(promotion_id, ids):
    # Convertir los ids a un formato compatible con DynamoDB
    ids_to_add = [{'S': str(id.get("userID"))} for id in ids]
    
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




# Función para enviar el correo electrónico
def sendEmail(destinatario, html_content):
    remitente = "no-responder@portaty.com"
    
    # Configuración del Email
    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = f"¡Tu promoción ha sido publicada!"
    
   # Enviar el contenido en HTML
    email.add_alternative(html_content, subtype='html')

    try:
        smtp = smtplib.SMTP_SSL("smtp.zoho.com", 465)
        smtp.login(remitente, "HdCmgawsJZbN")  # Usa AWS Secrets Manager o variables de entorno para las credenciales.
        smtp.sendmail(remitente, destinatario, email.as_string())
        smtp.quit()
    except Exception as e:
        print(f"Error al enviar el correo electrónico: {str(e)}")
        
        
# Función para cargar la plantilla HTML desde S3 y reemplazar los valores dinámicos
def get_html_content_from_s3(bucket, key, replacements):
    # print("REMPLAZAR: ", replacements)
    # Obtener la plantilla HTML desde S3
    response = s3.get_object(Bucket=bucket, Key=key)
    html_template = response['Body'].read().decode('utf-8')

    # Reemplazar los marcadores de posición con los datos reales
    for placeholder, value in replacements.items():
        html_template = html_template.replace(f'{placeholder}', value)

    return html_template
# Cuando una promocion pasa a published, se le envia una notificacion a los usuarios que etsen a 100km a la redoma 
# y una notificacion al usuario

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
            businessID = data.get("businessID") # Obtenemos el Negocio ID
            userID = data.get("userID") # Obtenemox el id del usuario propietario
            title = data.get("title", "") # Obtenemos el titulo de la promocion
            promotion_id = data.get("id", "") # obtenemos el id de la promocion
            image_url = data.get("image_url", "") # obtenemosl aurl de la imagen de la promocion
            dateInitial = data.get("dateInitial", "") 
            dateFinal = data.get("dateFinal", "") 
       
            # Obtenemos el negocio
            name, coordinates, email= get_db(table_business, businessID)
            print(f"Nombre de negocio {name}, coordinates: {coordinates}")
            # buscamos a los usuarios que tenga en lastConnection a 100km y obtenemos su notificationToken
            user_ids = get_token_users_opense(coordinates, userID)
            print("USER IDS:", user_ids)
            print("CANTIDAD DE USUARIOS ", len(user_ids))
            # Recorrer la lista una sola vez
            for user in user_ids:
                input_data = {
                        "userID": user["userID"],
                        "type":"promotion",
                        "owner": user["owner"],
                        "data": json.dumps({
                            'promotionID': businessID,
                            'extra': data,
                            "image": image_url
                        }),
                    }
                if user["userID"] == userID: # si es el propiteario
                    print("PARA EL PROPIETARIO")
                    input_data["title"]= f"¡Tu promoción ha sido publicada {name}!"
                    input_data["message"]= f"La promocion {title} fue publicada con exito!"
                else: # si no es el propietario
                    input_data["title"]= f"¡Nueva promoción de {name}!"
                    input_data["message"]=  title
                print("NOTIFICATION AL CREAR: ", input_data)
                create_notification_user(input_data)
                if email is not None:
                    # Cargar el contenido HTML desde S3
                    html_content = get_html_content_from_s3(bucketName, f"public/assets/html/promocion.html", {
                        '{business}': name,
                        '{descripion}': title,
                        '{imagen}': image_url,
                        '{fechaI}':dateInitial,
                        '{fechaC}':dateFinal
                    })
                    # print("HTML OBTENIDO: ", html_content)
                    sendEmail(email, html_content)
                    print("EMAIL ENVIADO")
            # Agregar lista de users_ids a promotions en notifiedUserIDs
            update_db_promotion(promotion_id,user_ids)  
        return 'Trigger Business Promotion exitoso'

          
    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e

