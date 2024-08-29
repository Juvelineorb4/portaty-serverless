import json
import boto3
import os
import math

AWS_REGION = os.environ.get("AWS_REGION")
print("REGION", AWS_REGION)
db = boto3.resource("dynamodb", region_name=AWS_REGION)
tableNameDB = os.environ.get("TABLE_BUSINESS_COMMENTS_NAME")
tableDB = db.Table(tableNameDB)


def query_db(businessID):
    try:
        response = tableDB.query(
            IndexName='byBusinessComments',  # Reemplaza 'name-index' con el nombre de tu GSI
            KeyConditionExpression=boto3.dynamodb.conditions.Key(
                'businessID').eq(businessID)
        )
        items = response['Items']

        while 'LastEvaluatedKey' in response:
            response = tableDB.query(
                IndexName='byBusinessComments',  # Reemplaza 'name-index' con el nombre de tu GSI
                KeyConditionExpression=boto3.dynamodb.conditions.Key(
                    'businessID').eq(businessID)
            )
            items += response['Items']

        print("RESPONSE QUERY: ", response)
        print(items)

        return items
    except Exception as e:
        print("ERROR IN QUERY_DB: ", str(e))
        raise

# Función para serializar un objeto Python a un objeto DynamoDB JSON


def handler(event, context):
    print("PEPEMEASA")
    print("EVENTO: ", event)
    params = event.get("queryStringParameters", "")
    print("PARAMS: ", params)
    businessID = params.get("businessID", "")
    if businessID == "":
        return {'statusCode': 400,  "body": json.dumps({
                "success": False,
                "message": "No se puede procesar sin id del negocio"
        })}
    try:
        data = query_db(businessID)
        # Inicializar el conteo de estrellas y la suma total
        star_count = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total_sum = 0

        # Contar las estrellas y sumarlas
        for item in data:
            stars = int(item['stars'])
            star_count[stars] += 1
            total_sum += stars

      
        # Calcular el promedio y redondear hacia abajo a un decimal
        if len(data) == 0:
            average = 0
        else:
            average = math.floor((total_sum / len(data)) * 10) / 10
        # Calcular el porcentaje
        if len(data) == 0:
            percentages = {star: 0 for star in star_count}
        else:
            percentages = {star: (count / len(data)) * 100 for star, count in star_count.items()}
        # Calcular el total de valoraciones
        total_ratings = len(data)
        
        # Crear un mensaje personalizado basado en el total de valoraciones
        if total_ratings < 100:
            ratings_message = f"{total_ratings} valoraciones"
        elif total_ratings < 1000:
            ratings_message = "100+ valoraciones"
        else:
            ratings_message = "1000+ valoraciones"
        print({
            'average': average,
            'star_count': star_count,
            'percentages': percentages,
            'total_ratings': total_ratings,
            'ratings_message': ratings_message, 
            'ratings_position': "Nº 14 en Turismo"
        })
        dataResult = {
            'average': average,
            'star_count': star_count,
            'percentages': percentages,
            'total_ratings': total_ratings,
            'ratings_message': ratings_message, 
            'ratings_position': "Nº 14 en Turismo"
        }
        print("DATA BUSINESS: ", data)
        return {'statusCode': 200,  "body": json.dumps({
                "success": True,
                "data": dataResult,
                "message": "Ratings de Negocio consultado con exito"
        })}
    except Exception as e:
        error_message = str(e)
        return {'statusCode': 500,  "body": json.dumps({
            "success": False,
            "message": "Error al consultar las metricas de ratings del Negocio",
            "error": error_message
        })}
