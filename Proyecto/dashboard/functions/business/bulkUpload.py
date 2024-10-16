import boto3
import json
import os


# Función Lambda principal
def handler(event, context):
    try:
        print("EVENT: ", event)
        print("CARGA DE NEGOCIOS MASIVOS EXITOSA")
        return "Búsqueda de negocio exitosa."
    except Exception as e:
        # Manejo de error
        print("Error en carga de busqueda de negocios: ", str(e))
        return e




