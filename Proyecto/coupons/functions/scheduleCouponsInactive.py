import os
import json
from datetime import datetime, timedelta, timezone
import requests

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

# Query para listar las campañas de cupones no activas con fecha de inicio hoy
list_coupon_campaigns = """
    query ListCouponCampaigns($filter: ModelCouponCampaignFilterInput) {
        listCouponCampaigns(filter: $filter) {
            items {
                id
                startDate
                status
                __typename
            }
            nextToken
        }
    }
"""

# Mutation para actualizar el estado de la campaña a ACTIVE
mutation_update_campaign_status = """
   mutation UpdateCouponCampaign($input: UpdateCouponCampaignInput!) {
       updateCouponCampaign(input: $input) {
           id
           status
           __typename
       }
   }
"""

# Obtener el rango de fechas para el inicio y final del día de hoy
def get_today_range():
    fecha_actual = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    fecha_actual_str = fecha_actual.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    final_dia = (fecha_actual + timedelta(days=1)) - timedelta(seconds=1)
    final_dia_str = final_dia.strftime('%Y-%m-%dT%H:%M:%SZ')

    return fecha_actual_str, final_dia_str

# Función para consultar campañas no activas con startDate de hoy
def get_coupon_campaigns_today(today, today_final):
    campaigns = []
    next_token = None

    while True:
        variables = {
            "filter": {
                "and": [
                    {"status": {"eq": "INACTIVE"}},
                    {"startDate": {"between": [today, today_final]}}
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
            json={"query": list_coupon_campaigns, "variables": variables},
            headers=headers,
        )
        data = response.json()["data"]["listCouponCampaigns"]
        campaigns.extend(data["items"])

        next_token = data.get("nextToken")
        if not next_token:
            break

    return campaigns

# Función para actualizar el estado de la campaña a ACTIVE
def update_campaign_status(campaign_id):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }
    variables = {
        "input": {
            "id": campaign_id,
            "status": "ACTIVE"
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
    # Obtener el inicio y final del día para el rango de fechas en el filtro
    date_today, date_today_final = get_today_range()
    
    try:
        print("Fecha actual:", date_today)
        print("Final del día:", date_today_final)
        
        # Buscar las campañas con fecha de inicio hoy
        campaigns = get_coupon_campaigns_today(date_today, date_today_final)
        print("Campañas encontradas:", campaigns)
        
        # Activar cada campaña que cumpla el criterio
        for campaign in campaigns:
            campaign_id = campaign["id"]
            print(f"Activando campaña {campaign_id}")
            update_result = update_campaign_status(campaign_id)
            if "errors" in update_result:
                print(f"Error al activar la campaña {campaign_id}: {update_result['errors']}")
            else:
                print(f"Campaña {campaign_id} activada con éxito")

        return "Proceso de activación de campañas completado"
    except Exception as e:
        message_error = str(e)
        print("Error al activar las campañas:", message_error)
        return f"Error al activar las campañas: {message_error}"
