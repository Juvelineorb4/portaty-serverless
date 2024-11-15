import boto3
import os

# Inicializamos el cliente de Cognito
cognito_client = boto3.client('cognito-idp')

# Validación de variables de entorno
try:
    OLD_USER_POOL_ID = os.environ['OLD_COGNITO_USER_POOL_ID']
    OLD_USER_POOL_CLIENT_ID = os.environ['OLD_COGNITO_USER_POOL_CLIENT_ID']
except KeyError as e:
    raise Exception(f"Falta una variable de entorno necesaria: {str(e)}")

def handler(event, context):
    print("EVENT: ", event)
    username = event.get('userName')
    password = event['request'].get('password')

    # Validar que el evento contiene el nombre de usuario y la contraseña
    if not username or not password:
        raise ValueError("Nombre de usuario o contraseña no proporcionados en el evento")

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

        # Almacenar el antiguo sub en el nuevo atributo personalizado custom:oldSub
        old_sub = next(attr['Value'] for attr in user_response['UserAttributes'] if attr['Name'] == 'sub')
        migrated_attributes = [{'Name': key, 'Value': value} for key, value in user_attributes.items()]
        migrated_attributes.append({'Name': 'custom:oldSub', 'Value': old_sub})
        print(f"Old sub almacenado en custom:oldSub: {old_sub}")

        # Confirmar el correo electrónico si existe y está verificado en el User Pool viejo
        if 'email' in user_attributes and 'email_verified' not in user_attributes:
            migrated_attributes.append({'Name': 'email_verified', 'Value': 'true'})

        # Configurar la respuesta de la Lambda para Cognito
        event['response']['userAttributes'] = user_attributes
        event['response']['userAttributes']['email_verified'] = 'true'
        event['response']['userAttributes']['custom:oldSub'] = old_sub
        event['response']['finalUserStatus'] = 'CONFIRMED'
        event['response']['messageAction'] = 'SUPPRESS'
        print("EVENT RESPONSE: ",event['response'] )
        print("Configuración de respuesta completada para Cognito")
        return event
        
    except cognito_client.exceptions.NotAuthorizedException:
        print("Error: Credenciales inválidas para el usuario.")
        raise Exception("Credenciales inválidas.")
    except cognito_client.exceptions.UserNotFoundException:
        print("Error: Usuario no encontrado en el User Pool viejo.")
        raise Exception("Usuario no encontrado.")
    except cognito_client.exceptions.ResourceNotFoundException:
        print("Error: El User Pool o el cliente de User Pool especificado no existe.")
        raise Exception("User Pool o User Pool Client no encontrado.")
    except cognito_client.exceptions.InvalidParameterException as e:
        print(f"Error: Parámetros inválidos - {str(e)}")
        raise Exception("Error en parámetros de autenticación.")
    except Exception as e:
        print(f"Error durante la migración: {str(e)}")
        raise Exception(f"Error inesperado durante la migración: {str(e)}")
