ATHENA_DB = "news_db"
ATHENA_TABLE = "news_table"
ATHENA_OUTPUT = "s3://zarruk/athena-results/"

NUM_NEWS = 100

QUERY_PARAMS = {
    'semana': {
        'params': {
            "query": '{"feedOffset":9,"feedSize":'+str(NUM_NEWS)+',"includeSections":"politica","sourceInclude":"canonical_url,_id,promo_items,headlines.basic,subheadlines.basic,description.basic,subtype,publish_date,taxonomy,copyright"}',
            "d": "7730",
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
