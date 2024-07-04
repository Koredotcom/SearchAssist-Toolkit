import os
from dotenv import load_dotenv

load_dotenv()

#LLM 
llm_used=os.environ.get("llm_used")

 
# OpenAI Configuration
OPENAI_KEY =os.environ.get("open_ai_key")
openAI_model=os.environ.get("openai_model")
openAI_apibase=os.environ.get("openAI_apibase")

#azure open ai
AZURE_OPENAI_KEY= os.environ.get("AZURE_OPENAI_KEY")
API_BASE=os.environ.get("API_BASE")
Azure_model=os.environ.get("azure_model")
userSubDomain=os.environ.get("userSubDomain")
deployment= os.environ.get("deployment")
Apiversion=os.environ.get("Apiversion")

# Access Token Configuration
accessTokenUrl = f"https://{os.environ.get('test_env')}.salesforce.com/services/oauth2/token"
hostUrl = os.environ.get('hostUrl')
accessTokenGrantType = "authorization_code"
accessTokenClientId = os.environ.get('clientId')
accessTokenClientSecret = os.environ.get('clientSecret')
redirectUri = os.environ.get('redirectUri')
accessTokenAuthCode =os.environ.get('accessTokenAuthCode')

#Refresh Token Configuration
refreshTokenUrl = f"https://{os.environ.get('test_env')}.salesforce.com/services/oauth2/token"
refreshTokenGrantType = "refresh_token"
refreshTokenClientId = os.environ.get('clientId')
refreshTokenClientSecret = os.environ.get('clientSecret')

#EachBatchCount
eachBatchCount =os.environ.get('eachBatchCount')

#searchassist cred
SA_botId=os.environ.get('searchassist_botId')
SA_Auth=os.environ.get('searchassist_Auth')
SA_url= os.environ.get('searchassist_URL')

#paths
input_path=os.environ.get('input_path')
output_path=os.environ.get('output_path')

#proxies
proxies=os.environ.get('proxies')

#Fetching definiton
inputFormat=os.environ.get('inputFormat')

#set SSL verfication
sslVerify=os.environ.get('ssl')

#itemIds
itemIds=os.environ.get('itemIds')

