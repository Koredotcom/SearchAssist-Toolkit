import os
import json
import requests
import variables as config
from utils.logger import get_logger
logger = get_logger()
def ingest_new_data(json_file):
  logger.info("data ingestion started")
  botId=config.SA_botId
  Auth= config.SA_Auth
  url= config.SA_url
  urls=url+"searchassistapi/external/stream/"
  urls+=botId+'/ingest?contentSource=manual&extractionType=data&index=true'
  payload = json.dumps({"documents": json_file,"name":"latest data"})
  headers = {
    'Content-Type': 'application/json',
    'Auth': Auth
  }
  response = requests.post(urls, headers=headers, data=payload,proxies=config.proxies,verify=False)
  if response.status_code == 200:
    logger.info("data ingested successfully")
    print("data ingested")
  else:
    logger.info("error occured in data ingestion")
    print("Error:", response.text)
  return response.status_code

