import requests
import variables as config
import asyncio
import aiohttp
import chunks_extraction as sa_utility
import os
import shutil
from utils.logger import get_logger, write_json_to_separate_file
logger = get_logger()
#access token generation
def generate_access_token():
    try:
        url = config.accessTokenUrl
        payload = {
            'grant_type': config.accessTokenGrantType,
            'client_secret': config.accessTokenClientSecret,
            'client_id': config.accessTokenClientId,
            'redirect_uri':config.redirectUri,
            'code': config.accessTokenAuthCode
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  

        access_token = response.json().get('access_token')
        instance_url=response.json().get('instance_url')
        refresh_token =response.json().get('refresh_token')
        if not access_token:
            raise ValueError("Access token not found in response")
        return access_token,instance_url,refresh_token
    except Exception as e:
        logger.error(f"An error occurred while generating access token: {e}", exc_info=True)

def generate_refresh_token(refresh_token) :
    try:
        url = config.accessTokenUrl
        payload = {
            'grant_type': config.refreshTokenGrantType,
            'client_secret': config.refreshTokenClientSecret,
            'client_id': config.refreshTokenClientId,
            'refresh_token' :refresh_token    
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  

        access_token = response.json().get('access_token')

        if not access_token:
            raise ValueError("Access token not found in response")
        return access_token
    except Exception as e:
        logger.error(f"An error occurred while generating access token: {e}", exc_info=True)


# Make an API call to the specified URL with optional headers.
def make_api_call(url, headers=None):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  
        logger.info(f"API call successful for URL: {url}")
        return response.json()
    except requests.HTTPError as e:
        logger.error(f"HTTP error occurred for URL {url}: {e}, status code: {response.status_code}", exc_info=True)
    except Exception as e:
        logger.error(f"An error occurred during API call for URL {url}: {e}", exc_info=True)

#getting id 
def get_articles_list_id(access_token):
    try:
        lists_url = f"{config.hostUrl}/services/data/v57.0/query/?q=SELECT Id, Title, LastModifiedDate, KnowledgeArticleId FROM KnowledgeArticleVersion WHERE PublishStatus='Online'" 
      
        headers = {
                   "Authorization": f"Bearer {access_token}",
                   "Accept-Language": "en-US",
                  }
        lists_response = make_api_call(lists_url, headers)
        item_ids = [item["KnowledgeArticleId"] for item in lists_response.get("records", [])]             
        list_url_all=[] 

        print(item_ids)
        #getting all the other page urls and the article ids in them
        if 'nextRecordsUrl' in lists_response:
         for page in lists_response['nextRecordsUrl']:  
          if lists_response['nextRecordsUrl']:
            headers = {
                   "Authorization": f"Bearer {access_token}",
                   "Accept-Language": "en-US"
                  }
            lists_url_2 = f"{lists_url}{lists_response['nextRecordsUrl']}"
            lists_responses = make_api_call(lists_url_2, headers)
            item_id_all = [item["KnowledgeArticleId"] for item in lists_responses.get("records", [])]  
            
            item_ids=item_ids + item_id_all  
            lists_response=lists_responses
            list_url_all.append(lists_url_2)


            
    except Exception as e:
        logger.error(f"An error occurred while retrieving 'Articles' list ID: {e}", exc_info=True)
        
    return item_ids
#getting details
async def fetch_item_details(new_access_token,instance_url,item_id):
    item_url = f"{instance_url}/services/data/v57.0/support/knowledgeArticles/{item_id}"  
    headers = {
                "Authorization": f"Bearer {new_access_token}",
                "Accept-Language": "en-US"
               } 
    try: 
        async with aiohttp.ClientSession() as session:     
            async with session.get(item_url, headers=headers, timeout=20) as response:
              response.raise_for_status()  
              item_response = await response.json()  
                
            return {
                'raw_data': item_response
            } 
    except aiohttp.ClientError as e:
        logger.error(f"An error occurred during item details fetch: {e}", exc_info=True)
    except asyncio.TimeoutError:
        logger.error(f"Timeout occurred during item details fetch for item ID {item_id}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during item details fetch: {e}", exc_info=True)
# Make an asynchronous API call to retrieve items from a SharePoint list.
async def make_list_api_call(access_token, instance_url,itemIds,refresh_token):
    logger.info(f"Making API call for retreiving all the item details")
    batches = [itemIds[i:i+int(config.eachBatchCount)] for i in range(0, len(itemIds), int(config.eachBatchCount))]
    print(batches)
    try:
                 
                results_final=[]; 
                x=1      
                for eachBatch in batches:
                    tasks = []   
                    print(len(eachBatch))
                    # print("Next Batch")
                    new_access_token=generate_refresh_token(refresh_token)
                    print("New Access Token",new_access_token)
                    for item_id in eachBatch:
                        task = fetch_item_details(new_access_token,instance_url,item_id)
                        tasks.append(task)    
                    results = await asyncio.gather(*tasks)
                    results_final.append(results); 

                    # x=1
                    for individual_batch in results_final :
                        for individual_response in individual_batch :
                         write_json_to_separate_file(individual_response, f'salesForceResponse{x}.json')
                         x=x+1
                    logger.info("Writing individual responses into individual files is done.")
                    filtered_results = [result for result in results_final if result is not None]
                    data=await sa_utility.helper(config.input_path, config.output_path)
                    logger.info(f"API call for retreiving all the item details is successfully completed")
                    results_final.clear()
                    shutil.rmtree(config.input_path)
                    os.makedirs(config.input_path)

                return filtered_results
                   
    except aiohttp.ClientError as e:
        logger.error(f"An error occurred during API call for retrieving item details: {e}", exc_info=True)


#salesforce data extraction
async def extractData():
    try:
        access_token,instance_url,refresh_token = generate_access_token()

        print("Access Token",access_token,instance_url)
        logger.info("Access token generated successfully.")
        logger.debug(f"Access token: {access_token}")

        logger.info("Access token generated successfully.")
        logger.debug(f"Access token: {access_token}")

        itemIds = get_articles_list_id(access_token)
        logger.debug(f"Instance Url: {itemIds}")
        
        details= await make_list_api_call(access_token,instance_url,itemIds,refresh_token)
        logger.debug(f"Details: {details}")

        return details

    except Exception as e:
        logger.error(f"An error occurred during share point data extraction: {e}", exc_info=True)
