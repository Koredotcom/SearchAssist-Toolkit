import os
import requests
from typing import Dict, List, Tuple, Optional

from utils.jti import JTI
import json

def generate_JWT_token(client_id, client_secret):
    """Generate JWT token for authentication"""
    jwt_token = JTI.get_hs_key(client_id, client_secret, "JWT", "HS256")
    return jwt_token

class XOSearchAPI:
    def __init__(self):
        # Use environment variables or defaults (no file-based config)
        self.client_id = os.getenv('UXO_CLIENT_ID', '<UXO_CLIENT_ID>')
        self.client_secret = os.getenv('UXO_CLIENT_SECRET', '<UXO_CLIENT_SECRET>')
        self.auth_token = generate_JWT_token(self.client_id, self.client_secret)
        self.app_id = os.getenv('UXO_APP_ID', '<UXO_APP_ID>')
        self.domain = os.getenv('UXO_DOMAIN', '<UXO_DOMAIN>')
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
            # Use logging instead of print for error handling
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
    @staticmethod
    def analyze_doc_id(answer: Dict, expected_doc_id: Optional[str] = None) -> Optional[Dict]:
        """
        Analyzes KB IDs from the answer JSON and checks if expected doc_id(s) are present in different chunk categories.
        Supports both single KB ID and comma-separated multiple KB IDs.
        Returns True if at least one expected KB ID meets the condition.
        
        Args:
            answer: The answer dictionary from the API response
            expected_doc_id: The expected KB ID(s) to check (optional). Can be a single KB ID or comma-separated string like "KB0011347,KB0011348"
            
        Returns:
            Dictionary containing:
            - qualified_chunks_doc_ids: List of KB IDs from all qualified chunks
            - chunks_sent_to_llm_doc_ids: List of KB IDs from chunks sent to LLM
            - answered_chunks_doc_ids: List of KB IDs from chunks used in the answer
            - expected_doc_id_position: List of positions/indexes of expected doc_ids in qualified chunks (None if not found)
            - expected_doc_id_qualified: Boolean - True if at least one expected doc_id is in qualified chunks
            - doc_id_sent_to_llm: Boolean - True if at least one expected doc_id is in chunks sent to LLM
            - doc_id_answered: Boolean - True if at least one expected doc_id is in answered chunks
        """
        if not expected_doc_id:
            return None
        
        # Parse comma-separated DOC IDs into a list
        expected_doc_ids = [doc_id.strip() for doc_id in str(expected_doc_id).split(',') if doc_id.strip()]
        if not expected_doc_ids:
            return None
            
        # Get all generative chunks (qualified chunks)
        # generative_chunks = answer.get('template', {}).get('chunk_result', {}).get('generative', [])
        generative_chunks = answer.get('chunk_result', {}).get('generative', [])
        
        # Extract DOC IDs from qualified chunks (all chunks)
        qualified_chunks_doc_ids = []
        chunks_sent_to_llm_doc_ids = []
        answered_chunks_doc_ids = []
        
        # Track positions of expected doc_ids in qualified chunks
        expected_doc_id_positions = []
        
        for idx, chunk in enumerate(generative_chunks):
            source = chunk.get('_source', {})
            doc_id = source.get('docId', '') 
            
            if doc_id:
                qualified_chunks_doc_ids.append(doc_id)
                
                # Check if this is one of the expected doc_ids and record its position
                for doc_id in expected_doc_ids:
                    if doc_id == doc_id:
                        # Find the index of this doc_id in expected_doc_ids list
                        doc_id_index = expected_doc_ids.index(doc_id)
                        # Ensure we have enough positions in the list
                        while len(expected_doc_id_positions) <= doc_id_index:
                            expected_doc_id_positions.append(None)
                        # Only record the first occurrence (position) of each doc_id
                        if expected_doc_id_positions[doc_id_index] is None:
                            expected_doc_id_positions[doc_id_index] = idx
                
                # Check if chunk was sent to LLM
                if source.get('sentToLLM') or source.get('sent_to_LLM'):
                    chunks_sent_to_llm_doc_ids.append(doc_id)
                    
                    # Chunks sent to LLM are considered answered chunks
                    answered_chunks_doc_ids.append(doc_id)
        
        # Check if at least one expected doc_id is in each category (returns True if any matches)
        expected_doc_id_qualified = any(doc_id in qualified_chunks_doc_ids for doc_id in expected_doc_ids)
        doc_id_sent_to_llm = any(doc_id in chunks_sent_to_llm_doc_ids for doc_id in expected_doc_ids)
        doc_id_answered = any(doc_id in answered_chunks_doc_ids for doc_id in expected_doc_ids)
        
        # Ensure positions list has the same length as expected_doc_ids
        while len(expected_doc_id_positions) < len(expected_doc_ids):
            expected_doc_id_positions.append(None)
        
        return {
            'qualified_chunks_doc_ids': qualified_chunks_doc_ids,
            'chunks_sent_to_llm_doc_ids': chunks_sent_to_llm_doc_ids,
            'answered_chunks_doc_ids': answered_chunks_doc_ids,
            'expected_doc_id_position': expected_doc_id_positions,
            'expected_doc_id_qualified': expected_doc_id_qualified,
            'doc_id_sent_to_llm': doc_id_sent_to_llm,
            'doc_id_answered': doc_id_answered
        }
  
    
    @staticmethod
    def analyze_record_title(answer: Dict, expected_record_title: Optional[str] = None) -> Optional[Dict]:
        """
        Analyzes record titles from the answer JSON and checks if expected record title(s) are present in different chunk categories.
        Supports both single record title and comma-separated multiple record titles.
        Returns True if at least one expected record title meets the condition.
        
        Args:
            answer: The answer dictionary from the API response
            expected_record_title: The expected record title(s) to check (optional). Can be a single record title or comma-separated string like "Title1,Title2"
            
        Returns:
            Dictionary containing:
            - qualified_chunks_record_titles: List of record titles from all qualified chunks
            - chunks_sent_to_llm_record_titles: List of record titles from chunks sent to LLM
            - answered_chunks_record_titles: List of record titles from chunks used in the answer
            - expected_record_title_position: List of positions/indexes of expected record titles in qualified chunks (None if not found)
            - expected_record_title_qualified: Boolean - True if at least one expected record title is in qualified chunks
            - record_title_sent_to_llm: Boolean - True if at least one expected record title is in chunks sent to LLM
            - record_title_answered: Boolean - True if at least one expected record title is in answered chunks
        """
        if not expected_record_title:
            return None
        
        # Parse comma-separated record titles into a list
        expected_record_titles = [title.strip() for title in str(expected_record_title).split(',') if title.strip()]
        if not expected_record_titles:
            return None
            
        # Get all generative chunks (qualified chunks)
        generative_chunks = answer.get('chunk_result', {}).get('generative', [])
        
        # Extract record titles from qualified chunks (all chunks)
        qualified_chunks_record_titles = []
        chunks_sent_to_llm_record_titles = []
        answered_chunks_record_titles = []
        
        # Track positions of expected record titles in qualified chunks
        expected_record_title_positions = []
        for idx, chunk in enumerate(generative_chunks):
            source = chunk.get('_source', {})
            record_title = source.get('recordTitle', '')
            
            if record_title:
                qualified_chunks_record_titles.append(record_title)
                
                # Check if this is one of the expected record titles and record its position
                for title in expected_record_titles:
                    if record_title == title:
                        # Find the index of this record title in expected_record_titles list
                        title_index = expected_record_titles.index(title)
                        # Ensure we have enough positions in the list
                        while len(expected_record_title_positions) <= title_index:
                            expected_record_title_positions.append(None)
                        # Only record the first occurrence (position) of each record title
                        if expected_record_title_positions[title_index] is None:
                            expected_record_title_positions[title_index] = idx
                
                # Check if chunk was sent to LLM
                if source.get('sentToLLM') or source.get('sent_to_LLM'):
                    chunks_sent_to_llm_record_titles.append(record_title)
                    
                    # Chunks sent to LLM are considered answered chunks
                    answered_chunks_record_titles.append(record_title)
        
        # Check if at least one expected record title is in each category (returns True if any matches)
        expected_record_title_qualified = any(title in qualified_chunks_record_titles for title in expected_record_titles)
        record_title_sent_to_llm = any(title in chunks_sent_to_llm_record_titles for title in expected_record_titles)
        record_title_answered = any(title in answered_chunks_record_titles for title in expected_record_titles)
        
        # Ensure positions list has the same length as expected_record_titles
        while len(expected_record_title_positions) < len(expected_record_titles):
            expected_record_title_positions.append(None)
        
        return {
            'qualified_chunks_record_titles': qualified_chunks_record_titles,
            'chunks_sent_to_llm_record_titles': chunks_sent_to_llm_record_titles,
            'answered_chunks_record_titles': answered_chunks_record_titles,
            'expected_record_title_position': expected_record_title_positions,
            'expected_record_title_qualified': expected_record_title_qualified,
            'record_title_sent_to_llm': record_title_sent_to_llm,
            'record_title_answered': record_title_answered
        }

    
    


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




