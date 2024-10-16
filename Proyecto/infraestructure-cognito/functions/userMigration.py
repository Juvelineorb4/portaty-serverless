import boto3
import os

# Inicializamos el cliente de Cognito
cognito_client = boto3.client('cognito-idp')

OLD_USER_POOL_ID = os.environ['OLD_COGNITO_USER_POOL_ID']
OLD_USER_POOL_CLIENT_ID = os.environ['OLD_COGNITO_USER_POOL_CLIENT_ID']

def handler(event, context):
    print("EVENT: ", event)
    username = event['userName']
    password = event['request']['password']

    print(f"Intentando autenticar usuario: {username}")

    try:
        # Autenticar al usuario en el User Pool viejo
        auth_response = cognito_client.admin_initiate_auth(
            UserPoolId=OLD_USER_POOL_ID,
            ClientId=OLD_USER_POOL_CLIENT_ID,
            AuthFlow='ADMIN_USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        print("Autenticación exitosa en el User Pool viejo", auth_response)

        # Recuperar detalles del usuario del User Pool viejo
        user_response = cognito_client.admin_get_user(
            UserPoolId=OLD_USER_POOL_ID,
            Username=username
        )
        print(f"Detalles del usuario recuperados: {user_response}")

        # Obtener atributos del usuario y preparar para el nuevo pool, excluyendo 'sub'
        user_attributes = {attr['Name']: attr['Value'] for attr in user_response['UserAttributes'] if attr['Name'] != 'sub'}
        print(f"Atributos del usuario (sin 'sub'): {user_attributes}")

        # Convertir atributos a formato esperado para el nuevo User Pool
        migrated_attributes = [{'Name': key, 'Value': value} for key, value in user_attributes.items()]

        # Confirmar el correo electrónico
        if 'email' in user_attributes:
            migrated_attributes.append({'Name': 'email_verified', 'Value': 'true'})

        # Configurar la respuesta de la Lambda para Cognito
        event['response']['userAttributes'] = user_attributes
        event['response']['userAttributes']['email_verified'] = 'true'
        event['response']['finalUserStatus'] = 'CONFIRMED'
        event['response']['messageAction'] = 'SUPPRESS'

        print("Configuración de respuesta completada para Cognito")
        return event
        
    except cognito_client.exceptions.NotAuthorizedException:
        print("Error: Credenciales inválidas.")
        raise Exception("Credenciales inválidas.")
    except cognito_client.exceptions.UserNotFoundException:
        print("Error: Usuario no encontrado en el User Pool viejo.")
        raise Exception("Usuario no encontrado.")
    except Exception as e:
        print(f"Error durante la migración: {str(e)}")
        raise e
