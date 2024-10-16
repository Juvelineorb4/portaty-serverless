import boto3
import json
import requests
from requests_aws4auth import AWS4Auth
import os
from datetime import datetime, timedelta, timezone

# Configuración inicial
region = os.environ.get("AWS_REGION")
service = "es"
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

host = os.environ.get("OPENSE_ENDPONIT")
index_business = os.environ.get("OPENSE_INDEX")  # Cambiar a tu índice de negocios
url_business = f"{host}/{index_business}/_search"

# Cliente S3 para obtener el geojson del país (si es necesario)
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

# Función Lambda principal
def handler(event, context):
    try:
        # Obtener los parámetros de la solicitud
        params = event.get("queryStringParameters", {})
        print("PARAMS: ", params)
        period = params.get("range", "12M")  # Puede ser '7d', '30d', '12M'
        country = params.get("country", None)  # Campo opcional de país

        # Calcular las fechas basadas en el periodo seleccionado
        current_date = datetime.now(timezone.utc)
        end_date = current_date.strftime('%Y-%m-%dT23:59:59Z')  # Fecha actual (hoy)
        calendar_interval = "day"
        calendar_format = "yyyy-MM-dd"
        if period == "7D":
            start_date = (current_date - timedelta(days=6)).strftime('%Y-%m-%dT00:00:00Z')
            min_date = (current_date - timedelta(days=6)).strftime('%Y-%m-%d')
            max_date = current_date.strftime('%Y-%m-%d')
            message = "Últimos 7 días de negocios obtenidos con éxito."
        elif period == "30D":
            start_date = (current_date - timedelta(days=29)).strftime('%Y-%m-%dT00:00:00Z')
            min_date = (current_date - timedelta(days=29)).strftime('%Y-%m-%d')
            max_date = current_date.strftime('%Y-%m-%d')
            message = "Últimos 30 días de negocios obtenidos con éxito."
        else:  # Asumimos que el periodo es '12M'
            start_date = (current_date - timedelta(days=365)).strftime('%Y-%m-%dT00:00:00Z')
            min_date = current_date - timedelta(days=365)

            # Sumamos un mes, manejando el cambio de año si es necesario
            year = min_date.year
            month = min_date.month + 1

            if month > 12:
                month = 1
                year += 1

            # Formateamos la fecha con el mes corregido
            min_date = f"{year}-{month:02d}"
            print(min_date)
            max_date = current_date.strftime('%Y-%m')
            message = "Últimos 12 meses de negocios obtenidos con éxito."
            calendar_interval = "month"
            calendar_format = "yyyy-MM"

        print("TIME NOW: ", current_date)
        print("TIME START: ", start_date)
        print("TIME END: ", end_date)
        print("TIME MIN: ", min_date)
        print("TIME MAX: ", max_date)

        # Construcción del query basado en las fechas calculadas
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {
                            "range": {
                                "createdAt": {  # Cambia 'createdAt' si el campo es diferente para negocios
                                    "gte": start_date,
                                    "lt": end_date
                                }
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "business_per_period": {
                    "date_histogram": {
                        "field": "createdAt",  # Cambia 'createdAt' si es diferente para negocios
                        "calendar_interval": calendar_interval,  # Intervalo diario o mensual
                        "format": calendar_format,
                        "min_doc_count": 0,  # Asegura que se incluyan días sin documentos
                        "extended_bounds": {
                            "min": min_date,
                            "max": max_date
                        }
                    }
                }
            }
        }

        # Si se proporciona el parámetro 'country', agregar el filtro geo_polygon
        if country:
            polygon_coordinates = get_country_polygon(country)
            if not polygon_coordinates:
                return error_response(f"No se pudo obtener el polígono del país {country}.")
            
            # Añadir el filtro geo_polygon al query
            query["query"]["bool"]["filter"] = [
                {
                    "geo_polygon": {
                        "coordinates": {  # Asegúrate de que el campo 'location' sea correcto para los negocios
                            "points": polygon_coordinates[0]  # Usar el primer conjunto de coordenadas del polígono
                        }
                    }
                }
            ]

        # Realizar la consulta en OpenSearch
        headers = {"Content-Type": "application/json"}
        print("QUERY OPENSE: ", query)
        r = requests.get(url_business, auth=awsauth, headers=headers, data=json.dumps(query))

        # Procesar la respuesta
        response_data = json.loads(r.text)
        print("RESPUESTA OPENSE: ", response_data)
        total_items = response_data['hits']['total']['value']
        buckets = response_data["aggregations"]["business_per_period"]["buckets"]

        # Formatear los resultados para devolverlos
        results = [{"date": bucket["key_as_string"], "registros": bucket["doc_count"]} for bucket in buckets]
        body = {
                "success": True,
                "message": message,  # Mensaje específico según el rango
                "data": results,
                'total': total_items
            }
        print("BODY: ", body)
        # Retornar éxito con los datos obtenidos, incluyendo el mensaje específico
        return {
            'statusCode': 200,
            'body': json.dumps(body)
        }

    except Exception as e:
        # Manejo de error
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error obteniendo datos para la gráfica.",
                "error": str(e)
            })
        }

# Función para obtener geo.json del S3 con el polígono del país
def get_country_polygon(country_code):
    try:
        file_key = f"public/countries/{country_code}.geo.json"
        response = s3.get_object(Bucket=bucketName, Key=file_key)
        geojson_data = json.loads(response['Body'].read().decode('utf-8'))
        coordinates = geojson_data["features"][0]["geometry"]["coordinates"]
        return coordinates
    except Exception as e:
        print(f"Error obteniendo el geojson del país: {str(e)}")
        return None

# Función para construir la respuesta de error
def error_response(message):
    return {
        'statusCode': 400,
        'body': json.dumps({
            "success": False,
            "message": message
        })
    }
