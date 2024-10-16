import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
import json
import os
import requests
import logging

# Configuración inicial
region = os.environ.get("AWS_REGION")
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

# Definir Region y otros parámetros
service = "es"
credentials = boto3.Session().get_credentials()
awsauth = AWSV4SignerAuth(credentials, region, service)
host = os.environ.get("OPENSE_ENDPONIT")
index = os.environ.get("OPENSE_INDEX_USERS")
url = f"{host}/{index}/_search"

# Configuración de OpenSearch
opense = OpenSearch(
    hosts=[{'host': host.replace("https://", ""), 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20
)

# Función para obtener los usuarios desde AppSync
def list_users_db():
    query = """
     query ListUsers(
        $filter: ModelUsersFilterInput
        $limit: Int
        $nextToken: String
     ) {
        listUsers(filter: $filter, limit: $limit, nextToken: $nextToken) {
          items {
            id
            name
            lastName
            email
            identityID
            gender
            notificationToken
            lastLocation {
              lat
              lon
            }
            owner
            createdAt
            updatedAt
          }
          nextToken
        }
      }
    """
    
    variables = {
        "limit": 100  # Ajusta el límite según sea necesario
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    total_items = []
    next_token = None

    while True:
        if next_token:
            variables["nextToken"] = next_token
        else:
            variables.pop("nextToken", None)

        response = requests.post(
            appsync_api_url,
            json={"query": query, "variables": variables},
            headers=headers,
        )
        
        data = response.json()
        
        if "errors" in data:
            raise Exception(f"Error en la consulta de AppSync: {data['errors']}")
        
        dataItems = data["data"]["listUsers"]["items"]
        total_items.extend(dataItems)
        
        next_token = data["data"]["listUsers"].get("nextToken")
        
        # Si no hay nextToken, terminamos el ciclo
        if not next_token:
            break

    return total_items

# Función para insertar los datos en OpenSearch usando _bulk
def bulk_insert_to_opensearch(users):
    bulk_data = ""
    
    for user in users:
        action = {
            "index": {
                "_index": index,
                "_id": user["id"]
            }
        }
        document = {
            "id": user["id"],
            "name": user["name"],
            "lastName": user["lastName"],
            "email": user["email"],
            "identityID": user.get("identityID", ""),
            "gender": user.get("gender", ""),
            "notificationToken": user.get("notificationToken", ""),
            "lastLocation": user.get("lastLocation", None),
            "owner": user.get("owner", ""),
            "createdAt": user["createdAt"],
            "updatedAt": user["updatedAt"]
        }
        # Agregar al cuerpo del bulk
        bulk_data += json.dumps(action) + "\n" + json.dumps(document) + "\n"
    
    # Realizar la operación _bulk en OpenSearch
    try:
        response = opense.bulk(body=bulk_data)
        if response.get('errors'):
            logging.error(f"Errores en la inserción masiva: {response}")
        else:
            logging.info(f"Insertados correctamente {len(users)} usuarios en OpenSearch.")
    except Exception as e:
        logging.error(f"Error durante la inserción masiva en OpenSearch: {str(e)}")

# Función Lambda principal
def handler(event, context):
    try:
        # Buscamos los usuarios en la base de datos 
        users = list_users_db()
        logging.info(f"Usuarios obtenidos: {len(users)}")

        # Realizar la insercion masiva a OpenSearch
        bulk_insert_to_opensearch(users)
 
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Sincronización de usuarios exitosa",
            })
        }
    except Exception as e:
        # Manejo de error
        logging.error(f"Error al sincronizar usuarios: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al sincronizar usuarios",
                "error": str(e)
            })
        }

# Función para construir la respuesta de error
def error_response(message):
    return {
        'statusCode': 400,
        'body': json.dumps({
            "success": False,
            "message": message
        })
    }
