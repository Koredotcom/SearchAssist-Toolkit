import requests
from openpyxl import Workbook
import time
from configManager import read_config

def get_context(answer):
    contexts=[]
    context_urls=""
    for chunkData in answer['template']['chunk_result']['generative']:
        if chunkData['_source']['sent_to_LLM']==True:
            contexts.append(chunkData['_source']['chunkText'])
            context_urls+=chunkData['_source']['recordUrl']+","

    return contexts,context_urls

def search_assist_api(query):
    config=read_config(r'./config.json')
    auth_token=config.get('auth_token')
    app_id=config.get('app_id')
    url = f'https://searchassist-app.kore.ai/searchassistapi/external/stream/{app_id}/advancedSearch'
    headers = {
        'auth': auth_token,
        'Content-Type': 'application/json'
    }   
    data = {
        "query": query,
        # "indexPipelineId": "fip-e9035ff3-7efc-5257-bca7-75d72e72b599",
        "includeChunksInResponse": True
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        data=response.json()
        # print(data)
        # return data['template']['graph_answer']['payload']['center_panel']['data'][0]['snippet_content'][0]['answer_fragment']
        return data
    except requests.exceptions.RequestException as e:
        # This will catch any request-related errors
        print(f"Request failed: {e}")
        return None
    except KeyError as e:
        # This will catch errors in navigating the data dictionary
        print(f"Data parsing failed: Key {e} not found in the response")
        return None
def get_Bot_Response(query,truth):
    print(query)
    answer=search_assist_api(query)
    # type(answer)
    

    time.sleep(1)
    try:
        answerData={}
        answerData['query']=query
        answerData['ground_truth']=truth  
        context_data,context_url=get_context(answer)      
        answerData['context']=context_data
        answerData['context_url']=context_url
        isAnswerNone=(answer.get('template', {})
               .get('graph_answer', {})
               .get('payload', {})
               .get('center_panel', None))
        if(isAnswerNone==None):
            answerData['answer']="No Answer Found"
        else:
            answerData['answer']=answer['template']['graph_answer']['payload']['center_panel']['data'][0]['snippet_content'][0]['answer_fragment'] 
        
        # print(qualified_chunk)
        return answerData
    except KeyError as e:
        # This will catch errors in navigating the data dictionary
        print(f"Data parsing failed: Key {e} not found in the response")
        return None





# # Example usage
# query = "what is eva?"
# result = calculate_chunk_scores(query)
# print(result["template"]["chunk_result"]["generative"][0])
