import pandas as pd
import json
import boto3
from io import BytesIO
import re
from openai import OpenAI
import os
import time
from bs4 import BeautifulSoup
import requests


client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def run_athena_query(query, database, output_location):
    client = boto3.client('athena', region_name='us-east-2')
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output_location}
    )
    return response['QueryExecutionId']


def filter_new_by_candidate_names(df, candidates):
    names = [line.strip() for line in candidates if line.strip() and not line.lower().startswith("lista")]

    pattern = '|'.join([re.escape(name) for name in names])
    df = df[df['articlebody'].str.contains(pattern, case=False, na=False)]
    return df


def query_athena_to_df(query, database, output_location):
    # Iniciar la ejecución del query
    athena_client = boto3.client('athena', region_name='us-east-2')
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output_location}
    )
    query_execution_id = response['QueryExecutionId']

    # Esperar a que se complete
    while True:
        status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        state = status['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(2)

    if state != 'SUCCEEDED':
        raise Exception(f"Athena query failed with state: {state}")

    # Construir la ruta del archivo CSV
    result_file = f"{output_location}{query_execution_id}.csv"

    # Leer el archivo en un DataFrame
    df = pd.read_csv(result_file)
    return df


def answer_question(question, prompt_data, tokens=1000):
    modelId = "gpt-4o"

    input = {
        "modelId": modelId,
        "contentType": "application/json",
        "accept": "*/*"
    }
    
    completion = client.chat.completions.create(
        model=input['modelId'],
        messages=[
            {
                "role": "user",
                "content": prompt_data + " " + question
            }
        ]
    )

    response_body = completion.choices[0].message.content

    return response_body


def extract_json(text):
    match = re.search(r'{[\s\S]*}', text)
    if match:
        return match.group()
    else:
        raise ValueError("No JSON found in the input")


def get_sentiment(candidatos, text, prompt):
    question = f"""
    {candidatos}
    Noticia: {text}
    """
    
    response = answer_question(question, prompt)
    print(response)
    
    data_json = json.loads(extract_json(response))

    df = pd.DataFrame(data_json)

    df_reshaped = (
        df.stack()
        .unstack(0)
    ).reset_index()

    df_reshaped['articlebody'] = text

    # Convertir a DataFrame
    return df_reshaped


def update_db(df, folder,
              athena_table, athena_db, athena_output, 
              date_str, run_str, source_str=""):
    
    if source_str != "":
        s3_key = f"{folder}/source={source_str}/date={date_str}/run={run_str}/data.csv"
    else:
        s3_key = f"{folder}/date={date_str}/run={run_str}/data.csv"

    upload_df_to_s3(
        df,
        bucket_name="zarruk",
        key=s3_key
    )

    print(f"File uploaded to: {s3_key}")

    # 🔹 Ejecutar query para agregar partición a Athena
    if source_str != "":
        partition_query = f"""
        ALTER TABLE {athena_table} ADD IF NOT EXISTS
        PARTITION (source='{source_str}', date='{date_str}', run='{run_str}')
        LOCATION 's3://zarruk/{folder}/source={source_str}/date={date_str}/run={run_str}/'
        """
    else:
        partition_query = f"""
        ALTER TABLE {athena_table} ADD IF NOT EXISTS
        PARTITION (date='{date_str}', run='{run_str}')
        LOCATION 's3://zarruk/{folder}/date={date_str}/run={run_str}/'
        """

    query_id = run_athena_query(
        query=partition_query,
        database=athena_db,
        output_location=athena_output
    )

    print(f"Athena partition query submitted. QueryExecutionId: {query_id}")



def get_propuesta(candidatos, text, prompt, json_propuestas, fuente):
    question = f"""
    {candidatos}
    JSON de propuestas: {json_propuestas}
    Noticia: {text}
    Fuente: {fuente}
    """
    
    response = answer_question(question, prompt)
    
    data_json = json.loads(extract_json(response))

    return data_json





def upload_df_to_s3(df, bucket_name, key):
    s3 = boto3.client('s3')
    buffer = BytesIO()

    df.to_csv(buffer, index=False, header=False, encoding='utf-8')
    content_type = 'text/csv'

    buffer.seek(0)  # Rewind the buffer to the beginning
    s3.put_object(Bucket=bucket_name, Key=key, Body=buffer, ContentType=content_type)


def read_df_from_s3(bucket_name, key):
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket_name, Key=key)
    body = response['Body'].read()

    df = pd.read_csv(BytesIO(body), encoding='utf-8')

    return df


def read_all_csvs_from_s3_folder(bucket_name, folder_prefix):
    s3 = boto3.client('s3')
    
    # Step 1: List all CSV objects in the folder
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_prefix)
    csv_keys = [
        obj['Key'] for obj in response.get('Contents', [])
        if obj['Key'].endswith('.csv')
    ]

    all_dfs = []

    # Step 2: Loop through and read each CSV
    for key in csv_keys:
        obj = s3.get_object(Bucket=bucket_name, Key=key)
        df = pd.read_csv(obj['Body'], encoding='utf-8')
        all_dfs.append(df)

    # Step 3: Concatenate all into a single DataFrame
    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df


