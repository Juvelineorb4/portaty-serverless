import boto3
import os
import time
import json
athena_client = boto3.client('athena',region_name=os.environ.get("REGION"))



def execute_athena_query(query_string, database, output_location):
    query = "SELECT * FROM events LIMIT 10"
    response = athena_client.start_query_execution(
        QueryString=query_string,
        QueryExecutionContext={
            'Database': database
        },
        ResultConfiguration={
            'OutputLocation': output_location
        }
    )
    return response['QueryExecutionId']

def get_query_status(query_execution_id):
    response = athena_client.get_query_execution(
        QueryExecutionId=query_execution_id
    )
    return response['QueryExecution']['Status']['State']

def get_query_results(query_execution_id):
    response = athena_client.get_query_results(
        QueryExecutionId=query_execution_id
    )
    # Process and print/query the results
    print(response['ResultSet']['Rows'])
    resultData = []
    resultDic = {}
    first_row_skipped = False
    for row in response['ResultSet']['Rows']:
        if not first_row_skipped:
            first_row_skipped = True
            continue  # Saltar la primera fila
        if "Data" in row:
            key = row['Data'][0]['VarCharValue']
            value = row['Data'][1]['VarCharValue']
            resultDic[key] = value
        resultData.append([field['VarCharValue'] for field in row['Data']])
    return resultDic


def handler(event, context):

    print("EVENT:",event)
    # obtenemos los valores de queryStringParameters
    params = event["queryStringParameters"]
    businessID =params["businessID"]
    print("BUSINESSID:", businessID)
    if not businessID:
        return {
        'statusCode': 400,
        'body': "Variabled Buisness is undefined"
        }
    query_string = f"SELECT CAST(CONCAT(partition_1, '-', partition_2, '-', partition_3) AS date) AS fecha, COUNT(*) AS numero_de_visitas FROM events WHERE eventname = 'user_viewed_business' AND businessid = '{businessID}' GROUP BY CONCAT(partition_1, '-', partition_2, '-', partition_3) ORDER BY fecha;"
    print("QUERY:", query_string)
    database = "portaty-app-glue-database"
    output_location = "s3://portaty-athena/"
    query_execution_id = execute_athena_query(query_string, database, output_location)
    status = get_query_status(query_execution_id)
    while status in ['QUEUED', 'RUNNING']:
        print(f"La consulta aún está en estado: {status}. Esperando 5 segundos antes de verificar de nuevo...")
        time.sleep(5)
        status = get_query_status(query_execution_id)
    
    if status == 'SUCCEEDED':
        print("La consulta ha sido completada exitosamente. Obteniendo resultados...")
        results = get_query_results(query_execution_id)
        print(results)
        return {
        'statusCode': 200,
        'body': json.dumps({
            "message": f'Query ejecutada con ID: {query_execution_id}',
            "data":{
                "likesData": results
                }
            })
        }
    else:
        print("La consulta ha fallado o ha sido cancelada.")
        return {
        'statusCode': 400,
        'body': f'Query failed or was canceled. ejecutada con ID: {query_execution_id}'
        }