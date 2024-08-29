import boto3
import json
import requests
from requests_aws4auth import AWS4Auth
import os
import math

expo_push_url = 'https://exp.host/--/api/v2/push/send'

# Validación de Variables de Entorno
required_env_vars = ["APPSYNC_URL", "APPSYNC_API_KEY", "TABLE_BUSINESS_PROMOTION_NAME", "AWS_REGION", "OPENSE_ENDPONIT", "OPENSE_BUSINESS_INDEX"]
for var in required_env_vars:
    if not os.environ.get(var):
        raise ValueError(f"La variable de entorno {var} no está configurada.")

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")
table_promotion = os.environ.get("TABLE_BUSINESS_PROMOTION_NAME") 

region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()

# Validación de Credenciales AWS
if not all([credentials.access_key, credentials.secret_key, credentials.token]):
    raise ValueError("No se encontraron las credenciales de AWS necesarias.")

awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_BUSINESS_INDEX")
url = f"{host}/{index}/_search"

dynamodb = boto3.client("dynamodb", region_name=region)

def list_promotions(business_ids):
    if not business_ids:
        print("No se encontraron negocios cercanos.")
        return []
    
    business_id_filters = [{"businessID": {"eq": id}} for id in business_ids]
    query = """
    query ListBusinessPromotions(
    $filter: ModelBusinessPromotionFilterInput
    $limit: Int
    $nextToken: String
  ) {
        listBusinessPromotions(
      filter: $filter
      limit: $limit
      nextToken: $nextToken
    ) {
            items {
                id
                title
                notifiedUserIDs
                business{
                    name
                }
            }
        }
    }
    """
    variables = {
        "filter": {
            "and": [
                {"status": {"eq": "PUBLISHED"}},
                {"or": business_id_filters}
            ]
        }
    }
    print("FILTER: ", variables)
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    try:
        response = requests.post(
            appsync_api_url,
            json={"query": query, "variables": variables},
            headers=headers,
        )
        response.raise_for_status()
        response_data = response.json()

        # Validación de la respuesta de AppSync
        if "data" not in response_data or "listBusinessPromotions" not in response_data["data"]:
            print("Formato de respuesta inesperado de AppSync.")
            return []

        print("RESULTADO DE API:", response_data)
        return response_data["data"]["listBusinessPromotions"]["items"]

    except requests.exceptions.RequestException as e:
        print(f"Error al consultar promociones en AppSync: {e}")
        return []

def list_business_by_distance(location):
    lat = location["lat"]
    lon = location["lon"]
    query = {
        "_source": ["id", "thumbnail"],
        "query": {
            "bool": {
                "must": {
                    "match_all": {}
                },
                "filter": {
                    "geo_distance": {
                        "distance": "100km",
                        "coordinates": {
                            "lat": f"{lat}",
                            "lon": f"{lon}"
                        }
                    }
                }
            }
        }
    }

    headers = {"Content-Type": "application/json"}

    try:
        r = requests.get(url, auth=awsauth, headers=headers, data=json.dumps(query))
        r.raise_for_status()
        search_results = json.loads(r.text)

        # Validación de la respuesta de OpenSearch
        if "hits" not in search_results or "hits" not in search_results["hits"]:
            print("Formato de respuesta inesperado de OpenSearch.")
            return []

        hits = search_results['hits']['hits']
        ids = [hit['_source']['id'] for hit in hits]
        print("IDs de los negocios encontrados:", ids)
        return ids

    except requests.exceptions.RequestException as e:
        print(f"Error al consultar negocios en OpenSearch: {e}")
        return []

def send_notification(promotion_id, user_id, token, nombre, title):
    print(f"Enviando notificación al usuario {user_id} sobre la promoción {promotion_id}")
    
    ownerMsg = {
        'to': token,
        'title': f"¡Nueva promoción de {nombre}!",
        'body': title
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
        print("Push notification successfully sent to the business owner via Expo's Push API.")

    except requests.exceptions.HTTPError as e:
        print(f"Error sending push notification to the business owner. Is this Expo push token valid? {e}")

    except Exception as e:
        print(f"Error inesperado al enviar la notificación: {e}")

def update_notified_users(promotion_id, user_id):
    print(f"Añadiendo el usuario {user_id} a la lista de notifiedUserIDs para la promoción {promotion_id}")
    
    ids_to_add = [{'S': str(user_id)}]
    
    try:
        response = dynamodb.update_item(
            TableName=table_promotion,
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

    except Exception as e:
        print(f"Error al actualizar DynamoDB: {e}")
        raise e

def handler(event, context):
    try:
        for record in event['Records']:
            print("RECORD: ", record)
            
            body = record.get('body')
            if not body:
                print("No se encontró el body en el registro.")
                continue
            
            message = json.loads(json.loads(body).get("Message"))
            if not message:
                print("No se encontró Message en el body.")
                continue
            
            print("Message Recibido:", message)
            
            if message.get('eventName') != 'MODIFY':
                print("El evento no es de tipo MODIFY.")
                continue

            dynamodb_data = message.get('dynamodb')
            if not dynamodb_data:
                print("No se encontró dynamodb en el mensaje.")
                continue
            
            new_image = dynamodb_data.get('NewImage', {})
            if not new_image:
                print("No se encontró NewImage en dynamodb.")
                continue
            
            new_location = new_image.get('lastLocation', {}).get('M', {})
            if not new_location:
                print("No se encontró lastLocation en NewImage.")
                continue

            try:
                new_lon = float(new_location.get('lon', {}).get('N'))
                new_lat = float(new_location.get('lat', {}).get('N'))
                print(f'Nueva ubicación: lat={new_lat}, lon={new_lon}')
                business_ids = list_business_by_distance({"lat": new_lat, "lon": new_lon})
                
                if business_ids:
                    promotions = list_promotions(business_ids)
                    user_id = new_image.get('id', {}).get('S')  # Asume que userID está en NewImage

                    if 'notificationToken' not in new_image or not new_image['notificationToken'].get('L'):
                        print("El campo 'notificationToken' no se encuentra en NewImage o está vacío.")
                        continue

                    ownerToken = new_image['notificationToken']['L'][0]["S"]
                    print("NOTIFICATION TOKEN: ", ownerToken)
                    if user_id:
                        for promotion in promotions:
                            print("PROMOCION: ", promotion)
                            promotion_id = promotion['id']
                            notified_user_ids = promotion.get('notifiedUserIDs', [])
                            if notified_user_ids is None:
                                notified_user_ids = []
                            nombre = promotion.get('business').get("name", "")
                            title = promotion.get('title', "")
                            print("notified_user_ids", notified_user_ids)
                            if user_id not in notified_user_ids:
                                
                                send_notification(promotion_id, user_id, ownerToken, nombre, title)
                                update_notified_users(promotion_id, user_id)
                            else:
                                print(f"El usuario {user_id} ya ha sido notificado sobre la promoción {promotion_id}.")
                    else:
                        print("No se encontró userID en NewImage.")
                else:
                    print("No se encontraron promociones debido a que no hay negocios cercanos.")

            except (TypeError, ValueError) as e:
                print(f"Error al obtener la ubicación: {e}")
                continue

        return 'Trigger Business Promotion exitoso'
    
    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e
