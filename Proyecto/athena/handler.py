import boto3

def handler(event, context):
    athena_client = boto3.client('athena')

    # Ejemplo de consulta
    query = "SELECT * FROM events LIMIT 10"

    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            'Database': 'portaty-app-glue-database'
        },
        ResultConfiguration={
            'OutputLocation': 's3://portaty-athena/'
        }
    )

    # Obtener el ID de ejecución de la consulta
    query_execution_id = response['QueryExecutionId']

    return {
        'statusCode': 200,
        'body': f'Query ejecutada con ID: {query_execution_id}'
    }