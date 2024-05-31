import json
import boto3
from PIL import Image
from io import BytesIO
import base64
import random
from datetime import datetime, timezone
import os




AWS_REGION = "us-east-1"
s3 = boto3.client("s3", region_name=AWS_REGION)
db = boto3.client("dynamodb", region_name=AWS_REGION)
bucketName = os.environ.get("S3_BUCKET_NAME")
tableNameDB= os.environ.get("TABLE_BUSINESS_NAME")
imageExtra = []
def resize_image(image, size):
    img = Image.open(image)
    img.thumbnail(size)
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return buffered.getvalue()

def put_db_profile(tableID, images, thumbnail=None):
     print("THUMBANIL", thumbnail)
     print(thumbnail == None)
     if thumbnail != None :
        resultDB =db.update_item(
            TableName= tableNameDB,
            Key={ 'id': {'S': tableID}},
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
     else:
        print("SIN THUMBANIL")
        resultDB =db.update_item(
            TableName= tableNameDB,
            Key={ 'id': {'S': tableID}},
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
        Key={ 'id': {'S': id} },
        ProjectionExpression='id, images'
    )
    if "Item" in response:
        item = response['Item']
        print(f"Elemento encontrado: {item}")
        return item
    else:
        return None

def put_db_extras(tableID, images):
    resultDB =db.update_item(
        TableName=tableNameDB,
        Key={ 'id': {'S': tableID}},
        UpdateExpression='SET #images = :images',
        ExpressionAttributeNames={
            '#images': 'images',
        },
        ExpressionAttributeValues={
           ':images': {'L': [{'S': item} for item in images] },
        },
        ReturnValues='UPDATED_NEW'
     )
    return resultDB
def deleteObject(arrayObj, key):
    newArray = arrayObj
    # Buscar el objeto con la clave a eliminar
    objeto_eliminado = None
    for objeto in newArray:
        if objeto['key'] == key:
            objeto_eliminado = objeto
            break

    # Si encontramos el objeto con la clave a eliminar, procedemos
    if objeto_eliminado:
        # Eliminar el objeto del arreglo
        newArray.remove(objeto_eliminado)

        # Actualizar las claves para los elementos restantes
        for indice, objeto_actualizado in enumerate(newArray):
            objeto_actualizado['key'] = indice
    return newArray
def getDateIso():
    # Obtener la fecha y hora actual en formato UTC
    fechaUTC = datetime.now(timezone.utc)

    # Formatear la fecha en formato ISO 8601 hasta los minutos
    fechaIso8601 = fechaUTC.strftime('%Y-%m-%dT%H:%M') + 'Z'

    return fechaIso8601
def thumbnail(event, context):
    body = json.loads(event['body'])
    print("BODY:", body)
    try:    
            #Obtenemos los datos su puestos
            action = body.get("action")
            typeF = body.get("type")
            imageb64 = body.get("image")
            identityid = body.get("identityid")
            businessid = body.get("businessid")
            key = body.get("key")
            description = body.get("description", "")

            #buscamos el negocio para obtener el array de images 
            business =  get_db(businessid)
            if business is None: return print("Elemento no encontrado")
            # arreglo de images
            imagesArray = business.get("images", {}).get("L", [])
            # Deserializar los strings JSON en objetos Python
            imagesObject = [json.loads(image['S']) for image in imagesArray]
            # Ordenar la lista por el valor de 'key'
            imagesObject = sorted(imagesObject, key=lambda x: int(x['key']))

            if action == "delete":
                path = body.get("path")
                newArray = deleteObject(imagesObject, key)
                put_db_extras(businessid, [json.dumps(objeto) for objeto in newArray])
                s3.delete_object(Bucket=bucketName, Key=path)
                response = {
                    "statusCode": 200,
                    "body": json.dumps("IMAGEN ELIMINADA CORRECTAMENTE")
                }
                return response


            # Decodifica la imagen base64
            imageData = ""
            originalData = ""
            if imageb64 != "" :  
                imageData = base64.b64decode(imageb64)
                originalData = resize_image(BytesIO(imageData), (1024, 1024))
                print("IMAGEN ORIGINAL: ",originalData)
            if action == "create":
                if typeF == "profile":
                    originalKey = f"protected/{identityid}/business/{businessid}/profile.jpg"
                    thumbnailData = resize_image(BytesIO(originalData), (1024, 1024))
                    thumbnailKey = f"protected/{identityid}/business/{businessid}/profile_thumbnail.jpg"
                    s3.put_object(Body=originalData, Bucket=bucketName, Key=originalKey, ContentType="image/jpeg", Metadata={"businessid": businessid})
                    s3.put_object(Body=thumbnailData, Bucket=bucketName, Key=thumbnailKey, ContentType="image/jpeg", Metadata={"businessid": businessid})

                    thumbnail = f"https://{bucketName}.s3.amazonaws.com/{thumbnailKey}"
                    date = getDateIso()
                    image = {"key": key, "url":f"https://{bucketName}.s3.amazonaws.com/{originalKey}", "description": description, "businessid": businessid, "date": date }
                    newArray = imagesObject
                    newArray.append(image)
                    # guardar en base de datos
                    put_db_profile(businessid, [json.dumps(objeto) for objeto in newArray], thumbnail)   
                elif typeF == "extras":
                    numRan = random.randrange(100000, 999999)
                    originalKey = f"protected/{identityid}/business/{businessid}/extras/image_{numRan}.jpg"
                    date = getDateIso()
                    imageJson = {"key": key, "url":f"https://{bucketName}.s3.amazonaws.com/{originalKey}", "description": description, "businessid": businessid, "date": date }
                    newArray = imagesObject
                    newArray.append(imageJson)
                    s3.put_object(Body=originalData, Bucket=bucketName, Key=originalKey, ContentType="image/jpeg", Metadata={"businessid": businessid})
                    put_db_extras(businessid, [json.dumps(objeto) for objeto in newArray])
            elif action == "update":
                if typeF == "profile":
                    if originalData != "":
                        numRan = random.randrange(100000, 999999)
                        originalKey = f"protected/{identityid}/business/{businessid}/profile_{numRan}.jpg"
                        thumbnailData = resize_image(BytesIO(originalData), (360, 360))
                        thumbnailKey = f"protected/{identityid}/business/{businessid}/profile_{numRan}_thumbnail.jpg"
            
                        
                        s3.put_object(Body=thumbnailData, Bucket=bucketName, Key=thumbnailKey, ContentType="image/jpeg", Metadata={"businessid": businessid})
                        s3.put_object(Body=originalData, Bucket=bucketName, Key=originalKey, ContentType="image/jpeg", Metadata={"businessid": businessid})

                        thumbnail = f"https://{bucketName}.s3.amazonaws.com/{thumbnailKey}"
                        date = getDateIso()
                        imageJSON = {"key": key, "url":f"https://{bucketName}.s3.amazonaws.com/{originalKey}", "description": description, "businessid": businessid, "date": date }
                        newArray = imagesObject
                        newArray[int(key)] = imageJSON
                        # guardar en base de datos
                        put_db_profile(businessid, [json.dumps(objeto) for objeto in newArray], thumbnail)   
                    else:
                        print("A EDITAR")
                        newArray = imagesObject
                        print("VIEJO", newArray)
                        newArray[int(key)]["description"] = description
                        print("NUEVO", newArray)
                        put_db_profile(businessid, [json.dumps(objeto) for objeto in newArray])

                        
                elif typeF == "extras":
                    if originalData != "":
                        numRan = random.randrange(100000, 999999)
                        originalKey = f"protected/{identityid}/business/{businessid}/image_{numRan}.jpg"
                        date=  getDateIso()
                        imageJSON = {"key": key, "url":f"https://{bucketName}.s3.amazonaws.com/{originalKey}", "description": description, "businessid": businessid, "date": date }   
                        newArray = imagesObject
                        newArray[int(key)] = imageJSON
                        s3.put_object(Body=originalData, Bucket=bucketName, Key=originalKey, ContentType="image/jpeg", Metadata={"businessid": businessid})
                        put_db_extras(businessid, [json.dumps(objeto) for objeto in newArray])
                    else: 
                        print("A EDITAR")
                        newArray = imagesObject
                        print("VIEJO", newArray)
                        newArray[int(key)]["description"] = description
                        print("NUEVO", newArray)
                        put_db_extras(businessid, [json.dumps(objeto) for objeto in newArray])
                 
            response = {
                "statusCode": 200,
                "body": json.dumps("LAMBDA EJECUTADA EXITOSAMENTE")
            }
            return response
    except Exception as e:
            print("ERROR: ", e)
            response = {
                "statusCode": 500,
                "body": json.dumps(e)
            }
            return response
     # end try
  



 
