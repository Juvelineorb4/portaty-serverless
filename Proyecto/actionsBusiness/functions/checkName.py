import json
import boto3
import os


AWS_REGION = os.environ.get("AWS_REGION")
print("REGION", AWS_REGION)
db = boto3.resource("dynamodb", region_name=AWS_REGION)
tableNameDB = os.environ.get("TABLE_BUSINESS_NAME")
tableDB = db.Table(tableNameDB)


def query_db(name):
    try:
        response = tableDB.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('name').eq(name)
        )
        items = response['Items']

        while 'LastEvaluatedKey' in response:
            response = tableDB.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr(
                    'name').eq(name),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items += response['Items']

        print("RESPONSE SCAN: ", response)
        print(items)

        return len(items) > 0
    except Exception as e:
        print("ERROR IN QUERY_DB: ", str(e))
        raise

# Función para serializar un objeto Python a un objeto DynamoDB JSON


def handler(event, context):
    print("EVENTO: ", event)
    params = event.get("queryStringParameters", "")
    print("PARAMS: ", params)
    # si params es vacio
    if params == "":
        return {'statusCode': 400,  "body": json.dumps({
            "success": False,
            "message": "No se han proporcionado parametros"
        })}
    businessName = params.get("name", "")
    print("BUSINESS NAME: ", businessName)
    # si no trajo nombre
    if businessName == "":
        return {'statusCode': 400,  "body": json.dumps({
            "success": False,
            "message": "No se han proporcionado nombre"
        })}
    try:
        # buscar nombre dl negocio para ver si existe
        # print(serialize(businessName))
        result = query_db(businessName)
        if result:
            return {'statusCode': 200,  "body": json.dumps({
                "success": True,
                "existing": result,
                "message": "El nombre ya esta en uso."
            })}
        else:
            return {'statusCode': 200,  "body": json.dumps({
                "success": True,
                "existing": result,
                "message": "El nombre esta disponible."
            })}
    except Exception as e:
        error_message = str(e)
        return {'statusCode': 500,  "body": json.dumps({
            "success": False,
            "message": "Error al verificr la existencia del nombre",
            "error": error_message
        })}
