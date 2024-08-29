import json
import os
import boto3
from datetime import datetime

# Variables 
region = os.environ.get("AWS_REGION")
cognito = boto3.client('cognito-idp', region_name=region)
user_pool_id = os.environ.get("USER_POOL_ID")

def handler(event, context):
    print("EVENTO: ", event)
    params = event.get("queryStringParameters", {})
    print("PARAMS: ", params)
    limit = int(params.get("limit", 0))
    nextToken = params.get("nextToken", None)  # Obtiene el nextToken de los parámetros de consulta

    if limit == 0:
        return {'statusCode': 400, "body": json.dumps({
                "success": False,
                "message": "El parámetro 'limit' no puede ser cero"
        })}
        
    try:
        # Lista para almacenar los usuarios
        users_list = []

        # Token de paginación para la próxima consulta
        next_pagination_token = None

        # Prepara los argumentos para la llamada a list_users
        list_users_args = {
            "UserPoolId": user_pool_id,
            "Limit": limit  # Ajusta este valor según sea necesario
        }
        
        if nextToken:  # Si se proporcionó un nextToken, inclúyelo en los argumentos
            list_users_args["PaginationToken"] = nextToken

        # Llama a la función list_users con los argumentos preparados
        response = cognito.list_users(**list_users_args)
    
        # Agrega los usuarios a la lista y transforma los atributos
        for user in response['Users']:
            # Crea un nuevo diccionario para almacenar la información del usuario
            user_info = {
                'Username': user['Username'],
                'UserStatus': user['UserStatus'],
                'UserCreateDate': datetime.strftime(user['UserCreateDate'], '%Y-%m-%d %H:%M:%S'),
                'UserLastModifiedDate': datetime.strftime(user['UserLastModifiedDate'], '%Y-%m-%d %H:%M:%S') if 'UserLastModifiedDate' in user else None,
                'Enabled': user['Enabled']
            }
            
            # Agrega cada atributo al diccionario del usuario
            for attribute in user['Attributes']:
                user_info[attribute['Name']] = attribute['Value']
            
            users_list.append(user_info)

        # Guarda el token de paginación si hay más usuarios
        next_pagination_token = response.get('PaginationToken', None)

        # Ordena los usuarios por la fecha de creación
        sorted_users_list = sorted(users_list, key=lambda x: x['UserCreateDate'])

        return {
            'statusCode': 200,
            "body": json.dumps({
                "success": True,
                "message": "Usuarios obtenidos con éxito",
                "data": sorted_users_list,
                "nextToken": next_pagination_token  # Incluye el token de paginación en la respuesta
            })
        }
    except Exception as e:
        error_message = str(e)
        return {'statusCode': 500, "body": json.dumps({
            "success": False,
            "message": "Error al obtener los usuarios",
            "error": error_message
        })}

# Ejemplo de uso:
# Suponiendo que esta función se invoca a través de un evento API Gateway con queryStringParameters 'limit' y opcionalmente 'nextToken'
