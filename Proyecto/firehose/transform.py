import base64
import json
import time

def handler(event, context):
    print("EVENTS: ", event)
    output = []

    for record in event['records']:
        # Decodifica el registro de entrada de base64
        payload = base64.b64decode(record['data'])

        # Transforma el registro y agrega el sello de tiempo
        transformed_record = json.loads(payload)
        transformed_record['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())

        # Codifica el registro transformado en base64
        transformed_payload = json.dumps(transformed_record)
        transformed_data = base64.b64encode(transformed_payload.encode('utf-8')).decode('utf-8')

        output_record = {
            'recordId': record['recordId'],
            'result': 'Ok',
            'data': transformed_data
        }
        output.append(output_record)

    return {'records': output}