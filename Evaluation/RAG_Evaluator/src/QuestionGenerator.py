#!/usr/bin/env python3
"""
Question Generator for RAG Evaluation

This script generates evaluation questions from chunks using:
1. Chunk List API to fetch chunks
2. OpenAI/Azure models to generate questions
3. Random chunk selection and pagination
4. Configuration from config.json

Usage:
    python QuestionGenerator.py --model openai
    python QuestionGenerator.py --model azure
"""

import os
import sys
import argparse
import asyncio
import aiohttp
import json
import random
import re
from datetime import datetime
from langdetect import detect, DetectorFactory
from typing import List, Dict, Optional, Any, Tuple
from openai import OpenAI
from openai import AzureOpenAI
import jwt
import time

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.configManager import ConfigManager
from async_api_calls import generate_JWT_token


def get_model_name(model_type: str) -> str:
    """Get the model name based on model type."""
    if model_type == "azure":
        return "gpt-4o-mini"  # Azure deployment name
    else:
        return "gpt-4o-mini"  # OpenAI model name


class QuestionGenerator:
    """
    Generates evaluation questions from chunks using LLM.
    """
    
    def __init__(self, model_name: str, openai_client, model_type: str = "openai", max_concurrent: int = 3):
        self.model_name = model_name
        self.openai_client = openai_client
        self.model_type = model_type
        self.config = ConfigManager().get_config()
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Language filtering configuration
        self.language_filter_config = self.config.get('question_generation', {}).get('language_filter', {})
        self.language_filter_enabled = self.language_filter_config.get('enabled', True)
        self.target_language = self.language_filter_config.get('target_language', 'en')
        self.allowed_languages = self.language_filter_config.get('allowed_languages', ['en'])
        self.exclude_code_content = self.language_filter_config.get('exclude_code_content', True)

    def extract_unique_record_titles(self, chunks: List[Dict]) -> List[str]:
        """
        Extract unique record titles from chunks.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            List of unique record titles
        """
        record_titles = set()
        for chunk in chunks:
            record_title = chunk.get('recordTitle', '')
            if record_title:
                record_titles.add(record_title)
        return list(record_titles)
    
    def detect_language(self, text: str) -> str:
        """
        Language detection using langdetect library.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code (en, es, fr, de, ro, etc.)
        """
        if not text:
            return 'unknown'
        
        # Clean the text
        text = text.strip()
        if len(text) < 10:  # Need minimum text for reliable detection
            return 'unknown'
        
        # Remove excessive whitespace and normalize
        text = re.sub(r'\s+', ' ', text)
        
        try:
            # Set seed for consistent results
            DetectorFactory.seed = 0
            detected_lang = detect(text)
            return detected_lang
        except Exception as e:
            # Fallback to simple character-based detection for very short texts
            text_lower = text.lower()
            english_chars = len(re.findall(r'[a-z]', text_lower))
            total_chars = len(text_lower)
            if total_chars > 0 and english_chars / total_chars > 0.6:
                return 'en'
            return 'unknown'
    
    def is_code_content(self, text: str) -> bool:
        """
        Detect if text contains code content.
        
        Args:
            text: Text to analyze
            
        Returns:
            True if text contains code patterns
        """
        if not text:
            return False
        
        # Code patterns to detect
        code_patterns = [
            r'function\s+\w+\s*\(',  # function definitions
            r'const\s+\w+\s*=',      # const declarations
            r'let\s+\w+\s*=',        # let declarations
            r'var\s+\w+\s*=',        # var declarations
            r'if\s*\(',              # if statements
            r'for\s*\(',             # for loops
            r'while\s*\(',           # while loops
            r'class\s+\w+',          # class definitions
            r'import\s+',            # import statements
            r'export\s+',            # export statements
            r'console\.log',         # console.log
            r'return\s+',            # return statements
            r'\.js\b',               # .js files
            r'\.py\b',               # .py files
            r'\.java\b',             # .java files
            r'\.cpp\b',              # .cpp files
            r'\.html\b',             # .html files
            r'\.css\b',              # .css files
            r'\.json\b',             # .json files
            r'keyboard\.shortcut',   # keyboard shortcuts
            r'Ctrl\+',               # Ctrl combinations
            r'Alt\+',                # Alt combinations
            r'Shift\+',              # Shift combinations
            r'F\d+',                 # Function keys
            # More specific code patterns - only match actual code constructs
            r'\w+\s*\(\s*[^)]*\s*\)\s*\{',  # Function calls with braces
            r'\w+\s*=\s*[^;]*;',     # Variable assignments with semicolon
            r'\w+\.\w+\s*\(',        # Method calls
            r'if\s*\([^)]*\)\s*\{',  # If statements with braces
            r'for\s*\([^)]*\)\s*\{', # For loops with braces
            r'while\s*\([^)]*\)\s*\{', # While loops with braces
        ]
        
        # Check for code patterns
        for pattern in code_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Check for high density of special characters (more lenient)
        special_chars = len(re.findall(r'[{}[\]()=+\-*/<>!&|;:,]', text))
        total_chars = len(text)
        if total_chars > 0 and special_chars / total_chars > 0.3:  # Increased threshold from 0.1 to 0.3
            return True
        
        return False
    
    def filter_chunks_by_language(self, chunks: List[Dict]) -> List[Dict]:
        """
        Filter chunks based on language and content type.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            Filtered list of chunks
        """
        if not self.language_filter_enabled:
            return chunks
        
        filtered_chunks = []
        language_counts = {}
        empty_chunks = 0
        code_chunks = 0
        unknown_language = 0
        
        for chunk in chunks:
            chunk_text = chunk.get('chunkText', '')
            if not chunk_text:
                empty_chunks += 1
                continue
            
            # Skip code content if enabled
            if self.exclude_code_content and self.is_code_content(chunk_text):
                code_chunks += 1
                continue
            
            # Detect language
            detected_language = self.detect_language(chunk_text)
            language_counts[detected_language] = language_counts.get(detected_language, 0) + 1
            
            if detected_language == 'unknown':
                unknown_language += 1
            
            # Check if language is allowed
            if detected_language in self.allowed_languages:
                filtered_chunks.append(chunk)
        
        print(f"🔍 Language filtering: {len(chunks)} chunks -> {len(filtered_chunks)} chunks (allowed languages: {self.allowed_languages})")
        print(f"   📊 Language distribution: {language_counts}")
        
        # Debug information
        if empty_chunks > 0:
            print(f"   ⚠️ {empty_chunks} chunks had empty text")
        if code_chunks > 0:
            print(f"   ⚠️ {code_chunks} chunks were filtered as code content")
        if unknown_language > 0:
            print(f"   ⚠️ {unknown_language} chunks had unknown language")
        
        return filtered_chunks
        
    async def fetch_chunks_from_api(self, session: aiohttp.ClientSession, jwt_token: str, 
                                  skip: int = 0, limit: int = None) -> Dict:
        """
        Fetch chunks from the chunk list API.
        
        Args:
            session: aiohttp session
            jwt_token: JWT token for authentication
            skip: Number of chunks to skip (for pagination)
            limit: Number of chunks to return
            
        Returns:
            Dictionary with chunks and pagination info
        """
        uxo_config = self.config.get('UXO', {})
        app_id = uxo_config.get('app_id')
        domain = uxo_config.get('domain')
        
        # Get URL template from config and replace placeholders
        url_template = self.config.get('question_generation', {}).get('chunk_list_api', {}).get('url_template')
        if url_template:
            url = url_template.format(domain=domain, streamId=app_id)
        else:
            # Fallback to hardcoded URL
            url = f"https://{domain}/api/public/bot/{app_id}/chunk/list"
        
        # Use the exact working payload structure
        # Get limit from config if not provided
        if limit is None:
            limit = self.config.get('question_generation', {}).get('chunks_per_question', 20)
        
        payload = {
            "filters": {
                "conditions": [],
                "operand": "and"
            },
            "enableFilters": False,
            "search": "",
            "skip": skip,
            "limit": limit
        }
        
        headers = {
            'Content-Type': 'application/json',
            'auth': jwt_token
        }
        
        try:
            print(f"   🔗 Making chunk list API call to: {url}")
            print(f"   📝 Payload: skip={skip}, limit={limit}")
            
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    print(f"   ✅ Chunk list API call successful")
                    
                    # Check if we have chunks in the response
                    chunks = response_data.get('chunks', [])
                    print(f"   📊 Found {len(chunks)} chunks in response")
                    
                    return response_data
                else:
                    print(f"   ❌ Error fetching chunks: {response.status} - {await response.text()}")
                    return None
        except Exception as e:
            print(f"   ❌ Exception fetching chunks: {str(e)}")
            return None
    


    async def fetch_chunks_from_api_with_cursor(self, session: aiohttp.ClientSession, jwt_token: str, 
                                               limit: int = None, next_cursor: str = None) -> Dict:
        """
        Fetch chunks from the chunk list API using nextCursor pagination.
        
        Args:
            session: aiohttp session
            jwt_token: JWT token for authentication
            limit: Number of chunks to return
            next_cursor: Next cursor for pagination (optional)
            
        Returns:
            Dictionary with chunks and pagination info
        """
        uxo_config = self.config.get('UXO', {})
        app_id = uxo_config.get('app_id')
        domain = uxo_config.get('domain')
        
        # Get URL template from config and replace placeholders
        url_template = self.config.get('question_generation', {}).get('chunk_list_api', {}).get('url_template')
        if url_template:
            url = url_template.format(domain=domain, streamId=app_id)
        else:
            # Fallback to hardcoded URL
            url = f"https://{domain}/api/public/bot/{app_id}/chunk/list"
        
        # Use the exact working payload structure
        # Get limit from config if not provided
        if limit is None:
            limit = self.config.get('question_generation', {}).get('chunks_per_question', 20)
        
        payload = {
            "filters": {
                "conditions": [],
                "operand": "and"
            },
            "enableFilters": False,
            "search": "",
            "limit": limit
        }
        
        # Add nextCursor if provided
        if next_cursor:
            payload['nextCursor'] = next_cursor
        
        headers = {
            'Content-Type': 'application/json',
            'auth': jwt_token
        }
        
        try:
            print(f"   🔗 Making chunk list API call with cursor to: {url}")
            print(f"   📝 Payload: limit={limit}, nextCursor={'provided' if next_cursor else 'none'}")
            
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    print(f"   ✅ Chunk list API call with cursor successful")
                    
                    # Check if we have chunks in the response
                    chunks = response_data.get('chunks', [])
                    print(f"   📊 Found {len(chunks)} chunks in response")
                    
                    return response_data
                else:
                    print(f"   ❌ Error fetching chunks with cursor: {response.status} - {await response.text()}")
                    return None
        except Exception as e:
            print(f"   ❌ Exception fetching chunks with cursor: {str(e)}")
            return None

    async def get_total_chunk_count(self) -> int:
        """
        Get the total number of chunks available from the API.
        
        Returns:
            Total number of chunks available (capped at 10,000 due to API limits)
        """
        async with aiohttp.ClientSession() as session:
            # Generate JWT token
            uxo_config = self.config.get('UXO', {})
            jwt_token = generate_JWT_token(
                uxo_config.get('client_id'),
                uxo_config.get('client_secret')
            )
            
            # Make initial call to get total chunk count
            print(f"📄 Getting total chunk count...")
            initial_response = await self.fetch_chunks_from_api(session, jwt_token, skip=0, limit=1)
            if initial_response:
                total_chunks = initial_response.get('count', 10000)
                # Cap at 10,000 due to API pagination limits
                total_chunks = min(total_chunks, 10000)
                print(f"📊 Total chunks available: {total_chunks} (capped at 10,000)")
                return total_chunks
            else:
                print(f"⚠️ Could not get total chunk count, using default: 10,000")
                return 10000

    async def get_random_chunks(self, num_chunks: int, min_chunks: int, total_chunks_available: int = None, session: aiohttp.ClientSession = None) -> List[Dict]:
        """
        Get random chunks from the chunk list API with randomized skip values.
        
        Args:
            num_chunks: Target number of chunks (used as limit)
            min_chunks: Minimum number of chunks required
            total_chunks_available: Total chunks available (from initial call)
            session: Optional aiohttp session to reuse
            
        Returns:
            List of chunk dictionaries
        """
        print(f"🔍 Fetching {num_chunks} random chunks using chunk list API (minimum {min_chunks})...")
        
        all_chunks = []
        max_attempts = self.config.get('question_generation', {}).get('max_pagination_attempts', 10)
        
        # Use provided total chunks or default from config
        if total_chunks_available is None:
            total_chunks_available = self.config.get('question_generation', {}).get('default_total_chunks', 10000)
        
        # Use provided session or create new one
        should_close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            should_close_session = True
        
        try:
            # Generate JWT token
            uxo_config = self.config.get('UXO', {})
            jwt_token = generate_JWT_token(
                uxo_config.get('client_id'),
                uxo_config.get('client_secret')
            )
            
            # Generate random skip values
            max_skip = max(0, total_chunks_available - num_chunks)
            random_skips = []
            
            for attempt in range(max_attempts):
                if len(all_chunks) >= num_chunks:
                    break
                
                # Generate random skip value for ALL attempts
                skip_value = random.randint(0, max_skip)
                # Avoid duplicate skip values
                while skip_value in random_skips and len(random_skips) < max_skip:
                    skip_value = random.randint(0, max_skip)
                random_skips.append(skip_value)
                
                print(f"📄 Fetching batch with skip={skip_value}...")
                response = await self.fetch_chunks_from_api(session, jwt_token, skip=skip_value, limit=num_chunks)
                
                if not response:
                    print(f"   ⚠️ No response for attempt {attempt + 1}")
                    continue
                
                # Extract chunks from response
                chunks = response.get('chunks', [])
                if not chunks:
                    print(f"   ⚠️ No chunks found for attempt {attempt + 1}")
                    continue
                
                all_chunks.extend(chunks)
                print(f"📊 Found {len(chunks)} chunks in response")
                
                # Apply language filtering
                filtered_chunks = self.filter_chunks_by_language(all_chunks)
                
                # Check if we have minimum required chunks from config
                if len(filtered_chunks) == 0:
                    print(f"❌ No English chunks found after filtering")
                    return []
                elif len(filtered_chunks) < min_chunks:
                    print(f"⚠️ Limited English chunks available: {len(filtered_chunks)} < {min_chunks}, but proceeding anyway")
                
                # Randomly select the required number of chunks from filtered chunks
                # Use all available chunks if we have fewer than requested
                selected_chunks = random.sample(filtered_chunks, min(num_chunks, len(filtered_chunks)))
                print(f"✅ Selected {len(selected_chunks)} random chunks (after language filtering) from {len(filtered_chunks)} available English chunks")
                
                return selected_chunks
                
        except Exception as e:
            print(f"❌ Error fetching chunks: {str(e)}")
            return []
        finally:
            if should_close_session:
                await session.close()
    
    def generate_question_from_chunks(self, chunks: List[Dict]) -> Tuple[str, List[str], List[Dict]]:
        """
        Generate a question from a list of chunks using LLM and return chunk texts and used chunks.
        
        Args:
            chunks: List of chunk dictionaries
            
        Returns:
            Tuple of (generated_question, chunk_texts_used, chunks_used)
        """
        # Get configuration for question generation
        target_specific_data = self.config.get('question_generation', {}).get('target_specific_data', False)
        max_chunks_per_question = self.config.get('question_generation', {}).get('max_chunks_per_question', 5)
        elaborate_queries = self.config.get('question_generation', {}).get('elaborate_queries', False)
        
        # Prepare chunks with indices for tracking
        chunk_texts = []
        chunk_indices = []  # Track which chunks are used
        valid_chunks = []   # Store the actual chunk objects
        
        # Limit chunks if targeting specific data
        max_chunks = min(max_chunks_per_question, len(chunks)) if target_specific_data else min(5, len(chunks))
        
        for i, chunk in enumerate(chunks[:max_chunks]):
            chunk_text = chunk.get('chunkText', '')
            if chunk_text:
                # Additional filtering for code content and language
                if self.exclude_code_content and self.is_code_content(chunk_text):
                    continue
                
                detected_language = self.detect_language(chunk_text)
                if detected_language not in self.allowed_languages:
                    continue
                
                chunk_texts.append(chunk_text)
                chunk_indices.append(i)
                valid_chunks.append(chunk)
        
        if not chunk_texts:
            return "No valid chunk text found after language and code filtering.", [], []
        
        # If we have very few chunks, use all of them
        min_chunks = self.config.get('question_generation', {}).get('min_chunks_per_question', 1)
        if len(chunk_texts) < min_chunks:
            print(f"   📝 Using all {len(chunk_texts)} available chunks for question generation")
        
        # Get target language from config
        target_language = self.config.get('question_generation', {}).get('language_filter', {}).get('target_language', 'en')
        
        # Create prompt that asks LLM to reference specific chunks
        if elaborate_queries:
            prompt = f"""Based on the following text chunks, generate a detailed customer service question. 

CRITICAL INSTRUCTION: You must ONLY list chunk numbers for chunks you ACTUALLY used to generate your question. Do NOT include chunks that are irrelevant or unused. Be strict and honest about which chunks directly contributed to your question generation.

DIVERSITY RULE: Choose a different topic/theme than previous questions. If you see multiple chunks about different products, services, or topics, select the most diverse and unique topic to avoid repetition.

CHUNK ASSIGNMENT RULE: These chunks are specifically assigned to you for this question. Use ONLY these chunks to generate your question. Do not reference or consider any other chunks.

KEYWORD REQUIREMENT: Your question MUST include specific keywords, product names, service names, or technical terms that appear in the chunk content. This ensures the question is specific enough to retrieve the same chunks when searched.

Text chunks:
{chr(10).join(f"Chunk {i+1}: {text}..." for i, text in enumerate(chunk_texts))}

Generate a detailed customer question that:
1. Sounds like something a real customer would ask
2. Includes specific details (product names, amounts, timeframes, locations, order numbers)
3. Reflects actual customer pain points or needs
4. Requires specific information from the provided content
5. Is conversational and natural in tone
6. Is written in {target_language} language
7. Focuses on a unique topic/theme to ensure diversity
8. Uses ONLY the chunks provided above (no other chunks)
9. MUST include specific keywords from the chunk content to ensure precise retrieval

Format your response as:
Question: [your question here]
Used chunks: [ONLY list chunk numbers you actually used for generating this specific question. If you only used one chunk, list only that one. Be precise and honest.]"""
        else:
            prompt = f"""Based on the following text chunks, generate a simple customer service question. 

CRITICAL INSTRUCTION: You must ONLY list chunk numbers for chunks you ACTUALLY used to generate your question. Do NOT include chunks that are irrelevant or unused. Be strict and honest about which chunks directly contributed to your question generation.

DIVERSITY RULE: Choose a different topic/theme than previous questions. If you see multiple chunks about different products, services, or topics, select the most diverse and unique topic to avoid repetition.

CHUNK ASSIGNMENT RULE: These chunks are specifically assigned to you for this question. Use ONLY these chunks to generate your question. Do not reference or consider any other chunks.

KEYWORD REQUIREMENT: Your question MUST include specific keywords, product names, service names, or technical terms that appear in the chunk content. This ensures the question is specific enough to retrieve the same chunks when searched.

Text chunks:
{chr(10).join(f"Chunk {i+1}: {text}..." for i, text in enumerate(chunk_texts))}

Generate a simple customer question that:
1. Sounds like something a real customer would ask
2. Includes specific details (product names, amounts, timeframes, locations, order numbers)
3. Reflects actual customer pain points or needs
4. Requires specific information from the provided content
5. Is conversational and natural in tone
6. Is written in {target_language} language
7. Keep the query relevant to the chunk content and at most 8-12 words
8. Focuses on a unique topic/theme to ensure diversity
9. Uses ONLY the chunks provided above (no other chunks)
10. MUST include specific keywords from the chunk content to ensure precise retrieval

Format your response as:
Question: [your question here]
Used chunks: [ONLY list chunk numbers you actually used for generating this specific question. If you only used one chunk, list only that one. Be precise and honest.]"""

        messages = [
            {"role": "system", "content": "You are an expert at creating customer service questions. You must be STRICTLY HONEST about which chunks you actually used to generate your question. Only list chunks that directly contributed to your question generation. Do not include irrelevant or unused chunks. Generate ONLY the question text without any quotes or formatting."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.attempt_api_call(messages)
        if response:
            # Parse the response to extract question and used chunks
            question, used_chunk_indices = self.parse_question_response(response, chunk_indices)
            
            # Get the chunk texts and chunks that were actually used
            used_chunk_texts = []
            used_chunks = []
            for idx in used_chunk_indices:
                if idx < len(chunk_texts):
                    used_chunk_texts.append(chunk_texts[idx])
                if idx < len(valid_chunks):
                    used_chunks.append(valid_chunks[idx])
            
            return question, used_chunk_texts, used_chunks
        else:
            return "Failed to generate question.", [], []
    
    def parse_question_response(self, response: str, chunk_indices: List[int]) -> Tuple[str, List[int]]:
        """
        Parse the LLM response to extract the question and used chunk indices.
        
        Args:
            response: LLM response
            chunk_indices: List of chunk indices
            
        Returns:
            Tuple of (question, used_chunk_indices)
        """
        # Clean the response
        cleaned_response = response.strip()
        
        # Try to parse structured response
        if "Question:" in cleaned_response and "Used chunks:" in cleaned_response:
            try:
                # Extract question
                question_start = cleaned_response.find("Question:") + 9
                question_end = cleaned_response.find("Used chunks:")
                question = cleaned_response[question_start:question_end].strip()
                
                # Extract used chunks
                chunks_start = cleaned_response.find("Used chunks:") + 12
                chunks_text = cleaned_response[chunks_start:].strip()
                
                # Parse chunk numbers
                used_chunk_indices = []
                import re
                chunk_numbers = re.findall(r'\d+', chunks_text)
                for num in chunk_numbers:
                    chunk_idx = int(num) - 1  # Convert to 0-based index
                    if 0 <= chunk_idx < len(chunk_indices):
                        used_chunk_indices.append(chunk_indices[chunk_idx])
                
                return question, used_chunk_indices
                # If parsing succeeded but no chunks were found, use all chunks
                if not used_chunk_indices and chunk_indices:
                    used_chunk_indices = chunk_indices
            except:
                pass
        
        # Fallback: if parsing fails, assume all chunks were used
        used_chunk_indices = []
        # If no chunks were parsed, use all available chunks
        if not used_chunk_indices and chunk_indices:
            used_chunk_indices = chunk_indices
        return cleaned_response, chunk_indices
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for API calls.
        
        Returns:
            Dictionary with authorization headers
        """
        try:
            # Generate JWT token
            uxo_config = self.config.get('UXO', {})
            jwt_token = generate_JWT_token(
                uxo_config.get('client_id'),
                uxo_config.get('client_secret')
            )
            
            return {
                'Authorization': f'Bearer {jwt_token}',
                'Content-Type': 'application/json'
            }
        except Exception as e:
            print(f"❌ Error generating auth headers: {str(e)}")
            return {}


    
    def attempt_api_call(self, messages: List[Dict]) -> Optional[str]:
        """
        Attempt to make an API call with retry logic.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            API response or None if failed
        """
        max_retries = self.config.get('question_generation', {}).get('max_api_retries', 3)
        for attempt in range(max_retries):
            try:
                # Get LLM parameters from config
                temperature = self.config.get('question_generation', {}).get('llm_temperature', 0.7)
                max_tokens = self.config.get('question_generation', {}).get('llm_max_tokens', 100)
                
                if self.model_type == "azure":
                    response = self.openai_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                else:
                    response = self.openai_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                
                content = response.choices[0].message.content.strip()
                return content
                
            except Exception as e:
                print(f"⚠️ API call attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    print(f"❌ API call failed after {max_retries} attempts: {str(e)}")
                    return None
                else:
                    print(f"⚠️ Retrying in 1 second...")
                    time.sleep(1)
        
        return None
    
    async def generate_evaluation_questions(self) -> List[Dict]:
        """
        Generate evaluation questions using chunks from the API.
        
        Returns:
            List of dictionaries containing questions and their associated chunks
        """
        num_questions = self.config.get('question_generation', {}).get('num_questions', 10)
        questions_per_batch = self.config.get('question_generation', {}).get('questions_per_batch', 1)
        print(f"🎯 Generating {num_questions} questions with {questions_per_batch} questions per batch, concurrency={self.max_concurrent}...")
        
        # Try async first, if it fails, fall back to sequential
        try:
            return await self._generate_questions_with_retry(num_questions, questions_per_batch)
        except Exception as e:
            print(f"⚠️ Async generation failed: {str(e)}")
            print("🔄 Falling back to sequential generation...")
            return await self._generate_questions_sequential(num_questions, questions_per_batch)

    async def _generate_questions_with_retry(self, num_questions: int, questions_per_batch: int) -> List[Dict]:
        """
        Generate questions with retry logic to ensure we get the target number.
        """
        print(f"🔄 Executing question generation with retry logic to get {num_questions} questions...")
        
        all_questions = []
        max_attempts = self.config.get('question_generation', {}).get('max_generation_attempts', 20)  # Maximum attempts to get enough questions
        attempt = 0
        
        while len(all_questions) < num_questions and attempt < max_attempts:
            attempt += 1
            print(f"   🔄 Attempt {attempt}: Need {num_questions - len(all_questions)} more questions...")
            
            # Calculate how many batches we need for this attempt
            remaining_questions = num_questions - len(all_questions)
            batches_needed = (remaining_questions + questions_per_batch - 1) // questions_per_batch
            
            # Create tasks for this attempt
            tasks = []
            for i in range(batches_needed):
                task = self.generate_batch_questions_async(i+1, batches_needed, questions_per_batch)
                tasks.append(task)
            
            # Execute tasks
            for i, task in enumerate(tasks):
                try:
                    result = await task
                    if result:
                        all_questions.extend(result)
                        print(f"   ✅ Got {len(result)} questions from batch {i+1}")
                    else:
                        print(f"   ❌ Batch {i+1} failed")
                except Exception as e:
                    print(f"   ❌ Error in batch {i+1}: {str(e)}")
            
            # If we got some questions, show progress
            if len(all_questions) > 0:
                print(f"   📊 Progress: {len(all_questions)}/{num_questions} questions generated")
        
        print(f"📊 Final result: {len(all_questions)}/{num_questions} questions generated after {attempt} attempts")
        return all_questions[:num_questions]  # Return only the requested number

    async def _generate_questions_sequential(self, num_questions: int, questions_per_batch: int) -> List[Dict]:
        """
        Generate questions sequentially to avoid asyncio loop issues.
        """
        evaluation_data = []
        
        # Calculate number of batches needed
        num_batches = (num_questions + questions_per_batch - 1) // questions_per_batch
        
        for batch_num in range(num_batches):
            print(f"   🔍 Generating batch {batch_num+1}/{num_batches}...")
            try:
                batch_data = await self.generate_batch_questions_async(batch_num+1, num_batches, questions_per_batch)
                if batch_data:
                    evaluation_data.extend(batch_data)
                    print(f"   ✅ Batch {batch_num+1}: {len(batch_data)} questions generated")
                else:
                    print(f"   ❌ Failed to generate batch {batch_num+1}")
            except Exception as e:
                print(f"   ❌ Error generating batch {batch_num+1}: {str(e)}")
        
        print(f"📊 Sequential generation completed: {len(evaluation_data)}/{num_questions} questions generated successfully")
        return evaluation_data

    async def _generate_questions_async(self, num_questions: int, questions_per_batch: int) -> List[Dict]:
        """
        Original async generation method.
        """
        print(f"🔄 Executing {num_questions} question generation tasks with {questions_per_batch} questions per batch, concurrency={self.max_concurrent}...")
        
        # Calculate number of batches needed
        num_batches = (num_questions + questions_per_batch - 1) // questions_per_batch
        
        # Create tasks for all batches
        tasks = []
        for i in range(num_batches):
            task = self.generate_batch_questions_async(i+1, num_batches, questions_per_batch)
            tasks.append(task)
        
        # Execute tasks with concurrency control
        results = []
        for i, task in enumerate(tasks):
            try:
                result = await task
                if result:
                    results.extend(result)
                    print(f"   ✅ Batch {i+1}: {len(result)} questions generated")
            except Exception as e:
                print(f"❌ Error in batch {i+1}: {str(e)}")
        
        print(f"📊 Generation completed: {len(results)}/{num_questions} questions generated successfully")
        return results
    
    async def generate_batch_questions_async(self, batch_index: int, total_batches: int, questions_per_batch: int, session: aiohttp.ClientSession = None) -> Optional[List[Dict]]:
        """
        Generate multiple questions from a single batch of chunks asynchronously.
        Each question gets its own dedicated chunk set to avoid repetition.
        
        Args:
            batch_index: Index of the batch being generated
            total_batches: Total number of batches to generate
            questions_per_batch: Number of questions to generate from this batch
            session: Optional aiohttp session to reuse
            
        Returns:
            List of dictionaries with question data or None if failed
        """
        async with self.semaphore:
            try:
                # Get configuration
                max_chunks_per_question = self.config.get('question_generation', {}).get('chunks_per_question', 20)
                min_chunks = self.config.get('question_generation', {}).get('min_chunks_per_question', 10)
                
                # Calculate total chunks needed - use max_chunks_per_question only, not multiplied by questions_per_batch
                total_chunks_needed = max_chunks_per_question
                
                # Get total chunk count (this will be cached after first call)
                if not hasattr(self, '_total_chunks_available'):
                    self._total_chunks_available = await self.get_total_chunk_count()
                
                # Get all chunks needed for this batch
                all_chunks = await self.get_random_chunks(total_chunks_needed, min_chunks, self._total_chunks_available, session)
                if not all_chunks:
                    return None
                
                # Filter chunks by language and code content
                filtered_chunks = self.filter_chunks_by_language(all_chunks)
                if not filtered_chunks:
                    print(f"   ❌ No qualified chunks after language filtering")
                    return None
                
                # Calculate how many questions we can generate based on available chunks
                total_qualified_chunks = len(filtered_chunks)
                
                # Calculate maximum questions possible with min_chunks_per_question
                max_questions_possible = total_qualified_chunks // min_chunks
                
                # Use the smaller of: questions_per_batch or max_questions_possible
                actual_questions_to_generate = min(questions_per_batch, max_questions_possible)
                
                if actual_questions_to_generate == 0:
                    print(f"   ❌ Not enough chunks to generate any questions (need at least {min_chunks} chunks)")
                    return None
                
                # Calculate chunks per question (distribute chunks evenly)
                chunks_per_question_actual = total_qualified_chunks // actual_questions_to_generate
                
                print(f"   📊 Dividing {total_qualified_chunks} qualified chunks into {actual_questions_to_generate} questions ({chunks_per_question_actual} chunks each)")
                
                # Generate questions with dedicated chunk sets
                batch_questions = []
                for i in range(actual_questions_to_generate):
                    # Get dedicated chunk set for this question
                    start_idx = i * chunks_per_question_actual
                    end_idx = start_idx + chunks_per_question_actual
                    question_chunks = filtered_chunks[start_idx:end_idx]
                    
                    if not question_chunks:
                        print(f"   ❌ No chunks available for question {i+1}")
                        continue
                    
                    print(f"   🔍 Generating question {i+1} with {len(question_chunks)} dedicated chunks...")
                    
                    # Generate question from dedicated chunk set
                    question, original_chunk_texts, used_chunks = self.generate_question_from_chunks(question_chunks)
                    
                    if question and question != "Failed to generate question." and question != "No valid chunk text found after language and code filtering.":
                        # Extract unique record titles from the chunks that were actually used for generation
                        record_titles = self.extract_unique_record_titles(used_chunks)
                        
                        # Create evaluation data entry with original chunk texts and record titles
                        evaluation_entry = {
                            "query": question,
                            "chunks": question_chunks,  # Only chunks assigned to this question
                            "original_chunk_texts": original_chunk_texts,  # Original chunk texts used for generation
                            "recordTitles": record_titles,  # Unique record titles from chunks actually used
                            "total_chunks_available": self._total_chunks_available,
                            "chunks_used_for_generation": len(original_chunk_texts),
                            "chunks_assigned_to_question": len(question_chunks),
                            "generation_timestamp": datetime.now().isoformat(),
                            "batch_index": batch_index,
                            "question_in_batch": i + 1
                        }
                        
                        batch_questions.append(evaluation_entry)
                        print(f"   ✅ Question {i+1} generated successfully")
                    else:
                        print(f"   ❌ Failed to generate question {i+1}")
                
                if batch_questions:
                    return batch_questions
                else:
                    return None
                    
            except Exception as e:
                print(f"   ❌ Error generating batch {batch_index}: {str(e)}")
                return None
    
    async def generate_single_question_async(self, question_index: int, total_questions: int, session: aiohttp.ClientSession = None) -> Optional[Dict]:
        """
        Generate a single question asynchronously with semaphore control.
        
        Args:
            question_index: Index of the question being generated
            total_questions: Total number of questions to generate
            session: Optional aiohttp session to reuse
            
        Returns:
            Dictionary with question data or None if failed
        """
        async with self.semaphore:
            try:
                # Get fresh chunks for this question
                chunks_per_batch = self.config.get('question_generation', {}).get('chunks_per_question', 20)
                min_chunks = self.config.get('question_generation', {}).get('min_chunks_per_question', 10)
                
                # Get total chunk count (this will be cached after first call)
                if not hasattr(self, '_total_chunks_available'):
                    self._total_chunks_available = await self.get_total_chunk_count()
                
                # Get exactly the number of chunks we need
                initial_chunks_needed = chunks_per_batch
                chunks = await self.get_random_chunks(initial_chunks_needed, min_chunks, self._total_chunks_available, session)
                if not chunks:
                    return None
                
                # Generate question from chunks
                question, original_chunk_texts, used_chunks = self.generate_question_from_chunks(chunks)
                
                if question and question != "Failed to generate question.":
                    # Extract unique record titles from the chunks that were actually used for generation
                    record_titles = self.extract_unique_record_titles(used_chunks)
                    
                    # Create evaluation data entry with original chunk texts and record titles
                    evaluation_entry = {
                        "query": question,
                        "chunks": chunks,  # All chunks available for this question
                        "original_chunk_texts": original_chunk_texts,  # Original chunk texts used for generation
                        "recordTitles": record_titles,  # Unique record titles from chunks actually used
                        "total_chunks_available": self._total_chunks_available,
                        "chunks_used_for_generation": len(original_chunk_texts),
                        "generation_timestamp": datetime.now().isoformat()
                    }
                    
                    print(f"   ✅")
                    return evaluation_entry
                else:
                    print(f"   ❌")
                    return None
                    
            except Exception as e:
                print(f"   ❌ Error generating question {question_index}: {str(e)}")
                return None
    
    def save_evaluation_data(self, evaluation_data: List[Dict]) -> str:
        """
        Save evaluation data to a JSON file in the Generate_Question folder.
        
        Args:
            evaluation_data: List of dictionaries with query and chunks
            
        Returns:
            Path to the saved file
        """
        # Create Generate_Question directory if it doesn't exist
        generate_question_dir = "Generate_Question"
        if not os.path.exists(generate_question_dir):
            os.makedirs(generate_question_dir)
            print(f"📁 Created {generate_question_dir} directory")
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"generate_question_{timestamp}.json"
        filepath = os.path.join(generate_question_dir, filename)
        
        # Save to JSON file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(evaluation_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Evaluation data saved to: {filepath}")
        return filepath


def setup_openai_client(model: str = "openai"):
    """
    Setup OpenAI client based on model choice.
    
    Args:
        model: Model choice (openai or azure)
        
    Returns:
        Configured OpenAI client
    """
    config = ConfigManager().get_config()
    
    if model == "azure":
        # Get API key from environment, everything else from config
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable not set")
        
        azure_config = config.get('azure', {})
        client = AzureOpenAI(
            api_key=api_key,
            api_version=azure_config.get('openai_api_version', '2024-02-15-preview'),
            azure_endpoint=azure_config.get('base_url'),
            azure_deployment=azure_config.get('model_deployment')
        )
    else:
        # Get API key from environment, everything else from config
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        openai_config = config.get('openai', {})
        client = OpenAI(api_key=api_key)
    
    return client


def main():
    """
    Main function to generate evaluation questions.
    """
    parser = argparse.ArgumentParser(description='Generate evaluation questions from chunks')
    parser.add_argument('--model', type=str, default='openai', choices=['openai', 'azure'],
                       help='Model to use for question generation (default: openai)')
    parser.add_argument('--num_questions', type=int, default=None,
                       help='Number of questions to generate (overrides config)')
    parser.add_argument('--concurrency', type=int, default=3,
                       help='Maximum concurrent API calls (default: 3)')
    parser.add_argument('--query_type', type=str, default='simple', choices=['simple', 'elaborate'],
                       help='Type of queries to generate: simple or elaborate (default: simple)')
    
    args = parser.parse_args()
    
    # Load configuration
    config = ConfigManager().get_config()
    
    # Override config with command line arguments
    if args.num_questions:
        config['question_generation']['num_questions'] = args.num_questions
        print(f"📝 Overriding config: generating {args.num_questions} questions")
    
    # Set query type in config
    config['question_generation']['elaborate_queries'] = (args.query_type == 'elaborate')
    query_type_display = "elaborate" if args.query_type == 'elaborate' else "simple"
    print(f"🎯 Generating {query_type_display} customer service questions.")
    
    # Setup OpenAI client
    openai_client = setup_openai_client(args.model)
    model_name = get_model_name(args.model)
    
    # Initialize generator with concurrency
    generator = QuestionGenerator(model_name, openai_client, args.model, args.concurrency)
    print(f"⚡ Using concurrency: {args.concurrency}")
    
    try:
        # Generate questions
        print("🎯 Generating questions...")
        evaluation_data = asyncio.run(generator.generate_evaluation_questions())
        
        if evaluation_data:
            # Save to file
            filepath = generator.save_evaluation_data(evaluation_data)
            print(f"💾 Data saved to: {filepath}")
            print("✅ Question generation completed successfully!")
        else:
            print("❌ No questions were generated successfully")
            
    except Exception as e:
        print(f"❌ Error during question generation: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 