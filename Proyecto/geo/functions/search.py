import json
import boto3
import os

AWS_REGION = os.environ.get("AWS_REGION")
PLACE_INDEX = os.environ.get("PLACE_INDEX_NAME")
client = boto3.client('location', region_name=AWS_REGION)

def handler(event, context):
    print("EVENTO: ", event)
    
    # Validar si los parámetros de consulta existen
    if not event.get('queryStringParameters'):
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "Faltan parámetros de consulta."
            })
        }
    
    # Obtener el texto de búsqueda y la ubicación
    text = event['queryStringParameters'].get('text')
    location_param = event['queryStringParameters'].get('location')
    
    if not text or not location_param:
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "El texto de búsqueda y la ubicación son obligatorios."
            })
        }

    try:
        location = json.loads(location_param)
        latitude = location.get("latitude")
        longitude = location.get("longitude")

        # Validar que se proporcionen la latitud y longitud
        if latitude is None or longitude is None:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    "success": False,
                    "message": "La latitud y longitud son obligatorias en la ubicación."
                })
            }

        # Configurar el máximo de resultados a devolver
        max_results = 5
        user_location = [longitude, latitude]

        # Llamar al servicio para obtener sugerencias basadas en el texto y ubicación del usuario
        response = client.search_place_index_for_suggestions(
            IndexName=PLACE_INDEX,
            Text=text,
            MaxResults=max_results,
            BiasPosition=user_location
        )
        
        # Asegurar que la respuesta contenga resultados
        if 'Results' not in response or len(response['Results']) == 0:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    "success": False,
                    "message": "No se encontraron resultados para la búsqueda."
                })
            }

        # Preparar los datos a devolver
        data = []
        for result in response["Results"]:
            place_id = result.get("PlaceId")
            if not place_id:
                continue  # Ignorar resultados sin PlaceId

            place = client.get_place(
                IndexName=PLACE_INDEX,
                PlaceId=place_id
            )

            # Procesar la etiqueta del lugar
            label_text = str(place["Place"]["Label"]).split(',', 1)
            label = label_text
           

            data.append({
                "Label": label,
                "Point": place["Place"]["Geometry"]["Point"]
            })

        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "data": data,
                "message": "Resultados de búsqueda obtenidos con éxito."
            })
        }

    except client.exceptions.ResourceNotFoundException as e:
        print(f"Error: {e}")
        return {
            'statusCode': 404,
            'body': json.dumps({
                "success": False,
                "message": "El recurso solicitado no fue encontrado.",
                'error': str(e)
            })
        }
    except Exception as e:
        print(f"Error inesperado: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Ocurrió un error al realizar la búsqueda.",
                'error': str(e),
            })
        }
