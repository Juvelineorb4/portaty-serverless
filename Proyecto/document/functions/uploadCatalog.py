import json
import boto3
from PIL import Image
from io import BytesIO
import base64
import random
from datetime import datetime, timezone
import os
import requests
from requests_aws4auth import AWS4Auth

AWS_REGION = "us-east-1"
s3 = boto3.client("s3", region_name=AWS_REGION)
db = boto3.client("dynamodb", region_name=AWS_REGION)
bucketName = os.environ.get("S3_BUCKET_NAME")
tableNameDB = os.environ.get("TABLE_BUSINESS_NAME")

appsync_api_url = os.environ.get("APPSYNC_URL")
appsync_api_key = os.environ.get("APPSYNC_API_KEY")
region = os.environ.get("AWS_REGION")
print(appsync_api_url)
service = 'appsync'  # servicio de opensearch
# credenciales de boto3 asociadas a esta session
credentials = boto3.Session().get_credentials()
# Para firmar las solicitudes https con la firma AWS Signature Version 4. Esta firma es necesaria para autenticar las solicitudes a servicios como OpenSearch.
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                   region, service, session_token=credentials.token)


def handler(event, context):
    print("EVENTO:", event)
    records = event["Records"]
    print("Records: ", records)
    try:
        for record in records:
            print(record)
            keyOriginal = record["s3"]["object"]["key"]
            # Reemplazar %3A por :
            key = keyOriginal.replace('%3A', ':')
            print("Key: ", key)
            result = s3.get_object(Bucket=bucketName, Key=key)
            print("RESULT: ", result)
            businessID = result["Metadata"]["businessid"]
            print("businessID: ", businessID)
            url = f"https://{bucketName}.s3.amazonaws.com/{key}"
            # db.update_item(
            #     TableName=tableNameDB,
            #     Key={'id': {'S': businessID}},
            #     UpdateExpression='SET #catalogpdf = :catalogpdf',
            #     ExpressionAttributeNames={
            #         '#catalogpdf': 'catalogpdf',
            #     },
            #     ExpressionAttributeValues={
            #         ':catalogpdf': {'S': url}
            #     },
            #     ReturnValues='UPDATED_NEW'
            # )

            # Definir la mutación de GraphQL
            mutation = """
                    mutation updateBusiness(
                        $input: UpdateBusinessInput!
                    ) {
                        updateBusiness(input: $input){
                            id
                        }
                    }
                """
            variables = {
                "input": {
                    "id": businessID,
                    "catalogpdf": url
                }
            }

            headers = {
                "Content-Type": "application/json",
                "x-api-key": appsync_api_key  # Utiliza la clave API en la cabecera x-api-key
            }
            response = requests.post(
                appsync_api_url,
                json={"query": mutation, "variables": variables},
                headers=headers,
            )
            print("AppSync Response: ", response.json())
        response = {
            "statusCode": 200,
            "body": json.dumps("LAMBDA EJECUTADA EXITOSAMENTE")
        }
        return response
    except Exception as e:
        print("ERROR: ", e)
        response = {
            "statusCode": 500,
            "body": json.dumps(e)
        }
        return response
    # end try
