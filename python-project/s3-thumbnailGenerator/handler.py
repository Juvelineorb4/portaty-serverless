import json
import boto3
import urllib.parse
from PIL import Image
from io import BytesIO
import os
import requests
from requests_aws_sign import AWSV4Sign


AWS_REGION = "us-east-1"
s3 = boto3.client("s3", region_name=AWS_REGION)
db = boto3.client("dynamodb", region_name=AWS_REGION)
tableNameDB = 'Business-ehid2xtqobf75gakml3qgdj45m-dev'
imageExtra = []


def resize_image(image, size):
    img = Image.open(image)
    img.thumbnail(size)
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return buffered.getvalue()


def put_db_profile(tableID, images, thumbnail):
    resultDB = db.update_item(
        TableName=tableNameDB,
        Key={'id': {'S': tableID}},
        UpdateExpression='SET #images = :images, #thumbnail = :thumbnail',
        ExpressionAttributeNames={
            '#images': 'images',
            '#thumbnail': 'thumbnail',
        },
        ExpressionAttributeValues={
            ':images': {'L': [{'S': item} for item in images]},
            ':thumbnail': {'S': thumbnail}
        },
        ReturnValues='UPDATED_NEW'
    )
    return resultDB


def put_db_extras(tableID, images):
    resultDB = db.update_item(
        TableName=tableNameDB,
        Key={'id': {'S': tableID}},
        UpdateExpression='SET #images = :images',
        ExpressionAttributeNames={
            '#images': 'images',
        },
        ExpressionAttributeValues={
            ':images': {'L': [{'S': item} for item in images]},
        },
        ReturnValues='UPDATED_NEW'
    )
    return resultDB


def get_db(id):
    response = db.get_item(
        TableName=tableNameDB,
        Key={'id': {'S': id}},
        ProjectionExpression='id, images'
    )
    if "Item" in response:
        item = response['Item']
        print(f"Elemento encontrado: {item}")
        return item
    else:
        return None


query_list_businesses = '''
    query ListBusinesses {
      listBusinesses {
        items {
          id
          name
          description
        }
      }
    }
    '''


def custom_graphql(query, variables=[]):
    # Reemplaza 'us-east-1' con tu región
    client = boto3.client('appsync', region_name='us-east-1')
    # Reemplaza con el ID de tu API de AppSync
    api_id = 'ehid2xtqobf75gakml3qgdj45m'

    endpoint_url = f'https://vkrtsagkivgqjgzbnhekkyusfm.appsync-api.{
        client.meta.region_name}.amazonaws.com/graphql'

    headers = {
        "Content-Type": "application/json",
        "x-api-key": "no-importa-ya-que-iam-se-usa"
    }

    payload = {
        "query": query,
    }

    try:
        response = requests.post(
            endpoint_url, json=payload, headers=headers).json()
        if 'errors' in response:
            print('Error attempting to query AppSync')
            print(response['errors'])
        else:
            return response
    except Exception as exception:
        print('Error with Mutation')
        print(exception)

    return None


def __parse_region_from_url(url):
    """Parses the region from the appsync url so we call the correct region regardless of the session or the argument"""
    # Example URL: https://xxxxxxx.appsync-api.us-east-2.amazonaws.com/graphql
    split = url.split('.')
    if 2 < len(split):
        return split[2]
    return None


