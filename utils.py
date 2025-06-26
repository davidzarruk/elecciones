import pandas as pd
import json
import boto3
from io import BytesIO
import re
from openai import OpenAI
import os


client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

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


def get_sentiment(candidatos, text, prompt):
    question = f"""
    {candidatos}
    Noticia: {text}
    """
    
    text = answer_question(question, prompt)
    
    print(text)
    data_json = json.loads(text)

    # Access elements like this:
    print(data_json["María José Pizarro"]["thinking"]) 

    data = {
        "thinking": re.search(r"<thinking>(.*?)</thinking>", text, re.DOTALL).group(1).strip(),
        "tono": re.search(r"<tono>(.*?)</tono>", text).group(1).strip(),
        "reason": re.search(r"<reason>(.*?)</reason>", text).group(1).strip(),
        "key_words": re.search(r"<key_words>(.*?)</key_words>", text).group(1).strip()
    }
    
    # Convertir a DataFrame
    return data["thinking"], data["tono"], data["reason"], data["key_words"]


def upload_df_to_s3(df, bucket_name, key):
    s3 = boto3.client('s3')
    buffer = BytesIO()

    df.to_csv(buffer, index=False, encoding='utf-8')
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
        df['source_file'] = key  # Optional: track where each row came from
        all_dfs.append(df)

    # Step 3: Concatenate all into a single DataFrame
    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df


def extract_canonical_urls(data, urls=[]):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "canonical_url":
                urls.append(value)
            elif isinstance(value, (dict, list)):
                extract_canonical_urls(value, urls)
    elif isinstance(data, list):
        for item in data:
            extract_canonical_urls(item, urls)

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


def get_data(soup):
    # Find all the script tags with type="application/ld+json"
    script_tags = soup.find_all('script', {'type': 'application/ld+json'})

    for script_tag in script_tags:
        try:
            # Load the JSON data from the script tag
            json_data = json.loads(script_tag.string)

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
                    'articleBody': [articleBody],
                    'date_published': [date_published],
                    'headline': [headline],
                    'description': [description],
                    'dateModified': [dateModified],
                    'dateline': [dateline],
                    'alternativeHeadline': [alternativeHeadline],
                    'keywords': [keywords],
                    'articleSection': [articleSection]
                    })
    
    return df