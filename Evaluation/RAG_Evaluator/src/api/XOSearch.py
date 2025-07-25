import requests
from typing import Dict, List, Tuple, Optional
from config.configManager import ConfigManager
from utils.jti import JTI

def generate_JWT_token(client_id, client_secret):
      
    jwt_token = JTI.get_hs_key(client_id, client_secret, "JWT", "HS256")  
    print('jwt_token: ', jwt_token)  
    return jwt_token

class XOSearchAPI:
    def __init__(self):
        config = ConfigManager().get_config()
        self.client_id = config.get('UXO').get('client_id')
        self.client_secret = config.get('UXO').get('client_secret')
        self.auth_token = generate_JWT_token(self.client_id, self.client_secret)
        self.app_id = config.get('UXO').get('app_id')
        self.domain = config.get('UXO').get('domain')
        self.base_url = f'https://{self.domain}/api/public/bot/{self.app_id}'

    def _make_request(self, endpoint: str, data: Dict) -> Optional[Dict]:
        headers = {
            'auth': self.auth_token,
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(f"{self.base_url}/{endpoint}", json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None

    def advanced_search(self, query: str) -> Optional[Dict]:
        data = {
            "query": query,
            "includeChunksInResponse": True
        }
        print("Making SA search call for query:", query)
        return self._make_request('advancedSearch', data)


class AnswerProcessor:
    @staticmethod
    def get_context(answer: Dict) -> Tuple[List[str], str]:
        contexts = []
        context_urls = set()
        for chunk in answer.get('chunk_result', {}).get('generative', []):
            source = chunk.get('_source', {})
            if source.get('sentToLLM'):
                contexts.append(source.get('chunkText', ''))
                context_urls.add(source.get('recordUrl', ''))
        return contexts, ",".join(context_urls)

    @staticmethod
    def extract_answer(answer: Dict) -> str:
        center_panel = (answer.get('response', {})
                        .get('answer_payload', {})
                        .get('center_panel', {}))
        if not center_panel:
            return "No Answer Found"
        snippet_content = center_panel.get('data', [{}])[0].get('snippet_content', [{}])
        answer_string = " ".join(content.get('answer_fragment', "No Answer Found") for content in snippet_content) if snippet_content else "No Answer Found"
        return answer_string


def get_bot_response(api: XOSearchAPI, query: str, truth: str) -> Optional[Dict]:
    answer = api.advanced_search(query)
    if not answer:
        return None

    context_data, context_url = AnswerProcessor.get_context(answer)
    bot_answer = AnswerProcessor.extract_answer(answer)

    return {
        'query': query,
        'ground_truth': truth,
        'context': context_data,
        'context_url': context_url,
        'answer': bot_answer
    }


# Example usage
if __name__ == "__main__":
    api = XOSearchAPI()
    query = "what is eva?"
    truth = "Example ground truth"
    result = get_bot_response(api, query, truth)
    if result:
        print(result)
    else:
        print("Failed to get response")

# Async version for batch processing
import aiohttp
import asyncio
from asyncio import Semaphore

class AsyncXOSearchAPI:
    def __init__(self):
        config = ConfigManager().get_config()
        uxo_config = config.get('UXO', {})
        
        self.client_id = uxo_config.get('client_id')
        self.client_secret = uxo_config.get('client_secret')
        self.app_id = uxo_config.get('app_id')
        self.domain = uxo_config.get('domain', '').strip()
        
        # Validate configuration
        if not all([self.client_id, self.client_secret, self.app_id, self.domain]):
            missing = []
            if not self.client_id: missing.append('client_id')
            if not self.client_secret: missing.append('client_secret')
            if not self.app_id: missing.append('app_id')
            if not self.domain: missing.append('domain')
            raise ValueError(f"Missing UXO configuration: {', '.join(missing)}")
        
        # Clean and validate domain
        if self.domain.startswith('http://') or self.domain.startswith('https://'):
            # Remove protocol if provided
            self.domain = self.domain.replace('https://', '').replace('http://', '')
        
        if not self.domain or self.domain in ['<SA domain url>', '<UXO domain url>']:
            raise ValueError(f"Invalid domain configuration: '{self.domain}'. Please provide a valid domain.")
        
        try:
            self.auth_token = generate_JWT_token(self.client_id, self.client_secret)
        except Exception as e:
            raise ValueError(f"Failed to generate JWT token: {e}")
            
        self.base_url = f'https://{self.domain}/api/public/bot/{self.app_id}'
        print(f"Initialized AsyncXOSearchAPI with URL: {self.base_url}")

    async def _make_async_request(self, session: aiohttp.ClientSession, endpoint: str, data: Dict) -> Optional[Dict]:
        headers = {
            'auth': f'{self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        full_url = f"{self.base_url}/{endpoint}"        
        try:
            async with session.post(full_url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"API request failed with status {response.status}: {await response.text()}")
                    return None
        except aiohttp.ClientConnectorError as e:
            print(f"Connection error - check domain configuration: {e}")
            print(f"Attempted URL: {full_url}")
            return None
        except aiohttp.ClientError as e:
            print(f"Async request failed: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in async request: {e}")
            return None

    async def advanced_search_async(self, session: aiohttp.ClientSession, query: str) -> Optional[Dict]:
        data = {
            "query": query,
            "includeChunksInResponse": True
        }
        print(f"Making async UXO search call for query: {query[:50]}...")
        return await self._make_async_request(session, 'advancedSearch', data)


async def get_bot_response_async(api: AsyncXOSearchAPI, session: aiohttp.ClientSession, query: str, truth: str) -> Optional[Dict]:
    answer = await api.advanced_search_async(session, query)
    if not answer:
        return None

    context_data, context_url = AnswerProcessor.get_context(answer)
    bot_answer = AnswerProcessor.extract_answer(answer)

    return {
        'query': query,
        'ground_truth': truth,
        'context': context_data,
        'context_url': context_url,
        'answer': bot_answer
    }
