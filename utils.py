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
import base64
import json
import requests
from datetime import datetime
import io
import os
import base64
import requests
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from pdfminer.high_level import extract_text as extract_pdf_text
from tika import parser
import tempfile
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import ast
from params import ATHENA_DB, ATHENA_OUTPUT


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
              partition_str=""):

    # 🔹 Construct S3 key and upload file
    s3_key = f"{folder}/data.csv"

    upload_df_to_s3(
        df,
        bucket_name="zarruk",
        key=s3_key
    )

    print(f"File uploaded to: {s3_key}")

    s3_uri = f"s3://zarruk/{folder}/"

    # 🔹 Construct Athena query based on whether partition info is provided
    if partition_str:
        partition_query = f"""
        ALTER TABLE {athena_table} ADD IF NOT EXISTS
        PARTITION ({partition_str})
        LOCATION '{s3_uri}'
        """
    else:
        partition_query = f"""
        ALTER TABLE {athena_table}
        SET LOCATION '{s3_uri}'
        """

    query_id = run_athena_query(
        query=partition_query,
        database=athena_db,
        output_location=athena_output
    )

    print(f"Athena update query submitted. QueryExecutionId: {query_id}")



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


def read_all_files_from_s3_folder(bucket_name, folder_prefix, file_extension=None):
    """
    Reads files from an S3 folder.
    
    Args:
        bucket_name (str): S3 bucket name.
        folder_prefix (str): Folder path in the bucket.
        file_extension (str or None): Extension to filter by (e.g., '.csv', '.pdf'). If None, all files are included.

    Returns:
        If CSVs: pd.DataFrame
        If PDFs: list of dicts {'key': ..., 'content': ...}
        If None: list of dicts {'key': ..., 'content': ...}
    """
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_prefix)

    keys = [
        obj['Key'] for obj in response.get('Contents', [])
        if not obj['Key'].endswith('/') and (file_extension is None or obj['Key'].endswith(file_extension))
    ]

    results = []

    for key in keys:
        obj = s3.get_object(Bucket=bucket_name, Key=key)

        if key.endswith('.csv'):
            df = pd.read_csv(obj['Body'], encoding='utf-8')
            results.append(df)

        elif key.endswith('.pdf'):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(obj['Body'].read())
                tmp_file_path = tmp_file.name

            try:
                text = extract_pdf_text(tmp_file_path)
                results.append({
                    'key': key.replace(folder_prefix, "").replace("Documento - ", "").replace(".pdf", ""),
                    'content': text
                })
            finally:
                os.remove(tmp_file_path)

        else:
            content = obj['Body'].read().decode('utf-8', errors='ignore')
            results.append({'key': key, 'content': content})

    if file_extension == '.csv':
        if not results:
            raise ValueError("No CSV files found.")
        return pd.concat(results, ignore_index=True)

    return results



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


def get_df_from_queue(queue_url, purge_queue=True):
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

            if purge_queue:
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

def get_access_token():
    """
    Use the refresh token to get a new access token from Google OAuth.
    """
    TOKEN_URI = 'https://oauth2.googleapis.com/token'
    payload = {
        'client_id': os.environ["CLIENT_ID"],
        'client_secret': os.environ["CLIENT_SECRET"],
        'refresh_token': os.environ["REFRESH_TOKEN"],
        'grant_type': 'refresh_token',
    }

    response = requests.post(TOKEN_URI, data=payload)
    response.raise_for_status()
    access_token = response.json().get('access_token')
    return access_token


def send_email_ses(to_email, subject, body_text, from_email="davidzarruk@gmail.com"):
    ses = boto3.client('ses', region_name='us-east-1')  # o la región donde activaste SES

    response = ses.send_email(
        Source=from_email,
        Destination={
            'ToAddresses': [to_email],
        },
        Message={
            'Subject': {
                'Data': subject,
                'Charset': 'UTF-8'
            },
            'Body': {
                'Text': {
                    'Data': body_text,
                    'Charset': 'UTF-8'
                }
            }
        }
    )
    print("Correo enviado con SES:", response)


def send_gmail(to_email, subject, body_text):
    access_token = get_access_token()

    # Properly encode subject with UTF-8 using email.mime
    message = MIMEText(body_text, 'plain', 'utf-8')
    message['To'] = to_email
    message['From'] = formataddr((str(Header('Propuestas Fajardo', 'utf-8')), 'me'))
    message['Subject'] = str(Header(subject, 'utf-8'))

    # Encode message
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Send via Gmail API
    url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    body = {
        'raw': raw_message
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code != 200:
        print("Gmail API Error:", response.text)
        raise Exception("Failed to send email")

    print("Email sent successfully.")
    return response.json()


def batch_scheduler_propuestas(queue_url, purge_queue):
    s3 = boto3.client('s3')

    df = get_df_from_queue(queue_url, purge_queue=False)

    if len(df)>0:
        # Create CSV in memory
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, header=False)

        # Save to S3 (organized by date/hour)
        now = datetime.utcnow()
        dt = now.strftime('%Y-%m-%d')
        hr = now.strftime('%H')
        s3_key = f"proposals/date={dt}/hour={hr}"

        s3.put_object(Bucket="zarruk",
                      Key=f"{s3_key}/proposals.csv",
                      Body=csv_buffer.getvalue())

        print(f"Stored {len(df)} proposals to {s3_key}")

        # 🔹 Construct Athena query based on whether partition info is provided
        partition_query = f"""
        ALTER TABLE propuestas_table ADD IF NOT EXISTS
        PARTITION (date='{dt}', hour='{hr}')
        LOCATION 's3://zarruk/{s3_key}/'
        """

        run_athena_query(
            query=partition_query,
            database=ATHENA_DB,
            output_location=ATHENA_OUTPUT
        )

    else:
        print(f"No new proposals to store")


def clean_and_format_name(name):
    if not isinstance(name, str):
        return name  # Return the value as is if it's not a string (e.g., NaN)
    
    # Remove country code in parentheses
    name_cleaned = re.sub(r'\s*\(\w{3}\)$', '', name)
    # Convert to title case
    name_formatted = name_cleaned.title()
    return name_formatted


def get_embedding(prompt_data):

    bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')  # Change region if needed

    body = json.dumps({"inputText": prompt_data})
    modelId = "amazon.titan-embed-text-v1"  # (Change this to try different embedding models)
    accept = "application/json"
    contentType = "application/json"

    response = bedrock_runtime.invoke_model(
        body=body, modelId=modelId, accept=accept, contentType=contentType
    )
    response_body = json.loads(response.get("body").read())

    embedding = response_body.get("embedding")
    return embedding


def generate_text_dataframe(text, title):
    embeddings = []

    embeddings.append(get_embedding(text[:16000]))

    df_text = pd.DataFrame({'title': title, 'embedding': embeddings})
    return df_text


def compute_closest_texts(target_embedding, embeddings, embedding_column='embedding'):
    # Asegúrate de que target_embedding sea un array numpy bidimensional
    vector_array = np.array(target_embedding).reshape(1, -1)

    # Convertir cada valor en la columna a una lista de floats (en caso de que sea string)
    matrix_array = np.array([
        ast.literal_eval(emb) if isinstance(emb, str) else emb
        for emb in embeddings[embedding_column]
    ])

    # Calcular la similitud coseno
    similarities = cosine_similarity(vector_array, matrix_array).flatten()

    # Obtener los índices ordenados de mayor a menor similitud (excluyendo el mismo texto si aplica)
    top_indices = np.argsort(similarities)[::-1]

    return top_indices