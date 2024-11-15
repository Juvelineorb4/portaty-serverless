import json
import boto3
from email.message import EmailMessage
import smtplib
import os

# Inicializa el cliente S3 y obtiene los datos de la región y el bucket desde variables de entorno
region = os.environ.get("AWS_REGION")
s3 = boto3.client("s3", region_name=region)
bucketName = os.environ.get("S3_BUCKET_NAME")

def handler(event, context):
    print("EVENT", event)
    records = event.get("Records")
    print("TAMANO DE RECORDS", len(records))
    
    for elemento in records:
        body = elemento.get("body")
        jsonBody = json.loads(body)
        print("BODY:", jsonBody)
        message = jsonBody.get("Message")
        print("Message:", message)
        datos = json.loads(message)
        print("DATOS: ", datos)

        # Obtener los datos necesarios
        email = datos.get("email").get("S")
        nombre_negocio = datos.get("name").get("S")
        telefono = datos.get("phone").get("S")
     

        if email is not None:
            # Cargar el contenido HTML desde S3
            html_content = get_html_content_from_s3(bucketName, f"public/assets/html/negocio.html", {
                '{nombre}': nombre_negocio,
                '{telefono}': telefono,
                '{correo}': email,
                '{business}': nombre_negocio
            })
            print("HTML OBTENIDO: ", html_content)
            sendEmail(email, html_content)
            print("EMAIL ENVIADO")

    response = {
        "statusCode": 200,
        "body": json.dumps("Mensaje Enviado")
    }

    return response

# Función para cargar la plantilla HTML desde S3 y reemplazar los valores dinámicos
def get_html_content_from_s3(bucket, key, replacements):
    print("REMPLAZAR: ", replacements)
    # Obtener la plantilla HTML desde S3
    response = s3.get_object(Bucket=bucket, Key=key)
    html_template = response['Body'].read().decode('utf-8')

    # Reemplazar los marcadores de posición con los datos reales
    for placeholder, value in replacements.items():
        html_template = html_template.replace(f'{placeholder}', value)

    return html_template

# Función para enviar el correo electrónico
def sendEmail(destinatario, html_content):
    remitente = "no-responder@portaty.com"
    
    # Configuración del Email
    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = "Gracias por registrar tu negocio en Portaty"
    
    # Enviar el contenido en HTML
    email.add_alternative(html_content, subtype='html')

    try:
        smtp = smtplib.SMTP_SSL("smtp.zoho.com", 465)
        smtp.login(remitente, "HdCmgawsJZbN")  # Usa AWS Secrets Manager o variables de entorno para las credenciales.
        smtp.sendmail(remitente, destinatario, email.as_string())
        smtp.quit()
    except Exception as e:
        print("Error al enviar el correo electrónico:", str(e))
