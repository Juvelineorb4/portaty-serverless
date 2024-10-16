import boto3
import json
import requests
import os

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")
region = os.environ.get("AWS_REGION")

def total_favorites(business_id):
    query = """
    query ListFavorites(
    $filter: ModelFavoritesFilterInput
    $limit: Int
    $nextToken: String
  ) {
    listFavorites(filter: $filter, limit: $limit, nextToken: $nextToken) {
      items {
        id
        businessID
        userID
        position
        owner
        createdAt
        updatedAt
        __typename
      }
      nextToken
      __typename
    }
  }
    """
    
    variables = {
        "filter": {
           "businessID": {"eq": business_id}
        },
        "limit": 100  # Puedes ajustar el límite según sea necesario
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    total_items = []
    next_token = None

    while True:
        if next_token:
            variables["nextToken"] = next_token
        else:
            variables.pop("nextToken", None)

        response = requests.post(
            appsync_api_url,
            json={"query": query, "variables": variables},
            headers=headers,
        )
        
        data = response.json()
        
        if "errors" in data:
            raise Exception(f"Error en la consulta de AppSync: {data['errors']}")
        
        favorites = data["data"]["listFavorites"]["items"]
        total_items.extend(favorites)
        
        next_token = data["data"]["listFavorites"].get("nextToken")
        
        # Si no hay nextToken, terminamos el ciclo
        if not next_token:
            break

    return total_items

def handler(event, context):
    print("EVENTO: ", event)
    params = event["queryStringParameters"]
    print("PARAMS: ", params)
    business_id = params["id"]
    
    try:
        total = total_favorites(business_id)
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "message": "Total de favoritos encontrados con éxito",
                "total": len(total)  # Retorna el total de registros
            })
        }
    
    except Exception as e:
        error_message = str(e)
        print("ERROR: ", error_message)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al consultar los favoritos.",
                "error": error_message
            })
        }
