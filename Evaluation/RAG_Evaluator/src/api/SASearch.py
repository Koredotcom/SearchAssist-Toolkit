import os
import requests
from typing import Dict, List, Tuple, Optional

from utils.jti import JTI


def generate_JWT_token(client_id, client_secret):
    """Generate JWT token for authentication"""
    jwt_token = JTI.get_hs_key(client_id, client_secret, "JWT", "HS256")
    return jwt_token

class SearchAssistAPI:
    def __init__(self):
        # Use environment variables or defaults (no file-based config)
        self.client_id = os.getenv('SA_CLIENT_ID', '<SA_CLIENT_ID>')
        self.client_secret = os.getenv('SA_CLIENT_SECRET', '<SA_CLIENT_SECRET>')
        self.auth_token = generate_JWT_token(self.client_id, self.client_secret)
        self.app_id = os.getenv('SA_APP_ID', '<SA_APP_ID>')
        self.domain = os.getenv('SA_DOMAIN', '<SA_DOMAIN>')
        self.base_url = f'https://{self.domain}/searchassistapi/external/stream/{self.app_id}'

    def _make_request(self, endpoint: str, data: Dict) -> Optional[Dict]:
        headers = {
            'auth': self.auth_token,
            'Content-Type': 'application/json'
        }
        try:

            response = requests.post(f"{self.base_url}/{endpoint}", json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None

    def advanced_search(self, query: str) -> Optional[Dict]:
        data = {
            "query": query,
            "includeChunksInResponse": True
        }

        return self._make_request('advancedSearch', data)


class AnswerProcessor:
    @staticmethod
    def get_context(answer: Dict) -> Tuple[List[str], str]:
        contexts = []
        context_urls = set()
        for chunk in answer.get('template', {}).get('chunk_result', {}).get('generative', []):
            source = chunk.get('_source', {})
            if source.get('sentToLLM'):
                contexts.append(source.get('chunkText', ''))
                context_urls.add(source.get('recordUrl', ''))
        return contexts, ",".join(context_urls)

    @staticmethod
    def extract_answer(answer: Dict) -> str:
        center_panel = (answer.get('template', {})
                        .get('graph_answer', {})
                        .get('payload', {})
                        .get('center_panel', {}))
        if not center_panel:
            return "No Answer Found"
        snippet_content = center_panel.get('data', [{}])[0].get('snippet_content', [{}])
        answer_string = " ".join(content.get('answer_fragment', "No Answer Found") for content in snippet_content) if snippet_content else "No Answer Found"
        return answer_string


def get_bot_response(api: SearchAssistAPI, query: str, truth: str) -> Optional[Dict]:
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




# Async version for batch processing
import aiohttp
import asyncio
from asyncio import Semaphore

class AsyncSearchAssistAPI:
    def __init__(self, config=None):
        if config is None:
            # Use environment variables or defaults (no file-based config)
            sa_config = {
                'client_id': os.getenv('SA_CLIENT_ID', '<SA_CLIENT_ID>'),
                'client_secret': os.getenv('SA_CLIENT_SECRET', '<SA_CLIENT_SECRET>'),
                'app_id': os.getenv('SA_APP_ID', '<SA_APP_ID>'),
                'domain': os.getenv('SA_DOMAIN', '<SA_DOMAIN>')
            }
        else:
            sa_config = config.get('SA', {})
        
        self.client_id = sa_config.get('client_id')
        self.client_secret = sa_config.get('client_secret')
        self.app_id = sa_config.get('app_id')
        self.domain = sa_config.get('domain', '').strip()
        
        # Validate configuration
        if not all([self.client_id, self.client_secret, self.app_id, self.domain]):
            missing = []
            if not self.client_id: missing.append('client_id')
            if not self.client_secret: missing.append('client_secret')
            if not self.app_id: missing.append('app_id')
            if not self.domain: missing.append('domain')
            raise ValueError(f"Missing SearchAssist configuration: {', '.join(missing)}")
        
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
            
        self.base_url = f'https://{self.domain}/searchassistapi/external/stream/{self.app_id}'


    async def _make_async_request(self, session: aiohttp.ClientSession, endpoint: str, data: Dict) -> Optional[Dict]:
        headers = {
            'auth': self.auth_token,
            'Content-Type': 'application/json'
        }
        
        full_url = f"{self.base_url}/{endpoint}"
        
        try:
            async with session.post(full_url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, Exception):
            return None

    async def advanced_search_async(self, session: aiohttp.ClientSession, query: str) -> Optional[Dict]:
        data = {
            "query": query,
            "includeChunksInResponse": True
        }

        return await self._make_async_request(session, 'advancedSearch', data)


async def get_bot_response_async(api: AsyncSearchAssistAPI, session: aiohttp.ClientSession, query: str, truth: str) -> Optional[Dict]:
    answer = await api.advanced_search_async(session, query)
    if not answer:
        return None

    context_data, context_url = AnswerProcessor.get_context(answer)
    bot_answer = AnswerProcessor.extract_answer(answer)
    
    # Extract chunk statistics from the search API response
    chunk_stats = {}
    try:
        from utils.chunkStatistics import ChunkStatisticsProcessor
        chunk_stats = ChunkStatisticsProcessor.extract_chunk_statistics(answer, api_type="SA")
        # Format chunk statistics for Excel export
        chunk_stats_formatted = ChunkStatisticsProcessor.format_chunk_statistics_for_excel(chunk_stats)
    except Exception as e:
        print(f"⚠️ Error extracting chunk statistics: {e}")
        chunk_stats_formatted = {}

    return {
        'query': query,
        'ground_truth': truth,
        'context': context_data,
        'context_url': context_url,
        'answer': bot_answer,
        'chunk_statistics': chunk_stats_formatted
    }
