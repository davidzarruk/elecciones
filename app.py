import requests
import json
from utils import extract_canonical_urls, sanitize_headers, get_data, upload_df_to_s3, \
    read_all_csvs_from_s3_folder, get_sentiment, read_df_from_s3, get_propuesta
from params import SEMANA_PARAMS, SEMANA_HEADERS, SEMANA_URL, SEMANA_NUM_NEWS
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

    url = "https://www.semana.com/"
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
    date_str = now.strftime("%Y-%m-%d")    # para la partición date
    run_str = now.strftime("%H%M")         # para la partición run (ej: "0830", "1230")

    s3_key = f"noticias-politica/source=semana/date={date_str}/run={run_str}/data.csv"

    # Guardar CSV en ruta particionada
    upload_df_to_s3(
        df,
        bucket_name="zarruk",
        key=s3_key
    )

    print(f"File uploaded to: {s3_key}")



def keep_unique_news(df_news):
    df = read_df_from_s3(
        bucket_name="zarruk",
        key=f"cleaned_news/cleaned_news.csv"
    )
    
    df = pd.concat([df, df_news])

    df = df.drop_duplicates()
    df = df[~df['articleBody'].isna()]

    upload_df_to_s3(
        df,
        bucket_name="zarruk",
        key=f"cleaned_news/cleaned_news.csv"
    )


def filter_new_by_candidate_names(df, candidates):
    names = [line.strip() for line in candidates if line.strip() and not line.lower().startswith("lista")]

    pattern = '|'.join([re.escape(name) for name in names])
    df = df[df['articleBody'].str.contains(pattern, case=False, na=False)]
    return df


def get_candidate_sentiment(event, context):
    prompt = open('prompt.txt', 'r').read()
    with open('lista_candidatos.txt', 'r', encoding='utf-8') as f:
        candidates = f.readlines()
    
    print("Reading cleaned news")
    df = read_df_from_s3(
        bucket_name="zarruk",
        key=f"cleaned_news/cleaned_news.csv"
    )

    print("Filtering by candidates")
    df = filter_new_by_candidate_names(df, candidates)
    df = df.sort_values('date_published', ascending=False).reset_index(drop=True)
    
    print(f"Keeping {len(df)} news in total")

    print(df['date_published'])

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

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

