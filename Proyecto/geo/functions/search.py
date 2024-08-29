import json
import boto3
import os

AWS_REGION = os.environ.get("AWS_REGION")
PLACE_INDEX = os.environ.get("PLACE_INDEX_NAME")
client = boto3.client('location', region_name=AWS_REGION)
def handler(event, context):
    print("EVENTO: ", event)
    print("PARAMS: ",event['queryStringParameters'] )
    text = event['queryStringParameters']['text']  # El texto para la búsqueda predictiva
    text = text
    location = json.loads(event['queryStringParameters']['location'])
    latitude = location.get("latitude", "")
    longitude = location.get("longitude", "")
    max_results = 3  # El número máximo de resultados a devolver
    user_location = [longitude, latitude]
    try:
        response = client.search_place_index_for_suggestions(
            IndexName=PLACE_INDEX,
            Text=text,
            MaxResults=5,
            BiasPosition= user_location
        )
        print("RESULTS: ", response["Results"])
        data = []
        for result in response["Results"]:
            print("RESULT: ", result)
            placeID = result.get("PlaceId", "")
            if placeID == "" : continue
            place = client.get_place(
                IndexName=PLACE_INDEX,
                PlaceId=result["PlaceId"]
            )
            texto = str(place["Place"]["Label"]).split(',', 1)
            label = texto[0].strip()
            sublabel = texto[1].strip() if len(texto) > 1 else ""  # Si no hay coma,
            data.append({
                "Label":label,
                "SubLabel": sublabel,
                "Point": place["Place"]["Geometry"]["Point"]
            })


        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "data": data,
                "message": "Resultados de busqueda obtenido con exito"
            })
        }
    except Exception as e:
        print(e)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                'message': 'Ocurrió un error al realizar la búsqueda de texto predictivo',
                'error': str(e),
            })
        }