import requests
import json
from utils import get_links, get_articles, upload_df_to_s3, \
    get_sentiment, read_df_from_s3, get_propuesta, \
    update_news_db, query_athena_to_df, filter_new_by_candidate_names
from params import NUM_NEWS, QUERY_PARAMS, ATHENA_TABLE, ATHENA_DB, ATHENA_OUTPUT
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json



def scrape_news(event, context):

    # Start requests session
    session = requests.Session()

    print(f"Scraping {event['source']}. Getting URLs from first {NUM_NEWS} news to fetch...")
    response = session.get(QUERY_PARAMS[event['source']]['api_url'],
                           params=QUERY_PARAMS[event['source']]['params']).text
    
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
        update_news_db(df, folder, source_str, date_str, run_str, ATHENA_TABLE, ATHENA_DB, ATHENA_OUTPUT)
    else:
        print("No news to update.")


def get_candidate_sentiment(event, context):
    prompt = open('prompt.txt', 'r').read()
    with open('lista_candidatos.txt', 'r', encoding='utf-8') as f:
        candidates = f.readlines()
    
    print("Reading cleaned news")
    query = "SELECT DISTINCT * FROM news_table WHERE source = 'semana'"
    database = "news_db"
    output_location = "s3://zarruk/athena-results/"

    df = query_athena_to_df(query, database, output_location)

    print("Filtering by candidates")
    df = filter_new_by_candidate_names(df, candidates)

    df_all_sentiments = pd.DataFrame()

    print("Getting sentiments")
    for article in df['articleBody']:
        try:
            df_sentiment = get_sentiment(candidates, article, prompt)
            df_all_sentiments = pd.concat([df_all_sentiments, df_sentiment], axis=0)
            print(f"df shape: {df_all_sentiments.shape}")
        except Exception as e:
            print(f"Skipping article due to error: {e}")

    df_all_sentiments = pd.merge(left=df_all_sentiments,
                                 right=df,
                                 on='articleBody')

    # Generate current timestamp
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    run_str = now.strftime("%H-%M")
    source_str = "semana"


    upload_df_to_s3(
        df_all_sentiments,
        bucket_name="zarruk",
        key=f"sentiments-news/sentiments_all_candidates_{timestamp}.csv"
    )


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




if __name__ == "__main__":

    scrape_news({'source': 'elespectador'}, {})

