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
    }
}
