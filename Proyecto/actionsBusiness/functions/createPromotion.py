import boto3
import requests
import os
import json
from datetime import datetime

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

def get_user_table(id):
    # Definir la mutación de GraphQL para obtener usuarios
    query = """
        query getUsers($id: ID!) {
            getUsers(id: $id) {
                id
                cognitoID
            }
        }
    """

    variables = {"id": id}

    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    response = requests.post(
        appsync_api_url,
        json={"query": query, "variables": variables},
        headers=headers,
    )

    return response.json()["data"]["getUsers"]

def handler(event, context):
    print("EVENTO: ", event)
    try:
        # Procesa cada registro del evento
        for record in event['Records']:
            print("RECORD: ", record)
            message_body = record['body']
            params = json.loads(message_body)
            print(f'Mensaje recibido: {message_body}')
            print(params)

            # Convertir las fechas a formato ISO 8601
            params['dateInitial'] = datetime.strptime(params['dateInitial'], '%Y-%m-%d').isoformat() + 'Z'
            params['dateFinal'] = datetime.strptime(params['dateFinal'], '%Y-%m-%d').isoformat() + 'Z'

            print("Parámetros con fechas ISO 8601: ", params)

            # Obtener el usuario correspondiente al ID
            user = get_user_table(params["userID"])
            print("USER:", user)
            params["owner"] = user["cognitoID"]

            # Comparar fechaInicial con la fecha actual
            dateInitial_obj = datetime.strptime(params['dateInitial'], '%Y-%m-%dT%H:%M:%SZ').date()
            now_date_obj = datetime.now().date()

            if dateInitial_obj == now_date_obj:
                params["status"] = "PUBLISHED"

            # Definir la mutación de GraphQL para crear la promoción
            mutation = """
                mutation CreateBusinessPromotion($input: CreateBusinessPromotionInput!) {
                    createBusinessPromotion(input: $input) {
                        id
                        userID
                        businessID
                        title
                        dateInitial
                        dateFinal
                        status
                        isView
                        image
                        owner
                    }
                }
            """

            variables = {
                "input": params
            }

            headers = {
                "Content-Type": "application/json",
                "x-api-key": appsync_api_key
            }

            response = requests.post(
                appsync_api_url,
                json={"query": mutation, "variables": variables},
                headers=headers,
            )

            print("AppSync Response: ", response.json())

        return 'Procesamiento exitoso'

    except Exception as e:
        print(f'Error al procesar el mensaje: {e}')
        raise e
