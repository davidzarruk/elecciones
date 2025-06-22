import pandas as pd
import json


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