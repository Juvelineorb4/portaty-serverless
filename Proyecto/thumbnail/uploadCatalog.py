import json
import boto3
from PIL import Image
from io import BytesIO
import base64
import random
from datetime import datetime, timezone
import os


AWS_REGION = "us-east-1"
s3 = boto3.client("s3", region_name=AWS_REGION)
db = boto3.client("dynamodb", region_name=AWS_REGION)
bucketName = os.environ.get("S3_BUCKET_NAME")
tableNameDB = os.environ.get("TABLE_BUSINESS_NAME")


def handler(event, context):
    body = json.loads(event['body'])
    print("BODY:", body)
    try:

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
