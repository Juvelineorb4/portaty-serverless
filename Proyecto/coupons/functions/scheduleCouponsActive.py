import os
import json
from datetime import datetime, timedelta, timezone
import requests

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

# Query para listar las campañas activas cuyo endDate fue ayer
list_coupon_campaigns_to_expire = """
    query ListCouponCampaigns($filter: ModelCouponCampaignFilterInput) {
        listCouponCampaigns(filter: $filter) {
            items {
                id
                endDate
                status
                __typename
            }
            nextToken
        }
    }
"""

# Mutation para actualizar el estado de la campaña a EXPIRED
mutation_update_campaign_status = """
   mutation UpdateCouponCampaign($input: UpdateCouponCampaignInput!) {
       updateCouponCampaign(input: $input) {
           id
           status
           __typename
       }
   }
"""

# Obtener el rango de fecha para el día de ayer
def get_yesterday_range():
    # Obtener el inicio del día de ayer
    fecha_ayer = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) - timedelta(days=1)
    fecha_ayer_str = fecha_ayer.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Obtener el final del día de ayer
    final_ayer = (fecha_ayer + timedelta(days=1)) - timedelta(seconds=1)
    final_ayer_str = final_ayer.strftime('%Y-%m-%dT%H:%M:%SZ')

    return fecha_ayer_str, final_ayer_str

# Función para consultar campañas activas con endDate de ayer
def get_coupon_campaigns_to_expire(yesterday, yesterday_final):
    campaigns = []
    next_token = None

    while True:
        variables = {
            "filter": {
                "and": [
                    {"status": {"eq": "ACTIVE"}},
                    {"endDate": {"between": [yesterday, yesterday_final]}}
                ]
            },
            "nextToken": next_token
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": appsync_api_key
        }

        response = requests.post(
            appsync_api_url,
            json={"query": list_coupon_campaigns_to_expire, "variables": variables},
            headers=headers,
        )
        data = response.json()["data"]["listCouponCampaigns"]
        campaigns.extend(data["items"])

        next_token = data.get("nextToken")
        if not next_token:
            break

    return campaigns

# Función para actualizar el estado de la campaña a EXPIRED
def update_campaign_status(campaign_id):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }
    variables = {
        "input": {
            "id": campaign_id,
            "status": "FINALIZED"
        }
    }
    response = requests.post(
        appsync_api_url,
        json={"query": mutation_update_campaign_status, "variables": variables},
        headers=headers
    )
    return response.json()

# Handler principal para la función Lambda programada
def handler(event, context):
    # Obtener el inicio y final del día de ayer para el filtro
    date_yesterday, date_yesterday_final = get_yesterday_range()
    
    try:
        print("Inicio del día de ayer:", date_yesterday)
        print("Final del día de ayer:", date_yesterday_final)
        
        # Buscar las campañas activas con fecha de finalización ayer
        campaigns = get_coupon_campaigns_to_expire(date_yesterday, date_yesterday_final)
        print("Campañas encontradas para expirar:", campaigns)
        
        # Expirar cada campaña que cumpla el criterio
        for campaign in campaigns:
            campaign_id = campaign["id"]
            print(f"Expirando campaña {campaign_id}")
            update_result = update_campaign_status(campaign_id)
            if "errors" in update_result:
                print(f"Error al expirar la campaña {campaign_id}: {update_result['errors']}")
            else:
                print(f"Campaña {campaign_id} expirada con éxito")

        return "Proceso de expiración de campañas completado"
    except Exception as e:
        message_error = str(e)
        print("Error al expirar las campañas:", message_error)
        return f"Error al expirar las campañas: {message_error}"
