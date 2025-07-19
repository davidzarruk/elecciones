import requests
import json
from utils import get_links, get_articles, update_db, \
    get_sentiment, read_df_from_s3, get_propuesta, clean_and_format_name, \
    query_athena_to_df, filter_new_by_candidate_names, send_gmail, batch_scheduler_propuestas
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
    folder = "noticias-politica"

    if len(df)>0:
        update_db(df, folder,
                  ATHENA_TABLE, ATHENA_DB, ATHENA_OUTPUT, 
                  date_str, run_str, source_str)
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

        update_db(df_all_sentiments, 'sentiments-news-table',
                  'sentiments_table', ATHENA_DB, ATHENA_OUTPUT, 
                  date_str, run_str)
        
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

    message = {
        "proposal_id": str(uuid.uuid4()),
        "nombre": event['nombre'],
        "correo": event['correo'],
        "propuesta": event['propuesta'],
        "submitted_at": datetime.utcnow().isoformat()
    }
    
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message)
    )
    
    print("Proposal submitted successfully")

    batch_scheduler_propuestas(QUEUE_URL, purge_queue=False)

    remitente = random.choice(REMITENTES)
    subject = random.choice(SUBJECT_EMAIL).format(clean_and_format_name(event['nombre']))
    
    send_gmail(event['correo'],
               subject,
               random.choice(RESPUESTAS_CORREO).format(clean_and_format_name(event['nombre']),
                                                       remitente))
    


if __name__ == "__main__":

    queue_proposal({'propuesta': 'prueba 1',
                    'nombre': 'david',
                    'correo': 'davidzarruk@gmail.com'}, {})

#    batch_scheduler_propuestas({}, {})

    
