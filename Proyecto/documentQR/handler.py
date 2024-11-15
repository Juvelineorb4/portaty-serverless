import json
import boto3
import qrcode
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import os
from io import BytesIO
import base64


AWS_REGION = "us-east-1"
s3 = boto3.client("s3", region_name=AWS_REGION)
bucketName = os.environ.get("S3_BUCKET_NAME")
bucketKey = "public"


def documentQr(event, context):
    try:
        print(f"Evento {event}")
        print(f"PARAMST: {event['queryStringParameters']} ")
        params = event['queryStringParameters']
        path = params.get("path")
        identityid = params.get("identityid")
        businessid = params.get("businessid")
        
        if not businessid:
            raise ValueError("El parámetro businessid es obligatorio")

        pathNew = f"https://www.portaty.com/share/business?id={businessid}"
        print(f"PATH: {path} IDENTITYID: {identityid} BUSINESSID: {businessid}")
        print(f"PATH NEW: {pathNew}")

        # Determinar las rutas para las imágenes según la presencia del identityid
        if identityid != 'null':
            logoKey = f"protected/{identityid}/business/{businessid}/profile_thumbnail.jpg"
            pathKey = f"protected/{identityid}/business/{businessid}/portatyQR.pdf"
        else:
            logoKey = f"public/assets/business/{businessid}/image.png"
            pathKey = f"public/assets/business/{businessid}/portatyQR.pdf"

        print(f"Intentando obtener la imagen del logo con la clave: {logoKey}")
        print(f"Intentando obtener la imagen base con la clave: {bucketKey}/portatyQR.jpg")

        # Obtener las imágenes del logo y la base
        try:
            logoResponse = s3.get_object(Bucket=bucketName, Key=logoKey)
            imageBaseResponse = s3.get_object(Bucket=bucketName, Key=f"{bucketKey}/portatyQR.jpg")
        except Exception as e:
            print(f"Error al obtener imágenes de S3 con la clave: {logoKey} o {bucketKey}/portatyQR.jpg: {e}")
            raise

        logo = logoResponse["Body"].read()
        imageBase = imageBaseResponse["Body"].read()

        # Procesar las imágenes
        try:
            logo = Image.open(BytesIO(logo))
            logoResize = logo.resize((100, 100))
            logoResize = make_logo_round(logoResize)
            imageBase = Image.open(BytesIO(imageBase))
            imageBase = imageBase.convert("RGBA")
            logoResize = logoResize.convert("RGBA")
            print("Se procesaron las imágenes correctamente")
        except Exception as e:
            print(f"Error al procesar las imágenes: {e}")
            raise

        # Crear el QR
        try:
            qr = generateQr(pathNew)
            qr = qr.resize((500, 500))
            qrLogo = addImageQr(qr, logoResize)
            imageBaseQr = addQrImageMain(qrLogo, imageBase)
            resultPDF = generatePdf("PORTATY_QR.pdf", imageBaseQr)
        except Exception as e:
            print(f"Error al generar el QR y el PDF: {e}")
            raise
        
        # Guardar el PDF en S3
        try:
            resultSave = s3.put_object(Body=resultPDF, Bucket=bucketName, Key=pathKey, ContentType="application/pdf")
            print("PDF guardado correctamente en S3")
        except Exception as e:
            print(f"Error al guardar el PDF en S3: {e}")
            raise

        # Respuesta exitosa
        response = {
            'statusCode': 200,
            'body': json.dumps({"url": f"https://{bucketName}.s3.amazonaws.com/{pathKey}"}),
            'headers': {
                'Content-Type': 'application/json',
            },
        }
        return response

    except Exception as e:
        print(f"Error en la función documentQr: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({"message": f"Error interno: {str(e)}"}),
            'headers': {'Content-Type': 'application/json'}
        }


def generateQr(path):
    # generar qr
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,

    )
    qr.add_data(path)
    qr.make()

    # qr imagen en color
    qrImg = qr.make_image().convert('RGB')
    return qrImg


def addImageQr(qr, logoResize):
    # calcular l;a posiciion de dodne se colocara el logo en el qr
    logoX = (qr.size[0] - logoResize.size[0]) // 2
    logoY = (qr.size[1] - logoResize.size[1]) // 2
    logoPos = (logoX, logoY)

    # insert logo image into qr code image
    qr.paste(logoResize, logoPos, logoResize)
    return qr


def addQrImageMain(qr, image):
    positionBase = (292, 380)
    # resizeQr = qr.resize((500,500))
    image.paste(qr, positionBase)
    return image


def generatePdf(path, image):

    # Crear un nuevo archivo PDF en memoria
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)

    # Obtener las dimensiones de la imagen
    ancho_imagen, alto_imagen = image.size

    # Establecer el tamaño del lienzo del PDF para que se ajuste a la imagen
    pdf.setPageSize((ancho_imagen, alto_imagen))

    # Convertir la imagen a bytes
    image_bytes = BytesIO()

    # Convertir la imagen a RGB antes de guardarla
    image_rgb = image.convert("RGB")

    # Guardar la imagen en formato JPEG
    image_rgb.save(image_bytes, format='JPEG')

    # Crear un objeto ImageReader a partir de los bytes
    image_reader = ImageReader(image_bytes)

    # Agregar la imagen al PDF desde ImageReader
    pdf.drawImage(image_reader, 0, 0, width=ancho_imagen, height=alto_imagen)

    # Guardar el PDF en el buffer
    pdf.showPage()
    pdf.save()

    # Obtener los bytes del buffer
    pdf_bytes = buffer.getvalue()

    return pdf_bytes


def make_logo_round(logo):
    # Crear una nueva imagen con el mismo tamaño y modo que el logo
    mask = Image.new('L', logo.size, 0)

    # Crear un objeto ImageDraw para dibujar en la máscara
    draw = ImageDraw.Draw(mask)

    # Dibujar un círculo blanco en la máscara en la misma posición y con el mismo tamaño que el logo
    draw.ellipse((0, 0) + logo.size, fill=255)

    # Crear una nueva imagen en modo RGBA para el logo redondo
    round_logo = Image.new('RGBA', logo.size)

    # Pegar el logo en la nueva imagen usando la máscara para hacerlo redondo
    round_logo.paste(logo, mask=mask)

    return round_logo
