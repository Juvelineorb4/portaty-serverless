import json
import os
from urllib.parse import urlparse, quote
import boto3
from boto3.dynamodb.types import TypeDeserializer
import requests
from requests_aws4auth import AWS4Auth




# Variables de openSeach 
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT")
OPENSEARCH_REGION = os.environ.get("OPENSEARCH_REGION")
OPENSE_INDEX = os.environ.get("OPENSE_INDEX")
DOC_TYPE = '_doc'

region = os.environ.get("OPENSEARCH_REGION")
service = 'es' # servicio de opensearch
credentials = boto3.Session().get_credentials() # credenciales de boto3 asociadas a esta session
# Para firmar las solicitudes https con la firma AWS Signature Version 4. Esta firma es necesaria para autenticar las solicitudes a servicios como OpenSearch.
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token) 



class StreamTypeDeserializer(TypeDeserializer):
    def _deserialize_n(self, value):
        val = float(value)
        if (val.is_integer()):
            return int(value)
        else:
            return val

    def _deserialize_b(self, value):
        return value  # Already in Base64
    
class DDBTypesEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

# Compute a compound doc index from the key(s) of the object in lexicographic order: "k1=key_val1|k2=key_val2"
def compute_doc_index(keys_raw, deserializer, formatIndex=False):
    index = []
    for key in sorted(keys_raw):
        if formatIndex:
            index.append('{}={}'.format(
                key, deserializer.deserialize(keys_raw[key])))
        else:
            index.append(deserializer.deserialize(keys_raw[key]))
    return '|'.join(map(str,index))





# obtener nombre de la tabla desde el arn
def get_table_name_from_arn(arn):
    return arn.split(':')[5].split('/')[1]

def post_to_opensearch(payload):
    # "Publicar datos en el clúster OpenSearch con retroceso exponencial"

    opensearch_url = urlparse(OPENSEARCH_ENDPOINT)
    # Extract the domain name in OPENSEARCH_ENDPOINT
    opensearch_endpoint = opensearch_url.netloc or opensearch_url.path
   
    url = f"https://{opensearch_endpoint}{quote('/_bulk')}"
  
    # Encabezados necesarios para la solicitud HTTP POST
    headers = { "Content-Type": "application/json" }
    # Realiza la solicitud HTTP POST para enviar los datos masivos
    response = requests.post(url, auth=awsauth, headers=headers, data=payload)

    # Verifica la respuesta
    if response.status_code == 200:
        print("'Datos indexados en OpenSearch con éxito'")
      
    else:
        print(f'Error al enviar datos masivos: {response.text}')
      

    



def handler(event, context):
    print("EVENTO:", event)
    response = {
        "statusCode": 200,
        "body": json.dumps("Messaged Send")
    }

   
    records = event.get("Records")
    ddb_deserializer = StreamTypeDeserializer()
    cnt_insert = cnt_modify = cnt_remove = 0
    opensearch_actions = []  # Items to be added/updated/removed from OpenSearch 
    print("Records: ", records)
   
    for record in records:
        message = get_message(record)
        print("MENSAJE: ", message)
        # Preguntamos si es un evento de tipo aws:dynamodb
        if message.get("eventSource") == "aws:dynamodb":
            ddb = message["dynamodb"]
            # Obtenemos el nombre de la tabla 
            ddb_table_name = get_table_name_from_arn(message['eventSourceARN'])

            # Compute DynamoDB table, type and index for item
            doc_table = ddb_table_name.lower()
            doc_type = DOC_TYPE
            doc_table_parts = doc_table.split('-')
            # Obtenemos el nombre del index que usaremos en openSearch
            # doc_opensearch_index_name = doc_table_parts[0] if len(doc_table_parts) > 0  else doc_table
            doc_opensearch_index_name = OPENSE_INDEX
            # Tipo de evento en la tabla de dynamodb
            event_name = message.get("eventName").upper()
            # verificamos si es INSERT O MODIFY
            is_ddb_insert_or_update = (event_name == 'INSERT') or (event_name == 'MODIFY')
            # SI es REMOVEs
            is_ddb_delete = event_name == 'REMOVE'
            # Si es INSERT o MOFIFY obtenemos el New Image si no es el OldImage
            image_name = 'NewImage' if is_ddb_insert_or_update else 'OldImage'
            
            if image_name not in ddb:
                print('No se puede procesar la secuencia si no contiene', image_name)
                continue
            # Deserialize DynamoDB type to Python types
            doc_fields = ddb_deserializer.deserialize({'M': ddb[image_name]})
            # del doc_fields["images"]
            # del doc_fields["tags"]
            for i, item in enumerate(doc_fields['tags']):
                objeto_json = json.loads(item)
                doc_fields['tags'][i] = objeto_json
                # Update counters
            if event_name == 'INSERT':
                cnt_insert += 1
            elif event_name == 'MODIFY':
                cnt_modify += 1
            elif event_name == 'REMOVE':
                cnt_remove += 1
            else:
                print('No Soportado event_name:', event_name)

            if ('Keys' in ddb):
                doc_id = compute_doc_index(ddb['Keys'], ddb_deserializer)
            else:
                print('No se pueden encontrar Keys en el registro ddb')
        
            print(f"Estado Dynamodb por ejecutar {event_name}, id:{doc_id}")
            # SI DynamoDB INSERT or MODIFY, enviar el 'index' a OpenSearch
            if is_ddb_insert_or_update:
              
                # Genera el payload que se cargara en openSearch
                action = {'index': {'_index': doc_opensearch_index_name,
                                '_id': doc_id}}
                # Agregamos OpenSearch la linea de action 'index' como directiva
                opensearch_actions.append(action)
                # agregamos  JSON datos que se guardara  payload
                opensearch_actions.append(doc_fields)

                 # eliminar la clave antigua si existe
                if ('id' in doc_fields) and (event_name == 'MODIFY') :
                    action = {'delete': {'_index': doc_opensearch_index_name, 
                        '_id': compute_doc_index(ddb['Keys'], ddb_deserializer, True)}}
                    opensearch_actions.append(action)
            elif is_ddb_delete:

                action = {'delete': {'_index': doc_opensearch_index_name,
                                    '_id': doc_id}}
                # linia de accion con 'delete' directiva
                opensearch_actions.append(action)

            # Preparar toda la carga masiva para openSearch
    opensearch_payload = '\n'.join([json.dumps(doc) for doc in opensearch_actions]) + '\n'
    print("OPENSEARCH PAYLOAD:", opensearch_payload)
    post_to_opensearch(opensearch_payload)  # Post to OpenSearch with exponential backoff
    
    response = {
        "statusCode": 200,
        "body": json.dumps("Messaged Send")
    }

    return response

def get_message(data):

    body = data.get("body")
    jsonBody = json.loads(body)
    return jsonBody