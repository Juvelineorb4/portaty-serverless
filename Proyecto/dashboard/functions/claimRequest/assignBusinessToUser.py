import json
import os
import requests

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

# Mutations and queries
getClaimRequest = """
    query GetClaimRequest($id: ID!) {
    getClaimRequest(id: $id) {
      id
      status
    }
  }
"""

getUser = """
    query GetUsers($id: ID!) {
        getUsers(id: $id) {
            id
            cognitoID
            business {
                items {
                    id
                }
            }
        }
    }
"""

getBusiness = """
    query GetBusiness($id: ID!) {
        getBusiness(id: $id) {
            id
            userID
        }
    }
"""

updateBusiness = """
   mutation UpdateBusiness(
    $input: UpdateBusinessInput!
    $condition: ModelBusinessConditionInput
  ) {
    updateBusiness(input: $input, condition: $condition) {
      id
      userID
      owner
    }
  }
"""

updateClaimRequest = """
   mutation UpdateClaimRequest(
    $input: UpdateClaimRequestInput!
    $condition: ModelClaimRequestConditionInput
  ) {
    updateClaimRequest(input: $input, condition: $condition) {
      id
      businessID
      userID
      status
      adminResponse
      createdAt
      updatedAt
      owner
    }
  }
"""

onlyStatus = ["ACCEPTED", "REJECTED"]

# Main handler
def handler(event, context):
    print("EVENT:", event)
    # Validar si no hay body en el evento
    if not event.get('body'):
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "Faltan datos necesarios, el body está vacío"
            })
        }
    body = json.loads(event['body'])
    print("BODY:", body)
    
    try:
        # Validar que existan las variables necesarias
        data = json.loads(body.get("data"))
        print("DATA: ", data)
        status = data.get("status", None)
        user_id = data.get("userID", None)
        business_id = data.get("businessID", None)
        claim_id = data.get("claimID", None)
        print(f'{status} {user_id} {claim_id} {business_id}')
        if not data or not status or not user_id or not business_id or not claim_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "Faltan datos necesarios para procesar la solicitud"
                })
            }
        
        

        # Paso 1: Consultar el estado del claim
        claim = get_claim_status(claim_id)
        if not claim:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    "success": False,
                    "message": "No se encontró la solicitud de reclamo"
                })
            }

        current_status = claim.get("status")

        # Si el estado actual es REJECTED o ACCEPTED, no hacer nada
        if current_status in onlyStatus:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    "success": False,
                    "message": f"La solicitud ya fue atendida con el estado: {current_status}"
                })
            }

        # Paso 2: Si el estado es PENDING, procesar la solicitud
        if current_status == "PENDING":
            if status == "REJECTED":
                # Actualizar el claim a REJECTED
                update_claim_request(claim_id, status)
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        "success": True,
                        "message": "La solicitud fue rechazada"
                    })
                }
            elif status == "ACCEPTED":
                # Validación adicional 1: Verificar que el negocio no tenga userID asignado
                business = get_business(business_id)
                if not business or business.get("userID"):
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            "success": False,
                            "message": "El negocio ya tiene un usuario asignado"
                        })
                    }

                # Validación adicional 2: Verificar que el usuario no tenga negocios asignados
                user = get_user_businesses(user_id)
                # Si el arreglo de items no está vacío, significa que el usuario ya tiene un negocio
                if user and user.get("business", {}).get("items", []):
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            "success": False,
                            "message": "El usuario ya tiene un negocio asignado"
                        })
                    }

                # Si pasa las validaciones, actualizar el negocio con el nuevo userID y el estado del claim
                update_business_owner(business_id, user_id, user.get("cognitoID"))
                update_claim_request(claim_id, status)
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        "success": True,
                        "message": "La solicitud fue aceptada y el negocio actualizado"
                    })
                }

        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "Estado inválido para la solicitud"
            })
        }

    except Exception as e:
        message_error = str(e)
        print("ERROR:", message_error)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al procesar la solicitud",
                "error": message_error
            })
        }

# Función para obtener el estado de una solicitud de reclamo
def get_claim_status(claim_id):
    query = getClaimRequest
    variables = {"id": claim_id}
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    try:
        response = requests.post(
            appsync_api_url,
            json={"query": query, "variables": variables},
            headers=headers
        )
        response_data = response.json()
        if "errors" in response_data:
            print(f"Error en la consulta de GraphQL: {response_data['errors']}")
            return None
        return response_data["data"]["getClaimRequest"]
    except Exception as e:
        print(f"Error al consultar AppSync: {e}")
        return None

# Función para obtener los negocios asignados a un usuario
def get_user_businesses(user_id):
    query = getUser
    variables = {"id": user_id}
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    try:
        response = requests.post(
            appsync_api_url,
            json={"query": query, "variables": variables},
            headers=headers
        )
        response_data = response.json()
        print("get_user_businesses",  response_data)
        if "errors" in response_data:
            print(f"Error en la consulta de GraphQL: {response_data['errors']}")
            return None
        return response_data["data"]["getUsers"]
    except Exception as e:
        print(f"Error al consultar AppSync: {e}")
        return None

# Función para obtener los detalles del negocio
def get_business(business_id):
    query = getBusiness
    variables = {"id": business_id}
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    try:
        response = requests.post(
            appsync_api_url,
            json={"query": query, "variables": variables},
            headers=headers
        )
        response_data = response.json()
        print("get_business",  response_data)
        if "errors" in response_data:
            print(f"Error en la consulta de GraphQL: {response_data['errors']}")
            return None
        return response_data["data"]["getBusiness"]
    except Exception as e:
        print(f"Error al consultar AppSync: {e}")
        return None

# Función para actualizar el propietario de un negocio
def update_business_owner(business_id, user_id, owner):
    mutation = updateBusiness
    variables = {
        "input": {
            "id": business_id,
            "userID": user_id,
            "owner": owner,
            "statusOwner": "ASSIGNED"
        }
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    try:
        response = requests.post(
            appsync_api_url,
            json={"query": mutation, "variables": variables},
            headers=headers
        )
        print("update_business_owner", response.json())
        print("Negocio actualizado")
    except Exception as e:
        print(f"Error al actualizar el negocio: {e}")

# Función para actualizar el estado de una solicitud de reclamo
def update_claim_request(claim_id, status):
    mutation = updateClaimRequest
    variables = {
        "input": {
            "id": claim_id,
            "status": status
        }
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    try:
        response = requests.post(
            appsync_api_url,
            json={"query": mutation, "variables": variables},
            headers=headers
        )
        print("Claim Request Actualizado",  response.json())
    except Exception as e:
        print(f"Error al actualizar la solicitud de reclamo: {e}")
