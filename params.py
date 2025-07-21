import os

ATHENA_DB = "news_db"
ATHENA_TABLE = "news_table"
ATHENA_OUTPUT = "s3://zarruk/athena-results/"
QUEUE_URL = f"{os.environ['QUEUE_URL']}"

NUM_NEWS = 100

QUERY_PARAMS = {
    'semana': {
        'params': {
            "query": '{"feedOffset":9,"feedSize":'+str(NUM_NEWS)+',"includeSections":"politica","sourceInclude":"canonical_url,_id,promo_items,headlines.basic,subheadlines.basic,description.basic,subtype,publish_date,taxonomy,copyright"}',
            "d": f"{os.environ['SEMANA_d_param']}",
            "mxId": "00000000",
            "_website": "semana"
        },
        'api_url': "https://www.semana.com/pf/api/v3/content/fetch/content-apir",
        'base_url': "https://www.semana.com",
        'headers': {}
    },
    'LSV': {
        'params': {},
        'api_url': "https://www.lasillavacia.com/",
        'headers': {}

    },
    'wradio': {
        'params': {},
        'api_url': "https://www.wradio.com.co/",
        'base_url': "https://www.wradio.com.co",
        'headers': {
            "Host": "www.wradio.com.co",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Connection": "keep-alive"
        }

    },
    'caracol': {
        'params': {},
        'api_url': "https://caracol.com.co/",
        'base_url': "https://caracol.com.co",
        'headers': {}

    },
    'elespectador': {
        'params': {
            "query": (
                    '{"section":"/politica",'
                    '"site":"el-espectador",'
                    '"size":' + str(NUM_NEWS) + ','
                    '"sourceInclude":"_id,canonical_url,headlines.basic,'
                    'taxonomy.primary_section._id,taxonomy.primary_section.name,'
                    'display_date,label,credits.by.name,credits.by._id,'
                    'taxonomy.tags.slug,promo_items.basic,subtype,description.basic,'
                    'credits.by.additional_properties.original,'
                    'promo_items.jw_player,promo_items.youtube"}'
                ),
                "d": "1057",
                "mxId": "00000000",
                "_website": "el-espectador"
        },
        'api_url': "https://www.elespectador.com/pf/api/v3/content/fetch/general",
        'base_url': "https://www.elespectador.com",
        'headers': {}

    }
}

SUBJECT_EMAIL = [
    "{}, ¡gracias por tu propuesta!",
    "{}, recibimos tu propuesta con gusto",
    "{}, tu voz cuenta — gracias por participar",
    "{}, estamos revisando tu propuesta",
    "{}, agradecemos tu aporte",
    "{}, ¡qué bueno recibir tu propuesta!",
    "{}, gracias por compartir tus ideas",
    "{}, tu propuesta es valiosa para nosotros",
    "{}, gracias por escribirnos",
    "{}, estamos leyendo tu propuesta con atención"
]

RESPUESTAS_CORREO = [
    "Hola {},\n\nGracias por compartir tu propuesta. La vamos a revisar con mucho cuidado y, si podemos integrarla al programa de gobierno, nos comunicaremos contigo.\n\nA grandes rasgos, creería que podría servir para el documento de {}.\n\nUn saludo,\n{}",
    
    "Hola {},\n\nRecibimos tu propuesta y te agradecemos por tomarte el tiempo de enviarla. La vamos a considerar y te avisaremos si podemos incluirla en el plan de gobierno.\n\nInicialmente, me parece que podría tener relación con el documento de {}.\n\nSaludos,\n{}",
    
    "Hola {},\n\nMil gracias por tu propuesta. Nos alegra saber que quieres aportar ideas. La revisaremos con atención y, si encaja en el programa, te lo haremos saber.\n\nA simple vista, creería que podría tener un lugar en el documento de {}.\n\nUn abrazo,\n{}",
    
    "Hola {},\n\nTe agradecemos mucho por enviarnos tu propuesta. Será parte del análisis que estamos haciendo para construir un proyecto colectivo. Si logramos incluirla, te lo contaremos.\n\nEn principio, podría tener sentido incluirla en el documento de {}.\n\nGracias por tu voz,\n{}",
    
    "Hola {},\n\nRecibimos tu propuesta y te damos las gracias por sumarte con tus ideas. Vamos a revisarla y, si es posible incorporarla, nos pondremos en contacto.\n\nPensamos que, en términos generales, podría servir como insumo para el documento de {}.\n\nSeguimos construyendo juntos,\n{}",
    
    "Hola {},\n\nGracias por tu mensaje y por aportar al proyecto. Cada propuesta cuenta, y la tuya será tenida en cuenta en este proceso de revisión. Si podemos incluirla, te avisamos.\n\nEn un primer vistazo, podría ser útil como referencia para el documento de {}.\n\nUn saludo grande,\n{}",
    
    "Hola {},\n\nApreciamos mucho tu participación. Tu propuesta ya está en nuestras manos y será analizada con el mismo cuidado que todas. Si logramos incorporarla, te escribiremos.\n\nA grandes rasgos, creemos que podría aportar al documento de {}.\n\nGracias por construir con nosotros,\n{}",
    
    "Hola {},\n\nGracias por enviarnos tu propuesta. Es muy valioso contar con ideas como la tuya para enriquecer el programa. Vamos a revisarla y te escribimos si logramos incluirla.\n\nPor lo que hemos visto, podría aportar algo interesante al documento de {}.\n\nUn fuerte abrazo,\n{}",
    
    "Hola {},\n\n¡Qué bueno recibir tu propuesta! La tendremos muy en cuenta en la construcción del programa. Si llega a hacer parte de la versión final, te lo haremos saber.\n\nDe entrada, nos parece que podría servir como insumo en el documento de {}.\n\nGracias por creer en este proyecto,\n{}",
    
    "Hola {},\n\nNos llegó tu propuesta y queremos darte las gracias. Queremos un programa que recoja muchas voces, y la tuya ya hace parte de ese esfuerzo. Si podemos incluirla, te contamos.\n\nSin comprometer nada aún, creemos que podría ser considerada en el documento de {}.\n\nCon gratitud,\n{}"
]

REMITENTES = [
    "David Zarruk",
    "Daniel Wills",
    "Alejandro Vallejo",
    "Guillermo Llinás",
    "Juan José Echavarría",
    "Juan Martín Londoño",
    "Alejandra Londoño"
]