def hello(event, context):
    print("EVENTO:", event)
    records = event["Records"]
    print("Records: ", records)
    try:
        for record in records:
            print("record:", record)
            s3Object = record["s3"]
            bucketName = s3Object["bucket"]["name"]
            key = s3Object["object"]["key"]
            # Decodificar la clave
            decoded_key = urllib.parse.unquote_plus(key)
            pathImage = os.path.dirname(decoded_key).replace("/incoming", "")
            imageName = os.path.basename(decoded_key)

            if "/incoming/" in decoded_key:
                print("Si esta dentro de un incoming")
                print(f"Nombre de Bucket: {bucketName}, key: {
                      decoded_key}, path: {pathImage}")
                # obtenemos el objecto s3
                response = s3.get_object(Bucket=bucketName, Key=decoded_key)
                print(f"Busqueda de Objecto: {response}")
                # obtenemos el objecto
                original = response["Body"].read()
                print(f"Objecto: {original}")
                # Acceder a los metadatos
                metadata = response.get('Metadata', {})
                print(f"Metadatos: {metadata}")
                # accedemos a los datos del metadato
                businessid = metadata.get("businessid")
                keyI = metadata.get("key")
                action = metadata.get("action")
                type = metadata.get("type")
                # buscamos el negocio para obtener el array de images
                business = get_db(businessid)
                if business is None:
                    return print("Elemento no encontrado")
                # arreglo de images
                imagesArray = business.get("images", {}).get("L", [])
                # Deserializar los strings JSON en objetos Python
                imagesObject = [json.loads(image['S'])
                                for image in imagesArray]
                # Ordenar la lista por el valor de 'key'
                imagesObject = sorted(
                    imagesObject, key=lambda x: int(x['key']))
                print(f"Arreglo viejo: {imagesObject}")
                # que accion hay que jercer
                if action == "create":
                    # que vamos a crear
                    if type == "extras":
                        print("Crear imagen extra")
                        # redimensionamos la imagen
                        imageData = resize_image(
                            BytesIO(original), (1024, 1024))
                        imageKey = f"{pathImage}/extras/{imageName}"
                        image = {
                            "key": keyI, "url": f"https://{bucketName}.s3.amazonaws.com/{imageKey}"}
                        newArray = imagesObject
                        newArray.append(image)
                        s3.put_object(Body=imageData, Bucket=bucketName, Key=imageKey,
                                      ContentType="image/jpeg", Metadata={"businessid": businessid})
                        put_db_extras(businessid, [json.dumps(
                            objeto) for objeto in newArray])
                    elif type == "profile":
                        # redimensionamos la imagen
                        # Crear miniatura (360x360)
                        thumbnailData = resize_image(
                            BytesIO(original), (360, 360))
                        thumbnailKey = f"{
                            pathImage}/${imageName}_thumbnail.jpg"
                        # crear standar (1024x1024)
                        standardData = resize_image(
                            BytesIO(original), (1024, 1024))
                        standardKey = f"{pathImage}/{imageName}"
                        # se guarda oriifinal y miniatura
                        s3.put_object(Body=thumbnailData, Bucket=bucketName, Key=thumbnailKey,
                                      ContentType="image/jpeg", Metadata={"businessid": businessid})
                        s3.put_object(Body=standardData, Bucket=bucketName, Key=standardKey,
                                      ContentType="image/jpeg", Metadata={"businessid": businessid})

                        thumbnail = f"https://{
                            bucketName}.s3.amazonaws.com/{thumbnailKey}"
                        image = {
                            "key": keyI, "url": f"https://{bucketName}.s3.amazonaws.com/{standardKey}"}
                        print("Objecto que sustituira", image)
                        newArray = imagesObject
                        newArray.append(image)
                        # guardar en base de datos
                        put_db_profile(businessid, [json.dumps(
                            objeto) for objeto in newArray], thumbnail)

                elif action == "update":
                    print("a actualizar algo")

                    # que vamos actualizar
                    if type == "extras":
                        print("es extra la imagen")
                        # redimensionamos la imagen
                        imageData = resize_image(
                            BytesIO(original), (1024, 1024))
                        imageKey = f"{pathImage}/extras/{imageName}"
                        image = {
                            "key": keyI, "url": f"https://{bucketName}.s3.amazonaws.com/{imageKey}"}
                        print("Objecto que sustituira", image)
                        newArray = imagesObject
                        newArray[int(keyI)] = image
                        print(f"arreglo nuevo {newArray}")
                        s3.put_object(Body=imageData, Bucket=bucketName, Key=imageKey,
                                      ContentType="image/jpeg", Metadata={"businessid": businessid})
                        put_db_extras(businessid, [json.dumps(
                            objeto) for objeto in newArray])

                    elif type == "profile":
                        # redimensionamos la imagen
                        # Crear miniatura (360x360)
                        thumbnailData = resize_image(
                            BytesIO(original), (360, 360))
                        thumbnailKey = f"{
                            pathImage}/${imageName}_thumbnail.jpg"
                        # crear standar (1024x1024)
                        standardData = resize_image(
                            BytesIO(original), (1024, 1024))
                        standardKey = f"{pathImage}/{imageName}"
                        # se guarda oriifinal y miniatura
                        s3.put_object(Body=thumbnailData, Bucket=bucketName, Key=thumbnailKey,
                                      ContentType="image/jpeg", Metadata={"businessid": businessid})
                        s3.put_object(Body=standardData, Bucket=bucketName, Key=standardKey,
                                      ContentType="image/jpeg", Metadata={"businessid": businessid})

                        thumbnail = f"https://{
                            bucketName}.s3.amazonaws.com/{thumbnailKey}"
                        image = {
                            "key": keyI, "url": f"https://{bucketName}.s3.amazonaws.com/{standardKey}"}
                        print("Objecto que sustituira", image)
                        newArray = imagesObject
                        newArray[int(keyI)] = image
                        # guardar en base de datos
                        put_db_profile(businessid, [json.dumps(
                            objeto) for objeto in newArray], thumbnail)
                return
            else:
                print("No esta dentro de un incoming")
                continue

    except Exception as e:
        print(f"Error: {e}")
    # end try

    body = {
        "message": "Go Serverless v3.0! Your function executed successfully!",
        "input": event,
    }

    return {"statusCode": 200, "body": json.dumps(body)}
