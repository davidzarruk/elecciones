import requests
import json
from utils import extract_canonical_urls, sanitize_headers, get_data, upload_df_to_s3, \
    get_sentiment, read_df_from_s3, get_propuesta, \
    update_news_db, query_athena_to_df, filter_new_by_candidate_names
from params import SEMANA_PARAMS, SEMANA_HEADERS, SEMANA_URL, SEMANA_NUM_NEWS, \
    ATHENA_DB, ATHENA_TABLE, ATHENA_OUTPUT
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json


def scrape_semana_news(event, context):
    
    print(f"Getting URLs from first {SEMANA_NUM_NEWS} news to fetch...")
    response = requests.get(SEMANA_URL,
                            headers=sanitize_headers(SEMANA_HEADERS),
                            params=SEMANA_PARAMS)
    
    links = extract_canonical_urls(json.loads(response.text))

    print("Getting already scraped URLs")
    query = "SELECT DISTINCT url FROM news_table WHERE source = 'semana'"
    df_urls = query_athena_to_df(query, "news_db", "s3://zarruk/athena-results/")
    
    url = "https://www.semana.com"
    
    if len(df_urls)>0:
        existing_links = [link.replace(url, "") for link in df_urls['url']]

        # Keep only links that have not been scraped
        links = list(set(links) - set(existing_links))
    
    df = pd.DataFrame()

    print("Scraping news...")
    # Perform GET requests for each filtered hyperlink
    for i, link in enumerate(links):
            
        full_url = url.rstrip('/') + link  # Construct the full URL by combining the base URL with the relative link
        link_response = requests.get(full_url)
        
        soup = BeautifulSoup(link_response.content, "html.parser")
        df_noticia = get_data(soup)
        df_noticia['url'] = full_url

        df = pd.concat([df, df_noticia])

    # Generate current timestamp
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    run_str = now.strftime("%H-%M")
    source_str = "semana"
    folder = "noticias-politica"

    update_news_db(df, folder, source_str, date_str, run_str, ATHENA_TABLE, ATHENA_DB, ATHENA_OUTPUT)


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

    scrape_semana_news({}, {})

