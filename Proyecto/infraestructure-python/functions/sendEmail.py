import json
import boto3
import os
import smtplib
from email.message import EmailMessage

# Inicializa las variables de entorno y el cliente SQS
smtp_username = os.environ.get("SMTP_USERNAME")
smtp_password = os.environ.get("SMTP_PASSWORD")
smtp_server = os.environ.get("SMTP_SERVER", "smtp.zoho.com")
smtp_port = int(os.environ.get("SMTP_PORT", 465))
sender_email = os.environ.get("SENDER_EMAIL", "no-responder@portaty.com")

def handler(event, context):
    print("EVENT:", event)
    
    # Procesa cada mensaje recibido desde la cola SQS
    for record in event.get('Records', []):
        body = record.get('body')
        if body:
            try:
                # Carga el mensaje y extrae los datos necesarios
                json_body = json.loads(body)
                print("BODY:", json_body)
                
                # Validar que los datos esenciales están presentes
                recipient_email = json_body.get('email')
                subject = json_body.get('subject', 'Notificación de Portaty')
                message_body = json_body.get('body', '')

                if not recipient_email:
                    print("Error: No se proporcionó el campo 'email'.")
                    continue

                # Envía el correo electrónico
                send_email(recipient_email, subject, message_body)
                print(f"Correo enviado a {recipient_email}")

            except Exception as e:
                print(f"Error procesando el mensaje: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Mensajes procesados exitosamente')
    }

# Función para enviar el correo electrónico
def send_email(recipient_email, subject, body):
    try:
        # Configuración del email
        email = EmailMessage()
        email["From"] = sender_email
        email["To"] = recipient_email
        email["Subject"] = subject
        email.set_content(body)

        # Conectar al servidor SMTP y enviar el correo
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
            smtp.login(sender_email, "HdCmgawsJZbN")  # Usa AWS Secrets Manager o variables de entorno para las credenciales.
            smtp.send_message(email)
            print(f"Correo enviado a {recipient_email}")

    except Exception as e:
        print(f"Error al enviar el correo: {str(e)}")
        raise e
