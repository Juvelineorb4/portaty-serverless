import json
import os
import requests

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

# Queries y Mutations de GraphQL
query_user = """
    query GetUsers($id: ID!) {
        getUsers(id: $id) {
            id
            __typename
        }
    }
"""

query_coupon_campaign = """
   query GetCouponCampaign($id: ID!) {
       getCouponCampaign(id: $id) {
           id
           businessID
           status
           totalQuantity
           redeemedQuantity
           __typename
       }
   }
"""

query_coupon_redemption = """
   query ListCouponsRedemptionByCampaignAndUser(
       $campaignID: ID!,
       $userID: ModelIDKeyConditionInput
   ) {
       listCouponsRedemptionByCampaignAndUser(
           campaignID: $campaignID,
           userID: $userID
       ) {
           items {
               id
               __typename
           }
           __typename
       }
   }
"""

mutation_create_coupon_redemption = """
   mutation CreateCouponRedemption($input: CreateCouponRedemptionInput!) {
       createCouponRedemption(input: $input) {
           id
           campaignID
           userID
           __typename
       }
   }
"""

mutation_update_coupon_campaign = """
   mutation UpdateCouponCampaign($input: UpdateCouponCampaignInput!) {
       updateCouponCampaign(input: $input) {
           id
           status
           redeemedQuantity
           __typename
       }
   }
"""

# Función para realizar consultas a AppSync
def get_db(query, variables):
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
        return response_data["data"]
    except Exception as e:
        print(f"Error al consultar AppSync: {e}")
        return None

# Handler principal
def handler(event, context):
    print("EVENT:", event)
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
        user_id = body.get("userID")
        campaign_id = body.get("campaignID")
        
        # Validación de campos necesarios
        if not user_id or not campaign_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "Faltan datos necesarios para procesar la solicitud"
                })
            }

        # Validar que el usuario existe
        user_data = get_db(query_user, {"id": user_id})
        if not user_data or not user_data.get("getUsers"):
            return {
                'statusCode': 404,
                'body': json.dumps({
                    "success": False,
                    "message": "Usuario no encontrado"
                })
            }

        # Validar que la campaña del cupón existe y está activa
        campaign_data = get_db(query_coupon_campaign, {"id": campaign_id})
        campaign = campaign_data.get("getCouponCampaign") if campaign_data else None
        if not campaign or campaign["status"] != "ACTIVE":
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "La campaña no está activa o no existe"
                })
            }

        # Validar si el usuario ya canjeó el cupón
        redemption_data = get_db(query_coupon_redemption, {"campaignID": campaign_id, "userID": {"eq": user_id}})
        if redemption_data and redemption_data.get("listCouponsRedemptionByCampaignAndUser", {}).get("items"):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "El usuario ya ha canjeado este cupón"
                })
            }

        # Crear el registro de canje del cupón
        create_redemption = get_db(mutation_create_coupon_redemption, {
            "input": {
                "campaignID": campaign_id,
                "userID": user_id
            }
        })
        
        if not create_redemption:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al crear el registro de canje"
                })
            }

        # Actualizar redeemedQuantity y verificar si se debe finalizar la campaña
        redeemed_quantity = campaign["redeemedQuantity"] + 1
        update_input = {"id": campaign_id, "redeemedQuantity": redeemed_quantity}
        if redeemed_quantity >= campaign["totalQuantity"]:
            update_input["status"] = "FINALIZED"

        update_campaign = get_db(mutation_update_coupon_campaign, {"input": update_input})
        if not update_campaign:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al actualizar la cantidad de canjes en la campaña"
                })
            }

        # Respuesta de éxito
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Cupón procesado con éxito"
            })
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al escanear el cupón",
                "error": str(e)
            })
        }
