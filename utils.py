import pandas as pd
import json
import boto3
from io import StringIO


def upload_df_to_s3(df, bucket_name, key, file_format='csv'):
    s3 = boto3.client('s3')
    buffer = BytesIO()

    if file_format == 'csv':
        df.to_csv(buffer, index=False, encoding='utf-8')
        content_type = 'text/csv'
    elif file_format == 'json':
        df.to_json(buffer, orient='records', lines=True, force_ascii=False)
        content_type = 'application/json'
    else:
        raise ValueError("Unsupported file format. Use 'csv' or 'json'.")

    buffer.seek(0)  # Rewind the buffer to the beginning
    s3.put_object(Bucket=bucket_name, Key=key, Body=buffer, ContentType=content_type)


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