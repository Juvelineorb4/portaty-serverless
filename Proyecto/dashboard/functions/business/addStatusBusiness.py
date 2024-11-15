import boto3
from botocore.exceptions import ClientError
import os

# Obtener el nombre de la tabla desde las variables de entorno
TABLE_BUSINESS_NAME = os.environ.get("TABLE_BUSINESS")
AWS_REGION = os.environ.get("AWS_REGION")

# Cliente de DynamoDB
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

def handler(event, context):
    try:
        table = dynamodb.Table(TABLE_BUSINESS_NAME)
        businesses_without_status = []
        last_evaluated_key = None
        
        # Paginación del scan
        while True:
            # Realizar el scan completo de la tabla
            if last_evaluated_key:
                response = table.scan(ExclusiveStartKey=last_evaluated_key)
            else:
                response = table.scan()
            
            businesses = response.get('Items', [])
            
            # Filtrar los negocios que no tienen el campo 'status'
            businesses_without_status.extend([business for business in businesses if 'statusOwner' not in business])
            
            # Verificar si hay más páginas de resultados
            last_evaluated_key = response.get('LastEvaluatedKey', None)
            if not last_evaluated_key:
                break
        
        print(f"Negocios sin campo 'status' encontrados: {len(businesses_without_status)}")
        
        # Actualizar cada negocio sin el campo 'status'
        for business in businesses_without_status:
            update_business_status(business['id'], table)
        
        # Retornar los negocios filtrados y actualizados
        return {
            "statusCode": 200,
            "body": {
                "message": "Negocios actualizados con 'status: ENABLED'.",
                "updated_count": len(businesses_without_status)
            }
        }

    except ClientError as e:
        print(f"Error al acceder a DynamoDB: {e}")
        return {
            "statusCode": 500,
            "body": {
                "message": "Error al acceder a la base de datos.",
                "error": str(e)
            }
        }
    except Exception as e:
        print(f"Error inesperado: {e}")
        return {
            "statusCode": 500,
            "body": {
                "message": "Error inesperado.",
                "error": str(e)
            }
        }

# Función para actualizar el campo 'status' de un negocio
def update_business_status(business_id, table):
    try:
        response = table.update_item(
            Key={
                'id': business_id
            },
            UpdateExpression="set #s = :statusValue",
            ExpressionAttributeNames={
                '#s': 'statusOwner'
            },
            ExpressionAttributeValues={
                ':statusValue': 'OWNER'
            },
            ReturnValues="UPDATED_NEW"
        )
        print(f"Negocio con ID {business_id} actualizado a 'status: ENABLED'. Respuesta: {response}")
    except ClientError as e:
        print(f"Error al actualizar el negocio con ID {business_id}: {e}")
    except Exception as e:
        print(f"Error inesperado al actualizar el negocio con ID {business_id}: {e}")
