import json
from email.message import EmailMessage
import smtplib



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
     
        email = datos.get("email")
        print("Email:", email)

        if (email != None):
            sendEmail(email)
            print("EMAIL ENVIADO")

    response = {
        "statusCode": 200,
        "body": json.dumps("Messaged Send")
    }

    return response



def sendEmail(des):
    remitente = "no-responder@portaty.com"
    destinatario = des
    mensaje = "Gracias por Registrate"


    # configuracion
    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = "Gracias por registrar tu negocio en Portaty"
    email.set_content(mensaje)
    try:
        smtp = smtplib.SMTP_SSL("smtp.zoho.com", 465)  # Ajusta el puerto según la configuración de tu proveedor
        smtp.login(remitente, "HdCmgawsJZbN")  # Utiliza variables de entorno o un sistema de gestión de secretos
        smtp.sendmail(remitente, destinatario, email.as_string())
        smtp.quit()
    except Exception as e:
        print("Error al enviar el correo electrónico:", str(e))