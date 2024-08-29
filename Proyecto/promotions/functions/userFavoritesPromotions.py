import json
import requests
import os

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")

def get_user_table(id):
    # Definir el query GraphQL para obtener usuarios y sus favoritos con promociones
    query = """
        query getUsers($id: ID!) {
            getUsers(id: $id) {
                favorites {
                    items {
                        business {
                            id
                            name
                            thumbnail
                            promotions {
                                items {
                                    id
                                    image
                                }
                            }
                        }
                    }
                    nextToken
                }
            }
        }
    """

    variables = {"id": id}

    headers = {
        "Content-Type": "application/json",
        "x-api-key": appsync_api_key
    }

    response = requests.post(
        appsync_api_url,
        json={"query": query, "variables": variables},
        headers=headers,
    )

    return response.json()["data"]["getUsers"]

def handler(event, context):
    print("EVENTO: ", event)
    params = event.get("queryStringParameters", {})
    print("PARAMS: ", params)
    
    # Validar si el parámetro userID está presente y no es vacío
    user_id = params.get('userID')
    if not user_id:
        return {
            'statusCode': 400,
            'body': json.dumps({
                "success": False,
                "message": "El parámetro 'userID' es requerido y no puede estar vacío."
            })
        }

    try:
        # Realizar la consulta para obtener información del usuario
        user_info = get_user_table(user_id)
        print("Información del usuario:", user_info)
        
        # Procesar la información para construir el array de stories
        stories = []
        
        # Recorrer los favoritos del usuario
        for favorite in user_info['favorites']['items']:
            business_id = favorite['business']['id']
            business_name = favorite['business']['name']
            business_thumbnail = favorite['business']['thumbnail']
            
            # Inicializar el array de stories para este negocio
            business_stories = []
            
            # Recorrer las promociones del negocio
            for promotion in favorite['business']['promotions']['items']:
                promotion_id = promotion['id']
                promotion_image_url = promotion['image']
                
                # Construir el objeto de historia (story)
                story = {
                    'id': promotion_id,
                    'source': {
                        'uri': promotion_image_url
                    }
                }
                
                # Agregar la historia al array de historias del negocio
                business_stories.append(story)
            
            # Construir el objeto de negocio con sus historias
            business_obj = {
                'id': business_id,
                'name': business_name,
                'imgUrl': business_thumbnail,
                'stories': business_stories
            }
            
            # Agregar el negocio al array de historias (stories)
            stories.append(business_obj)
        
        # Devolver la respuesta exitosa con los datos consultados
        print("stories", stories)
        return {
            'statusCode': 200,
            'body': json.dumps({
                "success": True,
                "data": stories,
                "message": "Promociones consultadas con éxito."
            })
        }
    
    except Exception as e:
        error_message = str(e)
        return {
            'statusCode': 500,
            'body': json.dumps({
                "success": False,
                "message": "Error al consultar promociones.",
                "error": error_message
            })
        }
