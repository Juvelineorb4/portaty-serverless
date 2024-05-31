import json
import boto3
import qrcode
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import os
from io import BytesIO
import base64


AWS_REGION = "us-east-1"
s3 = boto3.client("s3", region_name=AWS_REGION)
bucketName = "s3professions202858-dev"
bucketKey = "public"

def documentQr(event, context):
    print(f"Evento {event}")
    print(f"PARAMST: {event['queryStringParameters']} ")
    params = event['queryStringParameters']
    path = params.get("path")
    identityid= params.get("identityid")
    businessid= params.get("businessid")
    pathNew= f"https://www.portaty.com/share/business?id=${businessid}"
    print(f"PATH: {path} IDENTITYID: {identityid} BUSINESSID: {businessid}")
    print(f"PATH NEW: {pathNew}")
    # obtenemos las imagenes del logo y la del imageBase
    logoResponse = s3.get_object(Bucket=bucketName, Key=f"{bucketKey}/logo.png")
    imageBaseResponse = s3.get_object(Bucket=bucketName, Key=f"{bucketKey}/pdfQr.jpg")
    logo = logoResponse["Body"].read()
    imageBase = imageBaseResponse["Body"].read()
    # leemos la imagen 
    logo = Image.open(BytesIO(logo))
    logoResize = logo.resize((150,150))
    imageBase = Image.open(BytesIO(imageBase))
    
    
    # creamos el qr
    qr = generateQr(path)
    qrLogo = addImageQr(qr, logoResize)
    imageBaseQr = addQrImageMain(qrLogo,imageBase)
    resultPDF = generatePdf("qr.pdf",imageBaseQr)
    # pdf_base64 = base64.b64encode(result).decode('utf-8')
    print(resultPDF)
    pathKey = f"protected/{identityid}/business/{businessid}/qr.pdf"
    resultSave =s3.put_object(Body=resultPDF, Bucket=bucketName, Key=pathKey, ContentType="application/pdf")

    response = {
       'statusCode': 200,
        'body': json.dumps({"url": f"https://{bucketName}.s3.amazonaws.com/{pathKey}"}),
        'headers': {
            'Content-Type': 'application/json',
        },
    }

    return response


def generateQr(path):
    # generar qr
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,

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
  qr.paste(logoResize, logoPos,logoResize)
  return qr

def addQrImageMain(qr, image):
  positionBase = (140,210)
  resizeQr = qr.resize((366,400))
  image.paste(resizeQr, positionBase)
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
    image.save(image_bytes, format='JPEG')

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