# Async version for batch processing
import aiohttp
import asyncio
from asyncio import Semaphore

class AsyncXOSearchAPI:
    def __init__(self, config=None):
        if config is None:
            # Use environment variables or defaults (no file-based config)
            uxo_config = {
                'client_id': os.getenv('UXO_CLIENT_ID', '<UXO_CLIENT_ID>'),
                'client_secret': os.getenv('UXO_CLIENT_SECRET', '<UXO_CLIENT_SECRET>'),
                'app_id': os.getenv('UXO_APP_ID', '<UXO_APP_ID>'),
                'domain': os.getenv('UXO_DOMAIN', '<UXO_DOMAIN>')
            }
        else:
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


    async def _make_async_request(self, session: aiohttp.ClientSession, endpoint: str, data: Dict) -> Optional[Dict]:
        headers = {
            'auth': f'{self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        full_url = f"{self.base_url}/{endpoint}"    
        print(f"⚡ Processing {data} concurrently...")
    
        try:
            async with session.post(full_url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as response:
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


async def get_bot_response_async(api: AsyncXOSearchAPI, session: aiohttp.ClientSession, query: str, truth: str,expected_doc_id: Optional[str] = None,
    expected_record_title: Optional[str] = None) -> Optional[Dict]:
    
    answer = await api.advanced_search_async(session, query)
    if not answer:
        return None

    context_data, context_url = AnswerProcessor.get_context(answer)
    bot_answer = AnswerProcessor.extract_answer(answer)
    
    result = {
        'query': query,
        'ground_truth': truth,
        'context': context_data,
        'context_url': context_url,
        'answer': bot_answer
    }
    # Add expected_doc_id to result if provided
    if expected_doc_id:
        result['expected_doc_id'] = expected_doc_id
    
    # # Add expected_record_title to result if provided
    if expected_record_title:
        result['expected_record_title'] = expected_record_title
    
    # Analyze doc_id only if it's provided
    if expected_doc_id:
        kb_analysis = AnswerProcessor.analyze_doc_id(answer, expected_doc_id)
        if kb_analysis:
            result.update({
                'qualified_chunks_doc_ids': kb_analysis['qualified_chunks_doc_ids'],
                'chunks_sent_to_llm_doc_ids': kb_analysis['chunks_sent_to_llm_doc_ids'],
                'answered_chunks_doc_ids': kb_analysis['answered_chunks_doc_ids'],
                'expected_doc_id_position': kb_analysis['expected_doc_id_position'],
                'expected_doc_id_qualified': kb_analysis['expected_doc_id_qualified'],
                'doc_id_sent_to_llm': kb_analysis['doc_id_sent_to_llm'],
                'doc_id_answered': kb_analysis['doc_id_answered']
            })
    
    # Analyze record title only if it's provided
    if expected_record_title:
        record_title_analysis = AnswerProcessor.analyze_record_title(answer, expected_record_title)
        if record_title_analysis:
            result.update({
                'qualified_chunks_record_titles': record_title_analysis['qualified_chunks_record_titles'],
                'chunks_sent_to_llm_record_titles': record_title_analysis['chunks_sent_to_llm_record_titles'],
                'answered_chunks_record_titles': record_title_analysis['answered_chunks_record_titles'],
                'expected_record_title_position': record_title_analysis['expected_record_title_position'],
                'expected_record_title_qualified': record_title_analysis['expected_record_title_qualified'],
                'record_title_sent_to_llm': record_title_analysis['record_title_sent_to_llm'],
                'record_title_answered': record_title_analysis['record_title_answered']
            })
           
    
    
    # Extract chunk statistics from the search API response
    chunk_stats = {}
    try:
        from utils.chunkStatistics import ChunkStatisticsProcessor
        chunk_stats = ChunkStatisticsProcessor.extract_chunk_statistics(answer, api_type="XO")
        # Format chunk statistics for Excel export
        chunk_stats_formatted = ChunkStatisticsProcessor.format_chunk_statistics_for_excel(chunk_stats)
        result['chunk_statistics'] = chunk_stats_formatted
    except Exception as e:
        print(f"⚠️ Error extracting chunk statistics: {e}")
        result['chunk_statistics'] = {}
    return result    
