import aiohttp
import asyncio
import pandas as pd
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from config.configManager import ConfigManager
from utils.jti import JTI

def generate_JWT_token(client_id, client_secret):
    jwt_token = JTI.get_hs_key(client_id, client_secret, "JWT", "HS256")    
    # Ensure the token is a string, not bytes
    if isinstance(jwt_token, bytes):
        jwt_token = jwt_token.decode('utf-8')
    elif jwt_token is None:
        raise ValueError("Failed to generate JWT token")
    return jwt_token

def save_batch_to_persistent_file(batch_results: List[Dict], batch_number: int, api_type: str, 
                                output_dir: str = "outputs/sa_api_outputs", filename: str = None):
    """
    Save batch results to a single persistent file that accumulates all batches.
    
    Args:
        batch_results: List of results from the current batch
        batch_number: Current batch number
        api_type: Type of API used (SA or UXO)
        output_dir: Directory to save the persistent file (default: outputs)
        filename: Optional custom filename (if None, auto-generates)
    """
    try:
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{output_dir}/all_batches_{api_type}_{timestamp}.xlsx"
        
        # Convert batch results to DataFrame format
        df_data = []
        for result in batch_results:
            # Convert context list to string if it's a list
            context_str = result.get('context', [])
            if isinstance(context_str, list):
                context_str = '\n'.join(context_str)
            
            df_data.append({
                'query': result.get('query', ''),
                'ground_truth': result.get('ground_truth', ''),
                'answer': result.get('answer', ''),
                'context': context_str,
                'context_url': result.get('context_url', ''),
                'batch_number': batch_number,
                'api_type': api_type,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Create DataFrame for current batch
        current_batch_df = pd.DataFrame(df_data)
        
        # Check if file already exists
        if os.path.exists(filename):
            try:
                # Load existing data
                existing_df = pd.read_excel(filename, engine='openpyxl')
                
                # Append new batch data
                combined_df = pd.concat([existing_df, current_batch_df], ignore_index=True)
                
                # Save combined data
                combined_df.to_excel(filename, index=False)
                
                print(f"✅ Batch {batch_number} appended to existing file: {filename}")
                print(f"   📊 Total samples in file: {len(combined_df)}")
                print(f"   📊 New samples added: {len(current_batch_df)}")
                
            except Exception as e:
                print(f"⚠️  Error reading existing file, creating new file: {str(e)}")
                current_batch_df.to_excel(filename, index=False)
                print(f"✅ Batch {batch_number} saved to new file: {filename}")
                print(f"   📊 Samples in file: {len(current_batch_df)}")
        else:
            # Create new file with first batch
            current_batch_df.to_excel(filename, index=False)
            print(f"✅ Batch {batch_number} saved to new file: {filename}")
            print(f"   📊 Samples in file: {len(current_batch_df)}")
        
        return filename
        
    except Exception as e:
        print(f"❌ Error saving batch {batch_number} to persistent file: {str(e)}")
        return None

class AsyncXOSearchAPI:
    def __init__(self):
        config = ConfigManager().get_config()
        self.client_id = config.get('UXO').get('client_id')
        self.client_secret = config.get('UXO').get('client_secret')
        self.auth_token = generate_JWT_token(self.client_id, self.client_secret)
        # Ensure auth_token is a string
        if not isinstance(self.auth_token, str):
            raise ValueError(f"Auth token must be string, got {type(self.auth_token)}")
        self.app_id = config.get('UXO').get('app_id')
        self.domain = config.get('UXO').get('domain')
        self.base_url = f'https://{self.domain}/api/public/bot/{self.app_id}'
        
        # Get search API configuration from config
        search_api_config = config.get('search_api', {})
        self.search_api_version = search_api_config.get('version', 'v2')
        self.search_api_endpoint = search_api_config.get('endpoint', 'search/v2/advanced-search')
        self.search_api_payload = search_api_config.get('payload', {
            "includeChunksInResponse": True,
            "searchResults": True,
            "maxNumOfChunks": 15
        })
        self.answer_search = search_api_config.get('answerSearch', True)

    async def _make_request(self, session: aiohttp.ClientSession, endpoint: str, data: Dict) -> Optional[Dict]:
        headers = {
            'auth': self.auth_token,
            'Content-Type': 'application/json'
        }
        try:
            print("url is ", f"{self.base_url}/{endpoint}")
            async with session.post(f"{self.base_url}/{endpoint}", json=data, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            print(f"Request failed: {e}")
            return None

    async def advanced_search(self, session: aiohttp.ClientSession, query: str) -> Optional[Dict]:
        # Build payload from config and add query
        data = self.search_api_payload.copy()
        data["query"] = query
        
        # Add answerSearch flag from config
        data["answerSearch"] = self.answer_search
        
        print("Making async advanced search call for query:", query)
        print(f"Using search API version: {self.search_api_version}")
        print(f"Answer search enabled: {self.answer_search}")
        return await self._make_request(session, self.search_api_endpoint, data)


class AsyncSearchAssistAPI:
    def __init__(self):
        config = ConfigManager().get_config()
        self.client_id = config.get('SA').get('client_id')
        self.client_secret = config.get('SA').get('client_secret')
        self.auth_token = generate_JWT_token(self.client_id, self.client_secret)
        self.app_id = config.get('SA').get('app_id')
        self.domain = config.get('SA').get('domain')
        self.base_url = f'https://{self.domain}/searchassistapi/external/stream/{self.app_id}'

    async def _make_request(self, session: aiohttp.ClientSession, endpoint: str, data: Dict) -> Optional[Dict]:
        headers = {
            'auth': self.auth_token,
            'Content-Type': 'application/json'
        }
        try:
            async with session.post(f"{self.base_url}/{endpoint}", json=data, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            print(f"Request failed: {e}")
            return None

    async def advanced_search(self, session: aiohttp.ClientSession, query: str) -> Optional[Dict]:
        data = {
            "query": query,
            "includeChunksInResponse": True
        }
        print("Making async SA search call for query:", query)
        return await self._make_request(session, 'advancedSearch', data)


class AsyncAnswerProcessor:
    @staticmethod
    def get_context(answer: Dict, api_version: str = "v2") -> Tuple[List[str], str]:
        contexts = []
        context_urls = set()
        
        if api_version == "v2":
            # Handle v2 format (template.chunk_result)
            if 'template' in answer and 'chunk_result' in answer['template']:
                for chunk in answer['template']['chunk_result']:
                    source = chunk.get('_source', {})
                    if source.get('sentToLLM'):
                        contexts.append(source.get('chunkText', ''))
                        context_urls.add(source.get('recordUrl', ''))
        else:
            # Handle v1 format (chunk_result directly)
            if 'chunk_result' in answer:
                for chunk in answer.get('chunk_result', {}).get('generative', []):
                    source = chunk.get('_source', {})
                    if source.get('sentToLLM'):
                        contexts.append(source.get('chunkText', ''))
                        context_urls.add(source.get('recordUrl', ''))
        
        return contexts, ",".join(context_urls)

    @staticmethod
    def extract_answer(answer: Dict, api_version: str = "v2") -> str:
        if api_version == "v2":
            # Handle v2 format (template.answer_details.response.answer)
            if 'template' in answer and 'answer_details' in answer['template']:
                answer_details = answer['template']['answer_details']
                if 'response' in answer_details and 'answer' in answer_details['response']:
                    return answer_details['response']['answer']
        else:
            # Handle v1 format (response.answer_payload.center_panel)
            if 'response' in answer:
                center_panel = (answer.get('response', {})
                                .get('answer_payload', {})
                                .get('center_panel', {}))
                if not center_panel:
                    return "No Answer Found"
                snippet_content = center_panel.get('data', [{}])[0].get('snippet_content', [{}])
                answer_string = " ".join(content.get('answer_fragment', "No Answer Found") for content in snippet_content) if snippet_content else "No Answer Found"
                return answer_string
        
        return "No Answer Found"
    
    @staticmethod
    def extract_error_message(answer: Dict, api_version: str = "v2") -> str:
        """
        Extract error message from response based on API version.
        
        Args:
            answer: Full search API response
            api_version: API version (v1 or v2)
            
        Returns:
            Error message string or empty string if no error
        """
        if api_version == "v2":
            # Handle v2 format (template.answer_details.errMsg)
            if 'template' in answer and 'answer_details' in answer['template']:
                answer_details = answer['template']['answer_details']
                if 'errMsg' in answer_details:
                    return answer_details['errMsg']
        else:
            # Handle v1 format (response.errMsg)
            if 'response' in answer and 'errMsg' in answer['response']:
                return answer['response']['errMsg']
        
        return ""


async def get_async_bot_response(api_type: str, session: aiohttp.ClientSession, query: str, truth: str) -> Optional[Dict]:
    """
    Get bot response asynchronously
    
    Args:
        api_type: 'SA' for SearchAssist or 'UXO' for XO Search
        session: aiohttp session
        query: search query
        truth: ground truth
    """
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    if api_type == 'SA' and config.get('SA'):
        api = AsyncSearchAssistAPI()
    elif api_type == 'UXO' and config.get('UXO'):
        api = AsyncXOSearchAPI()
    else:
        print(f"API type {api_type} not configured")
        return None
    
    answer = await api.advanced_search(session, query)
    if not answer:
        return None

    # Get API version from config
    search_api_config = config.get('search_api', {})
    api_version = search_api_config.get('version', 'v2')
    
    context_data, context_url = AsyncAnswerProcessor.get_context(answer, api_version)
    bot_answer = AsyncAnswerProcessor.extract_answer(answer, api_version)

    return {
        'query': query,
        'ground_truth': truth,
        'context': context_data,
        'context_url': context_url,
        'answer': bot_answer
    }


async def call_search_api_async(queries: List[str], ground_truths: List[str], api_type: str = 'UXO', 
                              max_concurrent: int = 3, save_batches: bool = False, 
                              persistent_filename: str = None) -> List[Dict]:
    """
    Call search API asynchronously for multiple queries with configurable concurrency limit
    
    Args:
        queries: List of search queries
        ground_truths: List of ground truths
        api_type: 'SA' for SearchAssist or 'UXO' for XO Search
        max_concurrent: Maximum number of concurrent API calls (default: 3)
        save_batches: Whether to save data after each batch (default: True)
        persistent_filename: Optional custom filename for persistent saving
    """
    results = []
    batch_number = 1
    
    # Get sleep duration from config
    config = ConfigManager().get_config()
    sleep_seconds = config.get('search_api_sleep_seconds', 1)
    
    async with aiohttp.ClientSession() as session:
        # Process queries in batches to limit concurrency
        for i in range(0, len(queries), max_concurrent):
            batch_queries = queries[i:i + max_concurrent]
            batch_ground_truths = ground_truths[i:i + max_concurrent]
            
            print(f"🔄 Processing batch {batch_number}: {len(batch_queries)} queries (max {max_concurrent} concurrent)")
            
            # Create tasks for current batch
            tasks = []
            for query, truth in zip(batch_queries, batch_ground_truths):
                task = get_async_bot_response(api_type, session, query, truth)
                tasks.append(task)
            
            # Execute current batch concurrently
            batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process batch results
            batch_results = []
            for j, response in enumerate(batch_responses):
                query_index = i + j
                if isinstance(response, Exception):
                    print(f"❌ Error processing query {query_index}: {response}")
                    batch_result = {
                        'query': queries[query_index],
                        'ground_truth': ground_truths[query_index],
                        'context': [],
                        'context_url': '',
                        'answer': "Failed to get response"
                    }
                elif response:
                    batch_result = response
                    print(f"✅ Successfully processed query {query_index}: {queries[query_index][:50]}...")
                else:
                    batch_result = {
                        'query': queries[query_index],
                        'ground_truth': ground_truths[query_index],
                        'context': [],
                        'context_url': '',
                        'answer': "Failed to get response"
                    }
                
                batch_results.append(batch_result)
                results.append(batch_result)
            
            # Save batch data to persistent file after processing
            if save_batches:
                save_batch_to_persistent_file(batch_results, batch_number, api_type, 
                                           filename=persistent_filename)
            
            print(f"✅ Batch {batch_number} completed: {len(batch_results)} queries processed")
            
            # Sleep between batches if configured
            if sleep_seconds > 0 and i + max_concurrent < len(queries):
                print(f"😴 Sleeping for {sleep_seconds} seconds before next batch...")
                await asyncio.sleep(sleep_seconds)
            
            batch_number += 1
    
    return results


async def call_search_api_async_simple(queries: List[str], api_type: str = 'UXO', 
                                      max_concurrent: int = 3) -> List[Dict]:
    """
    Call search API asynchronously for multiple queries (simplified version for retrieval benchmark)
    
    Args:
        queries: List of search queries
        api_type: 'SA' for SearchAssist or 'UXO' for XO Search
        max_concurrent: Maximum number of concurrent API calls (default: 3)
    """
    results = []
    
    # Get sleep duration from config
    config = ConfigManager().get_config()
    sleep_seconds = config.get('search_api_sleep_seconds', 1)
    
    async with aiohttp.ClientSession() as session:
        # Process queries in batches to limit concurrency
        for i in range(0, len(queries), max_concurrent):
            batch_queries = queries[i:i + max_concurrent]
            
            print(f"🔄 Processing batch: {len(batch_queries)} queries (max {max_concurrent} concurrent)")
            
            # Create tasks for current batch
            tasks = []
            for query in batch_queries:
                task = get_async_bot_response_simple(api_type, session, query)
                tasks.append(task)
            
            # Execute current batch concurrently
            batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process batch results
            for j, response in enumerate(batch_responses):
                query_index = i + j
                if isinstance(response, Exception):
                    print(f"❌ Error processing query {query_index}: {response}")
                    results.append({})
                elif response:
                    results.append(response)
                    print(f"✅ Successfully processed query {query_index}: {queries[query_index][:50]}...")
                else:
                    results.append({})
            
            print(f"✅ Batch completed: {len(batch_queries)} queries processed")
            
            # Sleep between batches if configured
            if sleep_seconds > 0 and i + max_concurrent < len(queries):
                print(f"😴 Sleeping for {sleep_seconds} seconds before next batch...")
                await asyncio.sleep(sleep_seconds)
    
    return results


async def get_async_bot_response_simple(api_type: str, session: aiohttp.ClientSession, query: str) -> Optional[Dict]:
    """
    Get bot response asynchronously (simplified version without ground truth)
    
    Args:
        api_type: 'SA' for SearchAssist or 'UXO' for XO Search
        session: aiohttp session
        query: search query
    """
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    if api_type == 'SA' and config.get('SA'):
        api = AsyncSearchAssistAPI()
    elif api_type == 'UXO' and config.get('UXO'):
        api = AsyncXOSearchAPI()
    else:
        print(f"API type {api_type} not configured")
        return None
    
    answer = await api.advanced_search(session, query)
    if not answer:
        return None

    return answer


# Example usage
if __name__ == "__main__":
    async def main():
        queries = ["what is eva?", "how does it work?"]
        ground_truths = ["Example ground truth 1", "Example ground truth 2"]
        
        results = await call_search_api_async(queries, ground_truths, 'UXO')
        for result in results:
            print(result)
    
    asyncio.run(main()) 