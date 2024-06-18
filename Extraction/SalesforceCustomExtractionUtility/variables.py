import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI Configuration
OPENAI_KEY = os.environ.get('OPENAI_KEY')

#azure open ai 
apiKey= os.environ.get("apiKey")
userSubDomain=os.environ.get("userSubDomain")
deployment= os.environ.get("deployment")
Apiversion=os.environ.get("Apiversion")

# Access Token Configuration
accessTokenUrl = "https://login.salesforce.com/services/oauth2/token"
hostUrl = os.environ.get('hostUrl')
accessTokenGrantType = "authorization_code"
accessTokenClientId = os.environ.get('clientId')
accessTokenClientSecret = os.environ.get('clientSecret')
redirectUri = os.environ.get('redirectUri')
accessTokenAuthCode =os.environ.get('accessTokenAuthCode')

#Refresh Token Configuration
refreshTokenUrl = "https://login.salesforce.com/services/oauth2/token"
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