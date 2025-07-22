import requests
import json
from utils import get_links, get_articles, update_db, \
    get_sentiment, read_df_from_s3, get_propuesta, clean_and_format_name, \
    query_athena_to_df, filter_new_by_candidate_names, send_gmail, batch_scheduler_propuestas, \
    generate_text_dataframe, read_all_files_from_s3_folder, compute_closest_texts, get_embedding
from params import NUM_NEWS, QUERY_PARAMS, ATHENA_TABLE, ATHENA_DB, ATHENA_OUTPUT, QUEUE_URL, \
    SUBJECT_EMAIL, RESPUESTAS_CORREO, REMITENTES
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import random
import json
import boto3
import uuid



def scrape_news(event, context):

    # Start requests session
    session = requests.Session()

    print(f"Scraping {event['source']}. Getting URLs from first {NUM_NEWS} news to fetch...")
    response = session.get(QUERY_PARAMS[event['source']]['api_url'],
                           params=QUERY_PARAMS[event['source']]['params'],
                           headers=QUERY_PARAMS[event['source']]['headers']).text
    
    print(response)
    
    links = get_links(response,
                      source=event['source'],
                      params=QUERY_PARAMS[event['source']])
    
    print(f"Getting already scraped URLs from {event['source']}")
    query = f"SELECT DISTINCT url FROM news_table WHERE source = '{event['source']}'"
    df_urls = query_athena_to_df(query, "news_db", "s3://zarruk/athena-results/")
        
    if len(df_urls)>0:
        # Keep only links that have not been scraped
        links = list(set(links) - set(df_urls['url']))

    print(f"Total number of links to be scrapped: {len(links)}")

    df = pd.DataFrame()

    print("Scraping news...")
    # Perform GET requests for each filtered hyperlink
    for i, link in enumerate(links):
        df_noticia = get_articles(link, session=session, source=event['source'])
        df = pd.concat([df, df_noticia])

    # Generate current timestamp
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    run_str = now.strftime("%H-%M")
    source_str = event['source']
    folder = f"noticias-politica/source={source_str}/date={date_str}/run={run_str}"
    partition_str = f"source='{source_str}', date='{date_str}', run='{run_str}'"

    if len(df)>0:
        update_db(df, folder,
                  ATHENA_TABLE, ATHENA_DB, ATHENA_OUTPUT, 
                  partition_str=partition_str)
    else:
        print("No news to update.")


def get_candidate_sentiment(event, context):
    prompt = open('prompt.txt', 'r').read()
    with open('lista_candidatos.txt', 'r', encoding='utf-8') as f:
        candidates = f.readlines()
    
    print("Reading cleaned news")
    query = """
    SELECT DISTINCT *
    FROM news_table
    where url not in (SELECT DISTINCT url
                      FROM sentiments_table)
    """

    database = "news_db"
    output_location = "s3://zarruk/athena-results/"

    df = query_athena_to_df(query, database, output_location)

    print("Filtering by candidates")
    df = filter_new_by_candidate_names(df, candidates)

    df_all_sentiments = pd.DataFrame()

    if len(df)>0:
        print(f"Getting sentiments for {len(df)} news...")
        for i, article in enumerate(df['articlebody']):
            print(f"Analyzing article {i} our of {len(df)}. URL: {df['url'].iloc[i]}")
            try:
                df_sentiment = get_sentiment(candidates, article, prompt)
                df_all_sentiments = pd.concat([df_all_sentiments, df_sentiment], axis=0)
                print(f"df shape so far: {df_all_sentiments.shape}")
            except Exception as e:
                print(f"Skipping article due to error: {e}")

        df_all_sentiments = pd.merge(left=df_all_sentiments,
                                        right=df,
                                        on='articlebody')

        # Generate current timestamp
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        run_str = now.strftime("%H-%M")
        folder = f"sentiments-news-table/date={date_str}/run={run_str}"
        partition_str = f"date='{date_str}', run='{run_str}'"

        update_db(df_all_sentiments, folder,
                  'sentiments_table', ATHENA_DB, ATHENA_OUTPUT, 
                  partition_str=partition_str)
        
    else:
        print("No sentiments to update...")


