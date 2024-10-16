import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
import json
import os

# Definir Region y otros parámetros
region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()
host = os.environ.get("OPENSE_ENDPONIT")
index = "countries"
awsauth = AWSV4SignerAuth(credentials, region, service)

# Cliente de S3
s3 = boto3.client("s3", region_name=region)
bucket_name = os.environ.get("S3_BUCKET_NAME")

# Configuración de OpenSearch
opense = OpenSearch(
    hosts=[{'host': host.replace("https://", ""), 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20
)

# Función para obtener los nombres de archivos .geo.json de S3
def list_geojson_files():
    try:
        # Lista los objetos en el bucket bajo la ruta 'public/countries/'
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='public/countries/')
        files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.geo.json')]
        return files
    except Exception as e:
        print(f"Error listando archivos en S3: {str(e)}")
        return []

# Función para obtener el geojson de cada país desde S3
def get_country_data(file_key):
    try:
        # Obtener el archivo geo.json desde S3
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        geojson_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Extraer id, name y geometría
        feature = geojson_data["features"][0]
        country_id = feature["id"]
        country_name = feature["properties"]["name"]
        coordinates = feature["geometry"]["coordinates"]
        
        return {
            "id": country_id,
            "name": country_name,
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": coordinates
            }
        }
    except Exception as e:
        print(f"Error obteniendo el geojson del país {file_key}: {str(e)}")
        return None

# Función para insertar los datos en OpenSearch usando _bulk
def bulk_insert_to_opensearch(countries):
    bulk_data = ""
    
    for country in countries:
        action = {
            "index": {
                "_index": index,
                "_id": country["id"]
            }
        }
        document = {
            "id": country["id"],
            "name": country["name"],
            "geometry": country["geometry"]
        }
        # Agregar al cuerpo del bulk
        bulk_data += json.dumps(action) + "\n" + json.dumps(document) + "\n"
    
    # Realizar la operación _bulk en OpenSearch
    try:
        response = opense.bulk(body=bulk_data)
        if response.get('errors'):
            print(f"Errores en la inserción masiva: {response}")
        else:
            print(f"Insertados correctamente {len(countries)} países en OpenSearch.")
    except Exception as e:
        print(f"Error durante la inserción masiva en OpenSearch: {str(e)}")

def handler(event, context):
    try:
        # Paso 1: Listar todos los archivos .geo.json en S3
        geojson_files = list_geojson_files()
        
        # Paso 2: Obtener los datos de cada archivo .geo.json
        countries_data = []
        for file_key in geojson_files:
            country_data = get_country_data(file_key)
            if country_data:
                countries_data.append(country_data)
        
        # Paso 3: Realizar la inserción masiva en OpenSearch
        if countries_data:
            bulk_insert_to_opensearch(countries_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Carga de países en OpenSearch realizada con éxito.",
                "countries_inserted": len(countries_data)
            })
        }
    except Exception as e:
        print(str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error durante la carga de países en OpenSearch.",
                "error": str(e)
            })
        }
