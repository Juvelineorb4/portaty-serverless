import boto3
import os
import time
import json
import datetime

athena_client = boto3.client('athena',region_name=os.environ.get("REGION"))

region_name=region_name=os.environ.get("REGION")
s3_output_path= os.environ.get("S3_OUTPUT")
work_group='primary'
database= os.environ.get("GLUE_DATABASE")
nombres_meses_espanol = {
        1: "ene",
        2: "feb",
        3: "mar",
        4: "abr",
        5: "may",
        6: "jun",
        7: "jul",
        8: "ago",
        9: "sep",
        10: "oct",
        11: "nov",
        12: "dic"
    }


def run_query(query, s3_output_path, region_name, *args, **kwargs):
    query_list=[]
    response_list=[]
    if(type(query) is list):
        query_list=query
    else:
        query_list.append(query)
    work_group = kwargs.get('work_group', None)
    database = kwargs.get('database', None)
    OutputLocation={}
    OutputLocation['OutputLocation'] = s3_output_path
    client = boto3.client('athena', region_name=region_name)
    for single_query in query_list:
        if ((work_group == None) and (database == None)):
            response = client.start_query_execution( 
                    QueryString=single_query, 
                    ResultConfiguration=OutputLocation
                    ) 
        if ((work_group == None) and (database != None)):
            DatabaseName={}
            DatabaseName['Database'] = database
            response = client.start_query_execution( 
                    QueryString=single_query, 
                    ResultConfiguration=OutputLocation,
                    QueryExecutionContext=DatabaseName  
                    ) 
        if ((work_group != None) and (database == None)):
            response = client.start_query_execution( 
                    QueryString=single_query, 
                    ResultConfiguration=OutputLocation,
                    WorkGroup=work_group
                    ) 
        if ((work_group != None) and (database != None)):
            DatabaseName={}
            DatabaseName['Database'] = database
            response = client.start_query_execution( 
                    QueryString=single_query, 
                    ResultConfiguration=OutputLocation,
                    WorkGroup=work_group,
                    QueryExecutionContext=DatabaseName  
                    )
        print('\nExecution ID: ' + response['QueryExecutionId'])
        response_list.append(response['QueryExecutionId'])
    return response_list

def get_query_status(query_execution_id):
    response = athena_client.get_query_execution(
        QueryExecutionId=query_execution_id
    )
    return response['QueryExecution']['Status']['State']

def get_query_results(query_execution_id, type_query):
    response = athena_client.get_query_results(
        QueryExecutionId=query_execution_id
    )
    # Process and print/query the results
    print("PROCESS:",response['ResultSet']['Rows'])
    print("TIPO:", type_query)
    resultData = []
    resultDic = {}
    first_row_skipped = False
    row_key =  [field['VarCharValue'] for field in response['ResultSet']['Rows'][0]['Data']]
    print("ROW KEY:", row_key)
    for row in response['ResultSet']['Rows']:
        if not first_row_skipped:
            first_row_skipped = True
            continue  # Saltar la primera fila
        if type_query == "table":
             if "Data" in row:
                key = row['Data'][0]['VarCharValue']
                value = row['Data'][1]['VarCharValue']
                resultDic[key] = value
        elif type_query == "grafic":
            graficDic = {}
            for indice, field in enumerate(row['Data']):
                key = row_key[indice]
                value = field['VarCharValue']
                graficDic[key] = value
            resultData.append(graficDic)
    if type_query == "table":
        return resultDic
    elif type_query == "grafic":
        return resultData
              
        
def convertir_meses_a_palabras(diccionario):
    meses_en_palabras = {}
    for clave, valor in diccionario.items():
        ano, mes = clave.split('-')
        nombre_mes = f"{nombres_meses_espanol[int(mes)]}-{ano}"
        meses_en_palabras[nombre_mes.lower()] = valor
    return meses_en_palabras