def get_candidate_propuestas(event, context):
    prompt = open('prompt_propuestas.txt', 'r').read()
    with open('lista_candidatos.txt', 'r', encoding='utf-8') as f:
        candidates = f.readlines()
    
    print("Reading cleaned news")
    df = read_df_from_s3(
        bucket_name="zarruk",
        key=f"cleaned_news/cleaned_news.csv"
    )

    print("Filtering by candidates")
    df = filter_new_by_candidate_names(df, candidates)
    json_propuestas = {}

    print("Getting propuestas")

    for article in df['articleBody']:
        json_propuestas = get_propuesta(candidates, article, prompt, json_propuestas, "")
        print(json.dumps(json_propuestas, indent=2, ensure_ascii=False))



def queue_proposal(event, context):
    sqs = boto3.client('sqs')

    print(f"Getting embeddings from existing proposals...")
    query = f"SELECT DISTINCT titulo, embedding FROM documentos_programaticos"
    df_embeddings = query_athena_to_df(query, "news_db", "s3://zarruk/athena-results/")

    print(f"Getting embedding for proposal...")
    target_embedding = get_embedding(event['propuesta'])

    print(f"Computing closest proposal...")
    top_indices = compute_closest_texts(target_embedding,
                                        df_embeddings,
                                        embedding_column = 'embedding')

    print(f"Storing message...")
    message = {
        "proposal_id": str(uuid.uuid4()),
        "nombre": event['nombre'],
        "correo": event['correo'],
        "propuesta": event['propuesta'],
        "embedding": target_embedding,
        "closest_document_1": df_embeddings['titulo'][top_indices[0]],
        "closest_document_2": df_embeddings['titulo'][top_indices[1]],
        "closest_document_3": df_embeddings['titulo'][top_indices[2]],
        "closest_document_4": df_embeddings['titulo'][top_indices[3]],
        "closest_document_5": df_embeddings['titulo'][top_indices[4]],
        "submitted_at": datetime.utcnow().isoformat()
    }
    
    print(f"Queueing message...")
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message)
    )
    
    print("Proposal submitted successfully")

    batch_scheduler_propuestas(QUEUE_URL, purge_queue=False)

    remitente = random.choice(REMITENTES)
    subject = random.choice(SUBJECT_EMAIL).format(clean_and_format_name(event['nombre']))

    print(f"Sending email...")
    send_gmail(event['correo'],
               subject,
               random.choice(RESPUESTAS_CORREO).format(clean_and_format_name(event['nombre']),
                                                       df_embeddings['titulo'][top_indices[0]].lower(),
                                                       remitente))
    

def construct_document_embeddings(event, context):

    folder = "documentos-programaticos/"
    files = read_all_files_from_s3_folder("zarruk",
                                          folder,
                                          file_extension=None)
    
    df_text = pd.DataFrame()

    for file in files:
        df_text = pd.concat([df_text,
                             generate_text_dataframe(file['content'],
                                                     file['key'])])

    # Generate current timestamp
    now = datetime.now()
    df_text['last_updated'] = now

    folder = "documentos-programaticos-processed"

    update_db(df_text,
              folder,
              'documentos_programaticos', ATHENA_DB, ATHENA_OUTPUT
              )

if __name__ == "__main__":

    queue_proposal({'propuesta': 'Quisiera proponer más árboles.',
                    'nombre': 'david',
                    'correo': 'davidzarruk@gmail.com'}, {})

#    batch_scheduler_propuestas({}, {})

#    construct_document_embeddings({}, {})

#    scrape_news({'source': 'semana'}, {})
#    get_candidate_sentiment({}, {})