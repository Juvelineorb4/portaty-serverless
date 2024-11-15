import boto3
import json
import os
import requests
import base64
from datetime import datetime, timezone
from dateutil import parser

# Configuración de AppSync y S3
appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")
bucket_name = os.environ.get("S3_BUCKET_NAME")
s3_client = boto3.client("s3")

query_create_coupon_campaign = """
    mutation CreateCouponCampaign(
    $input: CreateCouponCampaignInput!
    $condition: ModelCouponCampaignConditionInput
  ) {
    createCouponCampaign(input: $input, condition: $condition) {
      id
      businessID
      type
      description
      totalQuantity
      startDate
      endDate
      status
      discountValue
      owner
      image
    }
  }
"""

# Campos requeridos para crear la campaña de cupones
required_fields = [
    "businessID", "type", "description", "totalQuantity", 
    "startDate", "endDate", "discountValue", "owner", "image", "identity_id", "terms"
]

# Función para realizar consultas a AppSync
def query_db(query, variables):
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

# Validación de base64
def is_base64_image(data):
    try:
        # Decodifica la imagen base64
        base64.b64decode(data, validate=True)
        return True
    except ValueError:
        return False

# Función para guardar la imagen en S3
def save_image_to_s3(image_data, identity_id, business_id):
    file_name = f"coupons_campaign/campaign_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    file_path = f"protected/{identity_id}/business/{business_id}/{file_name}"
    image_url = f"https://{bucket_name}.s3.amazonaws.com/{file_path}"

    # Decodificar la imagen base64
    image_bytes = base64.b64decode(image_data)
    
    # Subir la imagen a S3
    s3_client.put_object(
        Bucket=bucket_name,
        Key=file_path,
        Body=image_bytes,
        ContentType="image/jpeg",
        ACL="private"
    )
    return image_url

def handler(event, context):
    print("EVENTO: ", event)
    if not event.get('body'):
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "Faltan datos necesarios, el body está vacío"
            })
        }
    body = json.loads(event['body'])
    

    # Validar que todos los campos necesarios estén presentes
    missing_fields = [field for field in required_fields if field not in body or not body[field]]
    if missing_fields:
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": f"Faltan los siguientes campos requeridos: {', '.join(missing_fields)}"
            })
        }

    # Validar que el campo `image` esté en base64
    if not is_base64_image(body["image"]):
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "El campo 'image' no está en un formato base64 válido o no es una imagen."
            })
        }

    # Guardar la imagen en S3 y obtener la URL
    try:
        image_url = save_image_to_s3(body["image"], body["identity_id"], body["businessID"])
    except Exception as e:
        print("Error al guardar la imagen en S3:", e)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al guardar la imagen en S3.",
                "error": str(e)
            })
        }
    start_date_str = body["startDate"]
    start_date = parser.parse(start_date_str).date()
    current_date = datetime.now(timezone.utc).date()
    
    
    # Construir el input para la creación de la campaña de cupones
    coupon_campaign_input = {
        "businessID": body["businessID"],
        "type": body["type"],
        "description": body["description"],
        "totalQuantity": int(body["totalQuantity"]),
        "startDate": body["startDate"],
        "endDate": body["endDate"],
        "discountValue": float(body["discountValue"]),
        "owner": body["owner"],
        "image": image_url,
        "terms": body["terms"]
    }
    print("INPUT Coupons:", coupon_campaign_input)
    
    if start_date == current_date:
        print(f"La campaña comienza hoy. Actualizando estado a ACTIVE.")
        coupon_campaign_input["status"] = "ACTIVE"
    else:
        print(f"La campaña no comienza hoy.")


    try:
        # Llamar a la función query_db para crear la campaña en AppSync
        variables = {"input": coupon_campaign_input}
        result = query_db(query_create_coupon_campaign, variables)
        
        if result is None:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    "success": False,
                    "message": "Error al crear la campaña de cupones."
                })
            }

        # Obtener el resultado de la campaña creada
        created_campaign = result.get("createCouponCampaign", {})

        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Campaña de cupones creada con éxito!",
                "result": created_campaign,
            })
        }
    
    except Exception as e:
        error_message = str(e)
        print("ERROR DE PROMOCIONES: ", error_message)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al crear la campaña de cupones.",
                "error": error_message
            })
        }