def handler(event, context):
    print("EVENT:",event)
     # Obtener la fecha actual en formato yyyy-mm-dd
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    # Calcular la fecha de 30 días atrás
    before_30_days = (datetime.datetime.now() - datetime.timedelta(days=29)).strftime('%Y-%m-%d')
  

    # obtenemos los valores de queryStringParameters
    # HAY QUE MODIFICAR APRA PROD
    params = event.get("queryStringParameters", {"businessID": '177e1843-7600-43d8-bb33-b37c5411aeb5'})
    businessID =params["businessID"]

    if not businessID:
        return {
        'statusCode': 400,
        'body': json.dumps({
                "message": f'Variabled businessID is {businessID}',   
                })
        }
    query_view_30_days = f"WITH fecha_rango AS (SELECT DATE_ADD('day', seq, DATE '{before_30_days}') AS fecha FROM (SELECT ROW_NUMBER() OVER () - 1 AS seq FROM UNNEST(sequence(1, DATE_DIFF('day', TIMESTAMP '{before_30_days}', TIMESTAMP '{today}')+1)) AS t(seq) LIMIT 365) nums ) SELECT fecha_rango.fecha AS fecha, COALESCE(COUNT(events.userid), 0) AS numero_de_visitas FROM fecha_rango LEFT JOIN events ON CAST(CONCAT(events.partition_1, '-', events.partition_2, '-', events.partition_3) AS date) = fecha_rango.fecha AND events.eventname = 'user_viewed_business' AND events.businessid = '{businessID}' GROUP BY fecha_rango.fecha ORDER BY fecha_rango.fecha;"
   
    query_view_year = f"WITH fecha_rango AS (SELECT DATE_TRUNC('month', timestamp '{today}') - INTERVAL '1' MONTH * seq AS fecha FROM UNNEST(sequence(0, 11)) AS t(seq))SELECT to_char( DATE_TRUNC('month',fecha_rango.fecha), 'yyyy-mm') AS fecha_mes, COALESCE(COUNT(events.userid), 0) AS numero_de_visitas FROM fecha_rango LEFT JOIN events ON DATE_TRUNC('month',  CAST(CONCAT(events.partition_1, '-', events.partition_2, '-', events.partition_3) AS date)) = DATE_TRUNC('month', fecha_rango.fecha) AND events.eventname = 'user_viewed_business' AND events.businessid = '{businessID}' GROUP BY DATE_TRUNC('month', fecha_rango.fecha) ORDER BY DATE_TRUNC('month', fecha_rango.fecha);"
   
    
    query_gender_percentage = f"WITH total_visitas AS (SELECT COUNT(*) AS total FROM events WHERE eventname = 'user_viewed_business' AND businessid = '{businessID}'), generos AS (SELECT 'Male' AS genero UNION ALL SELECT 'Female' UNION ALL SELECT 'Others') SELECT generos.genero, COALESCE(COUNT(events.userid), 0) AS cantidad_visitas, CASE WHEN total_visitas.total = 0 THEN 0 ELSE ROUND(COALESCE(COUNT(events.userid), 0) * 100 / total_visitas.total, 2) END AS porcentaje_visitas FROM generos LEFT JOIN events ON events.gender = generos.genero AND events.eventname = 'user_viewed_business' AND events.businessid = '{businessID}' LEFT JOIN total_visitas ON 1=1 GROUP BY generos.genero, total_visitas.total ORDER BY porcentaje_visitas DESC;"
   
    query_country_percentage = f"SELECT country as pais, COUNT(*) AS numero_de_visitas, ROUND(COUNT(*) * 100 / total_visitas.total, 2) AS porcentaje_visitas FROM events CROSS JOIN (SELECT COUNT(*) AS total FROM events WHERE eventname = 'user_viewed_business' AND businessid = '{businessID}') AS total_visitas WHERE eventname = 'user_viewed_business' AND businessid = '{businessID}' GROUP BY country, total_visitas.total;"
   
    query_city_percentage = f"SELECT country as pais, city as ciudad, COUNT(*) AS numero_de_visitas, ROUND(COUNT(*) * 100.0 / total_visitas.total, 2) AS porcentaje_visitas FROM events CROSS JOIN ( SELECT COUNT(*) AS total FROM events WHERE eventname = 'user_viewed_business' AND businessid = '{businessID}') AS total_visitas WHERE eventname = 'user_viewed_business' AND businessid = '{businessID}' GROUP BY country, city, total_visitas.total;"
   
    query_age_percentage = f"WITH rangos_edad AS (SELECT '18-25' AS rango_edad UNION ALL SELECT '26-30' UNION ALL SELECT '31-40' UNION ALL SELECT '41-50' UNION ALL SELECT '50+'), edad_usuarios AS (SELECT DATE_DIFF('year', CAST(birthdate AS timestamp), CURRENT_TIMESTAMP) AS edad FROM events WHERE eventname ='user_viewed_business' AND businessid = '{businessID}') SELECT rangos_edad.rango_edad, COALESCE(COUNT(edad_usuarios.edad), 0) AS cantidad, ROUND(COALESCE(COUNT(edad_usuarios.edad) * 100 / NULLIF((SELECT COUNT(*) FROM edad_usuarios), 0), 0), 2) AS porcentaje FROM rangos_edad LEFT JOIN edad_usuarios ON CASE WHEN rangos_edad.rango_edad = '18-25' AND edad_usuarios.edad BETWEEN 18 AND 25 THEN 1 WHEN rangos_edad.rango_edad = '26-30' AND edad_usuarios.edad BETWEEN 26 AND 30 THEN 1 WHEN rangos_edad.rango_edad = '31-40' AND edad_usuarios.edad BETWEEN 31 AND 40 THEN 1 WHEN rangos_edad.rango_edad = '41-50' AND edad_usuarios.edad BETWEEN 41 AND 50 THEN 1 WHEN rangos_edad.rango_edad = '50+' AND edad_usuarios.edad >= 51 THEN 1 ELSE 0 END = 1 GROUP BY rangos_edad.rango_edad ORDER BY rangos_edad.rango_edad;"
    # arreglo de queries
    query_list=[query_view_30_days,query_view_year, query_gender_percentage, query_country_percentage, query_city_percentage, query_age_percentage]
    type_list = ["table", "table","grafic", "grafic", 'grafic', 'grafic']
    # respuesta en id de consulta de athena 
    response_list = run_query(query_list, s3_output_path, region_name, database=database)
    print("RESPONSE LIST:", response_list)
    # consultar estado de los queries id
    results_query = []
    for indice, query_execution_id in enumerate(response_list):
        
        status = get_query_status(query_execution_id)
        while status in ['QUEUED', 'RUNNING']:
            print(f"La consulta aún está en estado: {status}. Esperando 5 segundos antes de verificar de nuevo...")
            time.sleep(1.2)
            status = get_query_status(query_execution_id)
        
        if status == 'SUCCEEDED':
            print(f"La consulta ha sido completada exitosamente. Obteniendo resultados...{query_execution_id}")
            result = get_query_results(query_execution_id, type_list[indice])
            results_query.append(result)            
        else:
            return {
            'statusCode': 400,
            'body': json.dumps({
                "message": f'Query FALLIDA ejecutada con ID: {query_execution_id}',

                })
            }
    print("RESULT QUERY:", results_query)
    return {
        'statusCode': 200,
        'body': json.dumps({
            "message": f'Query ejecutada con exito',
            "data":{
                "likesData": {
                    "days": results_query[0],
                    "year": convertir_meses_a_palabras(results_query[1])
                },
                "gender": results_query[2],
                "country": results_query[3],
                "city": results_query[4],
                "age": results_query[5]
                }
            })
        }