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
        'base_url': "https://www.semana.com"
    },
    'LSV': {
        'params': {},
        'api_url': "https://www.lasillavacia.com/"
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
        'base_url': "https://www.elespectador.com"
    }
}