def get_links(response, source, params):
    if source == "LSV":
        return get_links_LSV(response)
    elif source == "semana":
        return get_links_semana(json.loads(response), params)
    elif source == "elespectador":
        return get_links_elespectador(response, params)
    elif source == "wradio":
        return get_links_wradio(response, params)
    elif source == "caracol":
        return get_links_wradio(response, params)


def get_links_LSV(response):
    # Parse the HTML
    soup = BeautifulSoup(response, 'html.parser')

    # Find all article links
    article_links = []
    for article in soup.find_all('article'):
        a_tag = article.find('a', href=True)
        if a_tag:
            article_links.append(a_tag['href'])

    return list(set(article_links))

def get_links_wradio(response, params):
    soup = BeautifulSoup(response, "html.parser")
    all_links = soup.find_all('a')
    links = [f'{params["base_url"]}{a.get("href")}' for a in all_links if a.get("href", "").startswith("/2025/")]
    return list(set(links))


def get_links_elespectador(response, params):
    # Extract all hrefs that start with "/politica"
    links = []
    elements = json.loads(response)['content_elements']
    for element in elements:
        links.append(element['canonical_url'])

    # Remove duplicates if needed
    links = list(set(links))
    
    links = [f"{params['base_url']}{link}" for link in links]
    return links


def get_links_semana(data, params, urls=[]):

    if isinstance(data, dict):
        for key, value in data.items():
            if key == "canonical_url":
                urls.append(value)
            elif isinstance(value, (dict, list)):
                get_links_semana(value, params, urls=urls)
    elif isinstance(data, list):
        for item in data:
            get_links_semana(item, params, urls=urls)

    urls = [f"{params['base_url']}{link}" for link in urls]

    return urls

def sanitize_headers(headers):
    safe_headers = {}
    for k, v in headers.items():
        try:
            v.encode("latin-1")
            safe_headers[k] = v
        except UnicodeEncodeError:
            # Skip or clean this header value
            safe_headers[k] = v.encode("ascii", "ignore").decode("ascii")
    return safe_headers


# Helper function to safely get attribute content
def get_content(tag, attr='content'):
    return tag.get(attr) if tag else None

def get_articles(link, session, source):
    if source == "LSV":
        return get_articles_LSV(link, session)
    elif source == "semana":
        return get_articles_semana(link, session)
    elif source == "elespectador":
        return get_articles_elespectador(link, session)
    elif source == "wradio":
        return get_articles_wradio(link, session)
    elif source == "caracol":
        return get_articles_wradio(link, session)


def get_articles_LSV(link, session):
    print(f"Started request for article: {link}")
    link_response = session.get(link)
    soup = BeautifulSoup(link_response.content, "html.parser")
    print(f"Got data for article: {link}")

    # Extract article data into dictionary
    article_data = {
        "date_published": get_content(soup.find("meta", property="article:published_time")),
        "link": link,
        "headline": get_content(soup.find("meta", property="og:title")),
        "articleBody": " ".join([
            p.get_text(strip=True)
            for p in soup.find("div", class_="entry-content").find_all("p")
        ]),
        "description": get_content(soup.find("meta", attrs={"name": "description"})),
        "dateModified": get_content(soup.find("meta", property="article:modified_time")),
        "dateline": "",
        "alternativeHeadline": "",
        "keywords": "",
        "articleSection": ""
    }

    # Create DataFrame
    df = pd.DataFrame([article_data])  # Wrap in list to create one-row DataFrame

    return df


def get_articles_wradio(link, session):
    print(f"Started request for article: {link}")
    link_response = session.get(link)
    soup = BeautifulSoup(link_response.content, "html.parser")
    print(f"Got data for article: {link}")

    # Find all the script tags with type="application/ld+json"
    script_tags = soup.find_all('script', {'type': 'application/ld+json'})

    for script_tag in script_tags:
        try:
            # Load the JSON data from the script tag
            raw_json = script_tag.get_text()
            json_data = json.loads(raw_json.replace('\n', '').replace('\t', ''))

            # Check if the desired keys are present
            if 'datePublished' in json_data and 'headline' in json_data and 'description' in json_data:
                # Extract the 'datePublished', 'headline', and 'description' values
                date_published = json_data['datePublished']
                headline = json_data['headline']
                description = json_data['description']
                dateModified = json_data["dateModified"]
                articleBody = json_data["articleBody"]

                break

        except json.JSONDecodeError:
            # Skip this script tag if there's an error decoding JSON
            date_published = 'NA'
            headline = 'NA'
            description = 'NA'
            articleBody = 'NA'
            dateModified = 'NA'
            pass

    df = pd.DataFrame({
                    'date_published': [date_published],
                    'link': [link],
                    'headline': [headline],
                    'articleBody': [articleBody],
                    'description': [description],
                    'dateModified': [dateModified],
                    'dateline': [""],
                    'alternativeHeadline': [""],
                    'keywords': [""],
                    'articleSection': [""]
                    })
    return df


