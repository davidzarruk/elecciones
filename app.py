import requests
import json
from utils import extract_canonical_urls, sanitize_headers, get_data, upload_df_to_s3, \
    read_all_csvs_from_s3_folder, get_sentiment
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

        df = pd.concat([df, get_data(soup)])

    # Generate current timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    upload_df_to_s3(
        df,
        bucket_name="zarruk",
        key=f"semana-politica/news_data_{timestamp}.csv"
    )

def get_candidate_sentiment(event, context):
    prompt = open('prompt.txt', 'r').read()
    with open('lista_candidatos.txt', 'r', encoding='utf-8') as f:
        candidates = f.readlines()

    names = [line.strip() for line in candidates if line.strip() and not line.lower().startswith("lista")]
    
    df = read_all_csvs_from_s3_folder(
        bucket_name='zarruk',
        folder_prefix='semana-politica'
    )

    df = df.drop_duplicates()
    df = df[~df['articleBody'].isna()]

    pattern = '|'.join([re.escape(name) for name in names])
    df = df[df['articleBody'].str.contains(pattern, case=False, na=False)]

    df_all_sentiments = pd.DataFrame()

    for article in df['articleBody']:
        df_sentiment = get_sentiment(candidates, article, prompt)
        df_all_sentiments = pd.concat([df_all_sentiments, df_sentiment], axis=0)

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


if __name__ == "__main__":

    get_candidate_sentiment({}, {})

