import json
import boto3
from botocore.exceptions import ClientError
import requests
# Cliente de IAM
iam = boto3.client('iam')

# Constantes para la respuesta de CloudFormation
SUCCESS = "SUCCESS"
FAILED = "FAILED"

def lambda_handler(event, context):
    try:
        # Extraer el tipo de solicitud (Create, Update, Delete)
        request_type = event['RequestType']
        # Obtener nombres de roles y pool de identidad desde las propiedades del recurso
        auth_role_name = event['ResourceProperties']['authRoleName']
        unauth_role_name = event['ResourceProperties']['unauthRoleName']
        identity_pool_id = event['ResourceProperties']['identityPoolId']
        
        # Define la política de asunción de rol
        def assume_role_policy(aud, amr):
            return {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Federated": "cognito-identity.amazonaws.com"},
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {"cognito-identity.amazonaws.com:aud": aud},
                        "ForAnyValue:StringLike": {"cognito-identity.amazonaws.com:amr": amr}
                    }
                }]
            }

        # En caso de eliminación
        if request_type == 'Delete':
            deny_policy = assume_role_policy(identity_pool_id, "unauthenticated")
            deny_policy["Statement"][0]["Effect"] = "Deny"
            update_role_policy(auth_role_name, deny_policy)
            update_role_policy(unauth_role_name, deny_policy)
        else:
            # En caso de creación o actualización, aplicar la política de permiso
            auth_policy = assume_role_policy(identity_pool_id, "authenticated")
            unauth_policy = assume_role_policy(identity_pool_id, "unauthenticated")
            update_role_policy(auth_role_name, auth_policy)
            update_role_policy(unauth_role_name, unauth_policy)

        # Respuesta de éxito a CloudFormation
        send(event, context, SUCCESS, {})
    except ClientError as e:
        print(f"Error updating role policies: {e}")
        send(event, context, FAILED, {"error": str(e)})

# Función para actualizar la política de asunción de rol
def update_role_policy(role_name, policy):
    iam.update_assume_role_policy(
        RoleName=role_name,
        PolicyDocument=json.dumps(policy)
    )

# Enviar respuesta a CloudFormation
def send(event, context, response_status, response_data):
    response_url = event['ResponseURL']
    response_body = json.dumps({
        "Status": response_status,
        "Reason": f"See the details in CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": context.log_stream_name,
        "StackId": event['StackId'],
        "RequestId": event['RequestId'],
        "LogicalResourceId": event['LogicalResourceId'],
        "Data": response_data
    })

    headers = {
        'content-type': '',
        'content-length': str(len(response_body))
    }

    try:
        # Realizar solicitud HTTP a la URL de respuesta
        response = requests.put(response_url, data=response_body, headers=headers)
        print(f"Response status: {response.status_code}")
    except Exception as e:
        print(f"Error sending response to CloudFormation: {e}")