def get_articles_semana(link, session):
    print(f"Started request for article: {link}")
    link_response = session.get(link)
    soup = BeautifulSoup(link_response.content, "html.parser")
    print(f"Got data for article: {link}")

    # Find all the script tags with type="application/ld+json"
    script_tags = soup.find_all('script', {'type': 'application/ld+json'})

    for script_tag in script_tags:
        try:
            # Load the JSON data from the script tag
            raw_json = script_tag.get_text()
            json_data = json.loads(raw_json.replace('\n', '').replace('\t', ''))
            
            # Check if the desired keys are present
            if 'datePublished' in json_data and 'headline' in json_data and 'description' in json_data:
                # Extract the 'datePublished', 'headline', and 'description' values
                date_published = json_data['datePublished']
                headline = json_data['headline']
                description = json_data['description']
                dateModified = json_data["dateModified"]
                dateline = json_data["dateline"]
                alternativeHeadline = json_data["alternativeHeadline"]
                keywords = json_data["keywords"]
                articleSection = json_data["articleSection"]
                articleBody = json_data["articleBody"]

                break
                
        except json.JSONDecodeError:
            # Skip this script tag if there's an error decoding JSON
            date_published = 'NA'
            headline = 'NA'
            description = 'NA'
            articleBody = 'NA'
            dateModified = 'NA'
            dateline = 'NA'
            alternativeHeadline = 'NA'
            keywords = 'NA'
            articleSection = 'NA'
            pass
    
    df = pd.DataFrame({
                    'date_published': [date_published],
                    'link': [link],
                    'headline': [headline],
                    'articleBody': [articleBody],
                    'description': [description],
                    'dateModified': [dateModified],
                    'dateline': [dateline],
                    'alternativeHeadline': [alternativeHeadline],
                    'keywords': [keywords],
                    'articleSection': [articleSection]
                    })
    
    return df


def get_articles_elespectador(link, session):
    print(f"Started request for article: {link}")
    link_response = session.get(link)
    soup = BeautifulSoup(link_response.content, "html.parser")
    print(f"Got data for article: {link}")

    # Find all the script tags with type="application/ld+json"
    script_tags = soup.find_all('script', {'type': 'application/ld+json'})

    for script_tag in script_tags:
        try:
            # Load the JSON data from the script tag
            raw_json = script_tag.get_text()
            json_data = json.loads(raw_json.replace('\n', '').replace('\t', ''))
            
            # Check if the desired keys are present
            if 'datePublished' in json_data and 'headline' in json_data and 'description' in json_data:
                # Extract the 'datePublished', 'headline', and 'description' values
                date_published = json_data['datePublished']
                headline = json_data['headline']
                description = json_data['description']
                dateModified = json_data["dateModified"]
                alternativeHeadline = json_data["alternativeHeadline"]
                articleSection = json_data["articleSection"]
                articleBody = json_data["articleBody"]

                break
                
        except json.JSONDecodeError:
            # Skip this script tag if there's an error decoding JSON
            date_published = 'NA'
            headline = 'NA'
            description = 'NA'
            articleBody = 'NA'
            dateModified = 'NA'
            alternativeHeadline = 'NA'
            articleSection = 'NA'
            pass
    
    df = pd.DataFrame({
                    'date_published': [date_published],
                    'link': [link],
                    'headline': [headline],
                    'articleBody': [articleBody],
                    'description': [description],
                    'dateModified': [dateModified],
                    'dateline': [""],
                    'alternativeHeadline': [alternativeHeadline],
                    'keywords': [""],
                    'articleSection': [articleSection]
                    })
    
    return df


def get_df_from_queue(queue_url):
    sqs = boto3.client('sqs')
    
    all_messages = []
    delete_entries = []

    while True:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1
        )

        messages = response.get('Messages', [])
        if not messages:
            break

        for msg in messages:
            body = json.loads(msg['Body'])
            all_messages.append(body)

            delete_entries.append({
                'Id': msg['MessageId'],
                'ReceiptHandle': msg['ReceiptHandle']
            })

        # Delete processed messages
        if delete_entries:
            sqs.delete_message_batch(
                QueueUrl=queue_url,
                Entries=delete_entries
            )
            delete_entries.clear()

    if not all_messages:
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(all_messages)

    # Ensure all columns exist
    expected_columns = ['proposal_id', 'nombre', 'correo', 'propuesta', 'submitted_at']
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    return df