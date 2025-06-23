import requests
import json
from utils import extract_canonical_urls, sanitize_headers, get_data, upload_df_to_s3
import pandas as pd
import pandas as pd
from bs4 import BeautifulSoup


def handler(event, context):
    url = "https://www.semana.com/pf/api/v3/content/fetch/content-apir"
    params = {
        "query": '{"feedOffset":9,"feedSize":50,"includeSections":"politica","sourceInclude":"canonical_url,_id,promo_items,headlines.basic,subheadlines.basic,description.basic,subtype,publish_date,taxonomy,copyright"}',
        "d": "7730",
        "mxId": "00000000",
        "_website": "semana"
    }

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Cookie": "_ga=GA1.1.1191394108.1661543491; G_ENABLED_IDPS=google; _cb=Dsqyd2C1x1TI8yoHn; _chartbeat2=.1661543509533.1733159429346.0000000000000001.BjmQrPCWqbIOBQpCxuCNvJsnCsOTO-.1; cto_bundle=zZwkK191MVF6Z0c2T2lZRERMa2gxbGozNzlKeWpEc2xTNyUyQlB1Sk1rbWRYOEUyd3R6VG50anVZVFB3RGFlUVJrU21WN2c1cFFOZ1EycDFoZDAxVjM4eWFrekZ4eFJ3ZHB0eHJQaFJhRXNDTTVFMzRUSDdRa1RNYjdEdXluSkNxd083Z01NeU1VZUMlMkZka2d4aEFSbmhyMFdaR0tBaENYM0dmcGZtejdsQk4lMkZwTDlTdjAyJTJGNzVjaSUyQmFnOUtITGxBTExZbVhO; _ga_WM4PJWMJZ5=GS2.1.s1750629127$o23$g1$t1750629143$…UyQmhmd3h2THBaNXZ1aDBXV0JRcmxhTSUyQmFzNU5mM0U2RnN0a2ZPcVR2M0I4VSUyQnFxUTdkTm9EUkZnbGVSZzFSS3FhRlNIcGtDZyUzRCUzRA; __eoi=ID=15c24c255d11b87d:T=1748712316:RT=1748712316:S=AA-AfjY2Qk6V4ABhIa--gkX2Oacq; FCNEC=%5B%5B%22AKsRol9HBBK9MCizHR82l0kcLpJaMhxl1Lzv8iv6ldH2RXsGAK3_KBQ0qjPogC022pKSPwDDCnN2rgFDrAjATWkpqBmORcJBEaznNXHP-wuEr_cN96NgHJNEvhGdmS9NejSEXbz0EMo4dkKxJ97fzUPBxixEBIPyqg%3D%3D%22%5D%5D; AKA_A2=A; RT=\"z=1&dm=semana.com&si=shac9g7ghz&ss=mc87dpdh&sl=0&tt=0\"; __reveal_ut=085df42f-7a36-409d-5df9-4dc591d5b2c0",
        "Host": "www.semana.com",
        "If-Modified-Since": "1750628442585",
        "Pragma": "no-cache",
        "Priority": "u=4",
        "Referer": "https://www.semana.com/politica/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "TE": "trailers",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0"
    }


    print("Getting URLs from first 100 news to fetch...")
    response = requests.get(url, headers=sanitize_headers(headers), params=params)
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

    upload_df_to_s3(
        df,
        bucket_name="zarruk",  # Replace with your bucket name
        key="semana-politica/news_data.csv",  # Replace with your desired S3 path
        file_format="csv"
    )
    
if __name__ == "__main__":

    handler({}, {})

