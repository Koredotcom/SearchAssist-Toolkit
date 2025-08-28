#!/usr/bin/env python3
"""
Retrieval Benchmark Evaluator

This script evaluates RAG retrieval systems focusing on:
1. Chunk qualification and usage patterns
2. Source relevance analysis
3. LLM utilization of retrieved chunks
4. Cross-window chunk analysis

Usage:
    python retrieval_benchmark.py --input data.xlsx --use_search_api
    python retrieval_benchmark.py --input data.xlsx --sheet Sheet1 --use_search_api
    python retrieval_benchmark.py --input data.xlsx --output results.xlsx --use_search_api
"""

import os
import sys
import argparse
import pandas as pd
import asyncio
import time
from datetime import datetime
from openai import OpenAI
from tqdm import tqdm
import json
from typing import List, Dict, Tuple, Optional, Any
from openai import AzureOpenAI
import hashlib

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.configManager import ConfigManager
from evaluators.baseEvaluator import BaseEvaluator
from async_api_calls import call_search_api_async_simple, AsyncAnswerProcessor


class RetrievalBenchmarkEvaluator(BaseEvaluator):
    """
    Retrieval benchmark evaluator that analyzes:
    - Chunk qualification patterns
    - Source utilization by LLM
    - Cross-window chunk analysis
    - Retrieval relevance metrics
    """
    
    def __init__(self, model_name: str, openai_client, model_type: str = "openai", max_concurrent: int = 5):
        self.model_name = model_name
        self.openai_client = openai_client
        self.model_type = model_type
        self.config = ConfigManager().get_config()
        # Create semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        
    def analyze_chunk_usage_patterns(self, chunk_results: List[Dict]) -> Dict:
        """
        Analyze chunk usage patterns from the search API response.
        
        Args:
            chunk_results: List of chunk results from template.chunk_result
            
        Returns:
            Dictionary with chunk usage analysis
        """
        analysis = {
            'total_chunks': len(chunk_results),
            'qualified_chunks': 0,
            'sent_to_llm': 0,
            'used_in_answer': 0,
            'source_breakdown': {},
            'chunk_scores': [],
            'next_chunk_analysis': {
                'has_next_chunks': 0,
                'next_chunk_count': 0
            }
        }
        
        for i, chunk in enumerate(chunk_results):
            source = chunk.get('_source', {})
            
            # Count qualified chunks
            if source.get('chunkQualified', False):
                analysis['qualified_chunks'] += 1
            
            # Count chunks sent to LLM
            if source.get('sentToLLM', False):
                analysis['sent_to_llm'] += 1
            
            # Count chunks used in answer
            if source.get('usedInAnswer', False):
                analysis['used_in_answer'] += 1
            
            # Track record title breakdown
            record_title = source.get('recordTitle', 'Unknown')
            if record_title not in analysis['source_breakdown']:
                analysis['source_breakdown'][record_title] = {
                    'total': 0,
                    'qualified': 0,
                    'sent_to_llm': 0,
                    'used_in_answer': 0
                }
            
            analysis['source_breakdown'][record_title]['total'] += 1
            if source.get('chunkQualified', False):
                analysis['source_breakdown'][record_title]['qualified'] += 1
            if source.get('sentToLLM', False):
                analysis['source_breakdown'][record_title]['sent_to_llm'] += 1
            if source.get('usedInAnswer', False):
                analysis['source_breakdown'][record_title]['used_in_answer'] += 1
            
            # Track chunk scores
            score = source.get('score', 0)
            analysis['chunk_scores'].append(score)
            
            # Analyze next chunks
            next_chunk_ids = source.get('nextChunkIds', [])
            if next_chunk_ids:
                analysis['next_chunk_analysis']['has_next_chunks'] += 1
                analysis['next_chunk_analysis']['next_chunk_count'] += len(next_chunk_ids)
        
        # Calculate averages
        if analysis['chunk_scores']:
            analysis['avg_chunk_score'] = sum(analysis['chunk_scores']) / len(analysis['chunk_scores'])
            analysis['max_chunk_score'] = max(analysis['chunk_scores'])
            analysis['min_chunk_score'] = min(analysis['chunk_scores'])
        
        return analysis
    
    def analyze_source_relevance(self, query: str, chunk_results: List[Dict]) -> Dict:
        """
        Analyze source relevance based on chunk content and query.
        
        Args:
            query: User query
            chunk_results: List of chunk results
            
        Returns:
            Dictionary with source relevance analysis
        """
        relevance_analysis = {
            'source_relevance_scores': {},
            'content_overlap': {},
            'keyword_matches': {}
        }
        
        # Extract keywords from query (simple approach)
        query_keywords = set(query.lower().split())
        
        for chunk in chunk_results:
            source = chunk.get('_source', {})
            record_title = source.get('recordTitle', 'Unknown')
            chunk_text = source.get('chunkText', '')
            
            if record_title not in relevance_analysis['source_relevance_scores']:
                relevance_analysis['source_relevance_scores'][record_title] = []
                relevance_analysis['content_overlap'][record_title] = 0
                relevance_analysis['keyword_matches'][record_title] = 0
            
            # Calculate keyword overlap
            chunk_keywords = set(chunk_text.lower().split())
            overlap = len(query_keywords.intersection(chunk_keywords))
            relevance_analysis['keyword_matches'][record_title] += overlap
            
            # Track chunk scores for this source
            score = source.get('score', 0)
            relevance_analysis['source_relevance_scores'][record_title].append(score)
        
        # Calculate average relevance scores per record title
        for record_title in relevance_analysis['source_relevance_scores']:
            scores = relevance_analysis['source_relevance_scores'][record_title]
            if scores:
                relevance_analysis['source_relevance_scores'][record_title] = {
                    'avg_score': sum(scores) / len(scores),
                    'max_score': max(scores),
                    'min_score': min(scores),
                    'chunk_count': len(scores)
                }
        
        return relevance_analysis
    
    def text_overlap_ratio(self, text1: str, text2: str) -> float:
        """
        Calculate the overlap ratio between two texts using word-based comparison.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Overlap ratio (0.0 to 1.0)
        """
        # Clean and normalize texts
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def evaluate_chunk_overlap(self, retrieved_chunks: List[Dict], original_chunk_texts: List[str]) -> Dict:
        """
        Evaluate chunk overlap between retrieved chunks and original chunks used to generate the query.
        
        Args:
            retrieved_chunks: List of chunks retrieved by the search API
            original_chunk_texts: List of original chunk texts that were used to generate the question
            
        Returns:
            Dictionary with overlap metrics
        """
        if not retrieved_chunks or not original_chunk_texts:
            return {
                'chunk_overlap_score': 0.0,
                'chunks_retrieved': 0,
                'chunks_original': len(original_chunk_texts),
                'overlapping_chunks': 0,
                'overlap_percentage': 0.0,
                'overlap_explanation': 'No chunks to compare'
            }
        
        # Extract chunk texts from retrieved chunks
        retrieved_texts = []
        for chunk in retrieved_chunks:
            chunk_text = chunk.get('chunkText', '')
            if chunk_text:
                retrieved_texts.append(chunk_text)
            else:
                # Try alternative field names
                alt_text = chunk.get('text', '') or chunk.get('content', '') or chunk.get('_source', {}).get('chunkText', '')
                if alt_text:
                    retrieved_texts.append(alt_text)
        
        # Check which original chunks (used to generate query) are present in retrieved chunks
        found_original_chunks = 0
        total_original_chunks = len(original_chunk_texts)
        
        for original_text in original_chunk_texts:
            for retrieved_text in retrieved_texts:
                # Check for exact match or significant overlap (>30% similarity)
                similarity = self.text_overlap_ratio(original_text, retrieved_text)
                if original_text == retrieved_text or similarity > 0.3:
                    found_original_chunks += 1
                    break
        
        # Calculate overlap score (0-1 scale)
        if total_original_chunks == 0:
            chunk_overlap_score = 0.0
            overlap_percentage = 0.0
        else:
            chunk_overlap_score = found_original_chunks / total_original_chunks
            overlap_percentage = chunk_overlap_score * 100
        
        # Create explanation
        if found_original_chunks == 0:
            explanation = f"No original chunks found in retrieved results. {found_original_chunks}/{total_original_chunks} chunks used to generate query were retrieved."
        elif found_original_chunks == total_original_chunks:
            explanation = f"Perfect retrieval! All {total_original_chunks} chunks used to generate query were found in retrieved results ({overlap_percentage:.1f}% overlap)."
        else:
            explanation = f"Partial retrieval: {found_original_chunks}/{total_original_chunks} chunks used to generate query were found in retrieved results ({overlap_percentage:.1f}% overlap)."
        
        return {
            'chunk_overlap_score': chunk_overlap_score,
            'chunks_retrieved': len(retrieved_texts),
            'chunks_original': total_original_chunks,
            'overlapping_chunks': found_original_chunks,
            'overlap_percentage': overlap_percentage,
            'overlap_explanation': explanation
        }
    
    def create_content_fingerprint(self, text: str) -> str:
        """
        Create a content fingerprint for text that remains stable across training cycles.
        
        Args:
            text: Text content
            
        Returns:
            Content fingerprint string
        """
        # Clean and normalize text
        cleaned_text = text.strip()
        if len(cleaned_text) > 200:
            # Use first 100 chars + last 100 chars + total length
            fingerprint_text = cleaned_text[:100] + cleaned_text[-100:] + str(len(cleaned_text))
        else:
            # For shorter text, use the whole text
            fingerprint_text = cleaned_text + str(len(cleaned_text))
        
        # Create hash
        hash_object = hashlib.md5(fingerprint_text.encode('utf-8'))
        return hash_object.hexdigest()[:16]  # Use first 16 chars for readability
    
    def evaluate_context_relevance(self, query: str, chunk_results: List[Dict]) -> Dict:
        """
        Evaluate context relevance using the exact prompt format from prompts.json.
        
        Args:
            query: User query
            chunk_results: List of chunk results from the search API
            
        Returns:
            Dictionary with context relevance score and explanation
        """
        # Extract only chunkText from chunks that were actually sent to LLM
        sent_to_llm_chunk_texts = []
        for i, chunk in enumerate(chunk_results):
            source = chunk.get('_source', {})
            if source.get('sentToLLM', False):  # Only include chunks that were sent to LLM
                chunk_text = source.get('chunkText', '')
                if chunk_text:
                    sent_to_llm_chunk_texts.append(chunk_text)
        
        # Format chunks for the prompt (just the text content, like LLMEvaluator)
        context_text = ""
        if sent_to_llm_chunk_texts:
            context_text = "\n\n".join(sent_to_llm_chunk_texts)
        else:
            context_text = "No chunks were sent to the LLM."
        
        # Use the exact prompt from prompts.json but modified for JSON output
        prompt = f"""You are an expert evaluator helping assess the quality of information retrieval for question answering systems.

Given a user query and a retrieved context passage, your task is to evaluate:

1. **Relevance**: How directly the context relates to the query.
2. **Usefulness**: How helpful this context would be in answering the query.

Please return:
- A **Relevance score** from 0 to 5, where:
    - 0 = Completely irrelevant
    - 1 = Slightly related
    - 2 = Moderately related
    - 3 = Related but lacking detail
    - 4 = Mostly relevant and partially helpful
    - 5 = Highly relevant and directly helpful for answering the query

- A **short explanation** justifying your score.

---

**Query:**
{query}

**Retrieved Context:**
{context_text}

---

Your response should be in JSON format:
{{"Relevance": [0-5], "Explanation": "[1-3 sentences explaining your score]"}}"""

        messages = [
            {"role": "system", "content": "You are an expert evaluator for information retrieval and question-answering systems."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.attempt_api_call(messages)
        if response:
            try:
                # Parse the response using JSON format (similar to cragEvaluationPrompt)
                import json
                import re
                
                # Clean the response - remove markdown code blocks if present
                cleaned_response = response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()
                
                response_json = json.loads(cleaned_response)
                relevance_score = float(response_json.get('Relevance', 0.0))
                llm_explanation = response_json.get('Explanation', 'No explanation provided')
                
                explanation = f"Context relevance score: {relevance_score}/5 - {llm_explanation}"
                
                # Convert 0-5 scale to 0-1 scale for consistency with existing code
                normalized_score = relevance_score / 5.0
                
                return {
                    'context_relevance_score': normalized_score,
                    'context_relevance_explanation': explanation
                }
            except Exception as e:
                print(f"Warning: Failed to parse context relevance response: {response}")
                print(f"Parse Error: {e}")
                return {
                    'context_relevance_score': 0.0,
                    'context_relevance_explanation': f'Failed to parse context relevance response: {str(e)}. This indicates an issue with the evaluation process.'
                }
        else:
            return {
                'context_relevance_score': 0.0,
                'context_relevance_explanation': 'Failed to evaluate context relevance due to API call failure. This indicates a technical issue with the evaluation process.'
            }
    
    def evaluate_answer_relevance(self, query: str, answer: str, chunk_results: List[Dict]) -> Dict:
        """
        Evaluate answer relevance using the same style as cragEvaluationPrompt but without ground truth.
        
        Args:
            query: User query
            answer: Generated answer
            chunk_results: List of chunk results from the search API
            
        Returns:
            Dictionary with answer relevance score and explanation
        """
        # Use cragEvaluationPrompt style but without ground truth and adapted for relevance
        prompt = f"""# Task:
You are given a Question and a model Prediction. Your task is to evaluate how relevant and accurate the model Prediction is in addressing the Question. Follow the instructions step by step to make a judgement.

1. Evaluate if the prediction directly addresses the user's question and intent.
2. Consider the completeness and accuracy of the information provided.
3. If the model prediction says that it couldn't answer the question or it doesn't have enough information, the relevance should be low.

# Output:
Respond with only a single JSON string with a "Relevance" field which is a score from 0 to 1, where:
- 0 = Completely irrelevant or doesn't address the question
- 0.3 = Slightly related but not helpful
- 0.5 = Somewhat relevant and partially helpful
- 0.7 = Relevant and helpful
- 0.9-1.0 = Highly relevant and directly addresses the question

# Examples:
Question: how many seconds is 3 minutes 15 seconds?
Prediction: 3 minutes 15 seconds is 195 seconds.
Relevance: 1.0

Question: Who authored The Taming of the Shrew (published in 2002)?
Prediction: The author to The Taming of the Shrew is Roma Shakespeare.
Relevance: 0.5

Question: Who played Sheldon in Big Bang Theory?
Prediction: I am sorry I don't know.
Relevance: 0.0

Question: {query}
Prediction: {answer}
Relevance: [0-1]"""

        messages = [
            {"role": "system", "content": "You are an expert evaluator for question-answering systems. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.attempt_api_call(messages)
        if response:
            try:
                # Parse the response using JSON format (similar to cragEvaluationPrompt)
                import json
                import re
                
                # Clean the response - remove markdown code blocks if present
                cleaned_response = response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()
                
                response_json = json.loads(cleaned_response)
                relevance_score = float(response_json.get('Relevance', 0.0))
                explanation = f"Relevance score: {relevance_score} - Answer relevance evaluation based on how well the prediction addresses the query."
                
                # Additional penalty if no chunks were used in answer
                chunks_used_count = sum(1 for chunk in chunk_results 
                                      if chunk.get('_source', {}).get('usedInAnswer', False))
                
                if chunks_used_count == 0:
                    # Penalize answers that don't use any chunks (reduce score but don't make it 0)
                    relevance_score = min(relevance_score, 0.5)  # Less strict penalty for 0.9 accuracy target
                    explanation = f"{explanation} [PENALIZED: No chunks were used in generating this answer.]"
                
                return {
                    'answer_relevance_score': relevance_score,
                    'answer_relevance_explanation': explanation
                }
            except Exception as e:
                print(f"Warning: Failed to parse answer relevance response: {response}")
                print(f"Parse Error: {e}")
                return {
                    'answer_relevance_score': 0.0,
                    'answer_relevance_explanation': f'Failed to parse answer relevance response: {str(e)}. This indicates an issue with the evaluation format or API response.'
                }
        else:
            return {
                'answer_relevance_score': 0.0,
                'answer_relevance_explanation': 'Failed to evaluate answer relevance due to API call failure. This indicates a technical issue with the evaluation process.'
            }
    
    def evaluate_comprehensive_relevance(self, query: str, answer: str, chunk_results: List[Dict]) -> Dict:
        """
        Evaluate both context relevance and answer relevance separately.
        
        Args:
            query: User query
            answer: Generated answer
            chunk_results: List of chunk results from the search API
            
        Returns:
            Dictionary with both relevance scores and explanations
        """
        # Evaluate context relevance using prompts.json format
        context_result = self.evaluate_context_relevance(query, chunk_results)
        
        # Check if answer search is enabled in config
        answer_search_enabled = self.config.get('search_api', {}).get('answerSearch', True)
        
        if answer_search_enabled:
            # Evaluate answer relevance using RAGAS format
            answer_result = self.evaluate_answer_relevance(query, answer, chunk_results)
            answer_relevance_score = answer_result['answer_relevance_score']
            answer_relevance_explanation = answer_result['answer_relevance_explanation']
        else:
            # Skip answer relevance evaluation when answerSearch is False
            answer_relevance_score = 0.0
            answer_relevance_explanation = 'Answer relevance evaluation skipped (answerSearch=False in config)'
        
        # Combine results (consistent with LLMEvaluator.py)
        return {
            'context_relevance_score': context_result['context_relevance_score'],
            'answer_relevance_score': answer_relevance_score,
            'context_relevance_explanation': context_result['context_relevance_explanation'],
            'answer_relevance_explanation': answer_relevance_explanation
            }
    

    
    def _parse_score_response(self, response: str, score_type: str) -> Tuple[float, str]:
        """
        Parse score response from LLM using the 0-5 scale format from prompts.json.
        
        Args:
            response: LLM response
            score_type: Type of score being parsed
            
        Returns:
            Tuple of (normalized_score, explanation) - normalized to 0-1 scale
        """
        try:
            lines = response.strip().split('\n')
            score = 0.0
            explanation = ""
            
            for line in lines:
                if f"{score_type.capitalize()} Score:" in line or "Relevance Score:" in line:
                    score_str = line.split(':')[1].strip()
                    # Remove any brackets or extra characters
                    score_str = score_str.replace('[', '').replace(']', '').replace('0–5', '').strip()
                    score = float(score_str)
                elif "Explanation:" in line:
                    explanation = line.split(':', 1)[1].strip()
                    # Remove any brackets or extra characters
                    explanation = explanation.replace('[', '').replace(']', '').strip()
            
            # Convert 0-5 scale to 0-1 scale for consistency
            normalized_score = score / 5.0
            
            return normalized_score, explanation
        except Exception as e:
            print(f"Warning: Failed to parse {score_type} score response: {e}")
            return 0.0, f"Failed to parse {score_type} score"
    
    async def evaluate_single_sample(self, index: int, query: str, search_response: Dict) -> Dict:
        """
        Evaluate a single sample from the search API response.
        
        Args:
            index: Sample index
            query: User query
            search_response: Full search API response
            
        Returns:
            Dictionary with evaluation results
        """
        try:
            # Extract data from response using helper function
            response_data = self.extract_response_data(search_response)
            answer = response_data['answer']
            error_message = response_data['error_message']
            chunk_results = response_data['chunk_results']
            
            # Analyze chunk usage patterns
            chunk_analysis = self.analyze_chunk_usage_patterns(chunk_results)
            
            # Analyze source relevance
            source_relevance = self.analyze_source_relevance(query, chunk_results)
            
            # Evaluate comprehensive relevance (both answer and context)
            relevance_evaluation = self.evaluate_comprehensive_relevance(query, answer, chunk_results)
            
            # Extract unique record titles for each category
            qualified_record_titles = []
            sent_to_llm_record_titles = []
            used_in_answer_record_titles = []
            
            for record_title, record_data in chunk_analysis['source_breakdown'].items():
                if record_data.get('qualified', 0) > 0:
                    qualified_record_titles.append(record_title)
                if record_data.get('sent_to_llm', 0) > 0:
                    sent_to_llm_record_titles.append(record_title)
                if record_data.get('used_in_answer', 0) > 0:
                    used_in_answer_record_titles.append(record_title)
            
            # Prepare results with only required columns
            results = {
                'query': query,
                'answer': answer,
                'answer_relevance_score': relevance_evaluation['answer_relevance_score'],
                'qualified_chunks': chunk_analysis['qualified_chunks'],
                'sent_to_llm': chunk_analysis['sent_to_llm'],
                'used_in_answer': chunk_analysis['used_in_answer'],
                'qualified_record_titles': ', '.join(qualified_record_titles) if qualified_record_titles else 'None',
                'sent_to_llm_record_titles': ', '.join(sent_to_llm_record_titles) if sent_to_llm_record_titles else 'None',
                'used_in_answer_record_titles': ', '.join(used_in_answer_record_titles) if used_in_answer_record_titles else 'None',
                'error_message': error_message
            }
            
            return results
            
        except Exception as e:
            print(f"❌ Error evaluating sample {index}: {str(e)}")
            return {
                'index': index,
                'query': query,
                'error': str(e)
            }
    
    async def evaluate_comprehensive(self, queries: List[str], search_responses: List[Dict]) -> pd.DataFrame:
        """
        Evaluate all samples comprehensively using async batching.
        First extracts basic data, then calculates relevance separately.
        
        Args:
            queries: List of queries
            search_responses: List of search API responses
            
        Returns:
            DataFrame with evaluation results
        """
        print(f"🔍 Evaluating {len(queries)} samples with async batching...")
        
        # Prepare output file path (use single file for all results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"outputs/retrieval_benchmark_{timestamp}.xlsx"
        print(f"💾 All results will be saved to: {output_file}")
        
        # Step 1: Extract basic data (query, answer, chunks) without relevance calculation
        print("📊 Step 1: Extracting basic data...")
        basic_results = []
        
        for i, (query, response) in enumerate(zip(queries, search_responses)):
            try:
                # Extract data from response using helper function
                response_data = self.extract_response_data(response)
                answer = response_data['answer']
                error_message = response_data['error_message']
                chunk_results = response_data['chunk_results']
                
                # Analyze chunk usage patterns
                chunk_analysis = self.analyze_chunk_usage_patterns(chunk_results)
                
                # Extract unique record titles for each category
                qualified_record_titles = []
                sent_to_llm_record_titles = []
                used_in_answer_record_titles = []
                
                for record_title, record_data in chunk_analysis['source_breakdown'].items():
                    if record_data.get('qualified', 0) > 0:
                        qualified_record_titles.append(record_title)
                    if record_data.get('sent_to_llm', 0) > 0:
                        sent_to_llm_record_titles.append(record_title)
                    if record_data.get('used_in_answer', 0) > 0:
                        used_in_answer_record_titles.append(record_title)
                
                # Store basic results
                basic_results.append({
                    'query': query,
                    'answer': answer,
                    'qualified_chunks': chunk_analysis['qualified_chunks'],
                    'sent_to_llm': chunk_analysis['sent_to_llm'],
                    'used_in_answer': chunk_analysis['used_in_answer'],
                    'qualified_record_titles': ', '.join(qualified_record_titles) if qualified_record_titles else 'None',
                    'sent_to_llm_record_titles': ', '.join(sent_to_llm_record_titles) if sent_to_llm_record_titles else 'None',
                    'used_in_answer_record_titles': ', '.join(used_in_answer_record_titles) if used_in_answer_record_titles else 'None',
                    'error_message': error_message,
                    'chunk_results': chunk_results  # Store for later relevance calculation
                })
                
            except Exception as e:
                print(f"❌ Error extracting basic data for sample {i}: {str(e)}")
                basic_results.append({
                    'query': query,
                    'error': str(e)
                })
        
        # Step 2: Calculate comprehensive relevance scores using 0-5 scale from prompts.json
        print("🎯 Step 2: Calculating comprehensive relevance scores (0-5 scale)...")
        
        # Create tasks for comprehensive relevance calculation
        relevance_tasks = []
        for i, result in enumerate(basic_results):
            if 'error' not in result and 'chunk_results' in result:
                # Relevance evaluation task using prompts.json format
                relevance_task = self.calculate_comprehensive_relevance_with_semaphore(
                    result['query'], 
                    result['answer'], 
                    result['chunk_results']
                )
                relevance_tasks.append((i, relevance_task))
        
        # Process relevance tasks in batches - read from config
        config = ConfigManager().get_config()
        max_concurrent_evaluation = config.get("max_concurrent_requests_for_evaluation", 5)
        batch_size = min(self.max_concurrent, max_concurrent_evaluation)
        print(f"📊 Using batch size of {batch_size} (from config: max_concurrent_requests_for_evaluation={max_concurrent_evaluation})")
        relevance_scores = {}
        
        # Process comprehensive relevance tasks
        for i in range(0, len(relevance_tasks), batch_size):
            batch_tasks = relevance_tasks[i:i + batch_size]
            batch_start = i + 1
            batch_end = min(i + batch_size, len(relevance_tasks))
            
            print(f"🔄 Processing relevance evaluation batch {batch_start}-{batch_end} of {len(relevance_tasks)} (0-5 scale)")
            
            # Execute batch concurrently
            batch_results = await asyncio.gather(*[task for _, task in batch_tasks], return_exceptions=True)
            
            # Process batch results
            for j, (index, _) in enumerate(batch_tasks):
                result = batch_results[j]
                if isinstance(result, Exception):
                    print(f"❌ Error calculating relevance for sample {index}: {result}")
                    relevance_scores[index] = {
                        'context_relevance_score': 0.0,
                        'answer_relevance_score': 0.0,
                        'context_relevance_explanation': f'Failed to calculate context relevance: {str(result)}',
                        'answer_relevance_explanation': f'Failed to calculate answer relevance: {str(result)}'
                    }
                else:
                    relevance_scores[index] = result
            
            # Print batch summary
            batch_scores = [relevance_scores.get(idx, {}).get('context_relevance_score', 0) for idx in range(i, min(i + batch_size, len(relevance_tasks)))]
            batch_answer_scores = [relevance_scores.get(idx, {}).get('answer_relevance_score', 0) for idx in range(i, min(i + batch_size, len(relevance_tasks)))]
            
            avg_context_score = sum(batch_scores) / len(batch_scores) if batch_scores else 0
            avg_answer_score = sum(batch_answer_scores) / len(batch_answer_scores) if batch_answer_scores else 0
            
            print(f"✅ Relevance evaluation batch {batch_start}-{batch_end} completed")
            print(f"📊 Batch Summary - Avg Context Relevance: {avg_context_score:.3f}, Avg Answer Relevance: {avg_answer_score:.3f}")
            
            # Small delay between batches
            if i + batch_size < len(relevance_tasks):
                await asyncio.sleep(1)
        
        # Step 3: Combine basic data with relevance scores and save final results
        print("🔗 Step 3: Combining results and saving final results...")
        final_results = []
        
        for i, result in enumerate(basic_results):
            if 'error' in result:
                final_results.append(result)
            else:
                # Add comprehensive relevance scores if available
                if i in relevance_scores:
                    result['answer_relevance_score'] = relevance_scores[i]['answer_relevance_score']
                    result['context_relevance_score'] = relevance_scores[i]['context_relevance_score']
                    result['context_relevance_explanation'] = relevance_scores[i].get('context_relevance_explanation', '')
                    result['answer_relevance_explanation'] = relevance_scores[i].get('answer_relevance_explanation', '')
                    result['evaluation_status'] = 'success'
                else:
                    result['answer_relevance_score'] = 0.0
                    result['context_relevance_score'] = 0.0
                    result['context_relevance_explanation'] = 'Failed to calculate context relevance'
                    result['answer_relevance_explanation'] = 'Failed to calculate answer relevance'
                    result['evaluation_status'] = 'failed'
                
                # Remove chunk_results from final output
                if 'chunk_results' in result:
                    del result['chunk_results']
                
                final_results.append(result)
        
        # Convert to DataFrame
        df = pd.DataFrame(final_results)
        
        # Format DataFrame columns
        df = self._format_dataframe_columns(df)
        
        # Save final results to file (only save once at the end)
        with pd.ExcelWriter(output_file, engine='openpyxl', mode='w') as writer:
            df.to_excel(writer, sheet_name='Final_Results', index=False)
        
        print(f"💾 Final results saved to: {output_file}")
        
        return df, output_file
    
    async def evaluate_comprehensive_terminal(self, queries: List[str], search_responses: List[Dict]) -> Tuple[pd.DataFrame, str]:
        """
        Evaluate all samples comprehensively using async batching for terminal output.
        Similar to evaluate_comprehensive but doesn't save to Excel file.
        
        Args:
            queries: List of queries
            search_responses: List of search API responses
            
        Returns:
            DataFrame with evaluation results and dummy output file path
        """
        print(f"🔍 Evaluating {len(queries)} samples with async batching (terminal output)...")
        
        # Step 1: Extract basic data (query, answer, chunks) without relevance calculation
        print("📊 Step 1: Extracting basic data...")
        basic_results = []
        
        for i, (query, response) in enumerate(zip(queries, search_responses)):
            try:
                # Extract data from response using helper function
                response_data = self.extract_response_data(response)
                answer = response_data['answer']
                error_message = response_data['error_message']
                chunk_results = response_data['chunk_results']
                
                # Analyze chunk usage patterns
                chunk_analysis = self.analyze_chunk_usage_patterns(chunk_results)
                
                # Extract unique record titles for each category
                qualified_record_titles = []
                sent_to_llm_record_titles = []
                used_in_answer_record_titles = []
                
                for record_title, record_data in chunk_analysis['source_breakdown'].items():
                    if record_data.get('qualified', 0) > 0:
                        qualified_record_titles.append(record_title)
                    if record_data.get('sent_to_llm', 0) > 0:
                        sent_to_llm_record_titles.append(record_title)
                    if record_data.get('used_in_answer', 0) > 0:
                        used_in_answer_record_titles.append(record_title)
                
                # Store basic results
                basic_results.append({
                    'query': query,
                    'answer': answer,
                    'qualified_chunks': chunk_analysis['qualified_chunks'],
                    'sent_to_llm': chunk_analysis['sent_to_llm'],
                    'used_in_answer': chunk_analysis['used_in_answer'],
                    'qualified_record_titles': ', '.join(qualified_record_titles) if qualified_record_titles else 'None',
                    'sent_to_llm_record_titles': ', '.join(sent_to_llm_record_titles) if sent_to_llm_record_titles else 'None',
                    'used_in_answer_record_titles': ', '.join(used_in_answer_record_titles) if used_in_answer_record_titles else 'None',
                    'error_message': error_message,
                    'chunk_results': chunk_results  # Store for later relevance calculation
                })
                
            except Exception as e:
                print(f"❌ Error extracting basic data for sample {i}: {str(e)}")
                basic_results.append({
                    'query': query,
                    'error': str(e)
                })
        
        # Step 2: Calculate comprehensive relevance scores using 0-5 scale from prompts.json
        print("🎯 Step 2: Calculating comprehensive relevance scores (0-5 scale)...")
        
        # Create tasks for comprehensive relevance calculation
        relevance_tasks = []
        for i, result in enumerate(basic_results):
            if 'error' not in result and 'chunk_results' in result:
                # Relevance evaluation task using prompts.json format
                relevance_task = self.calculate_comprehensive_relevance_with_semaphore(
                    result['query'], 
                    result['answer'], 
                    result['chunk_results']
                )
                relevance_tasks.append((i, relevance_task))
        
        # Process relevance tasks in batches - read from config
        config = ConfigManager().get_config()
        max_concurrent_evaluation = config.get("max_concurrent_requests_for_evaluation", 5)
        batch_size = min(self.max_concurrent, max_concurrent_evaluation)
        print(f"📊 Using batch size of {batch_size} (from config: max_concurrent_requests_for_evaluation={max_concurrent_evaluation})")
        relevance_scores = {}
        
        # Process comprehensive relevance tasks
        for i in range(0, len(relevance_tasks), batch_size):
            batch_tasks = relevance_tasks[i:i + batch_size]
            batch_start = i + 1
            batch_end = min(i + batch_size, len(relevance_tasks))
            
            print(f"🔄 Processing relevance evaluation batch {batch_start}-{batch_end} of {len(relevance_tasks)} (0-5 scale)")
            
            # Execute batch concurrently
            batch_results = await asyncio.gather(*[task for _, task in batch_tasks], return_exceptions=True)
            
            # Process batch results
            for j, (index, _) in enumerate(batch_tasks):
                result = batch_results[j]
                if isinstance(result, Exception):
                    print(f"❌ Error calculating relevance for sample {index}: {result}")
                    relevance_scores[index] = {
                        'context_relevance_score': 0.0,
                        'answer_relevance_score': 0.0,
                        'context_relevance_explanation': f'Failed to calculate context relevance: {str(result)}',
                        'answer_relevance_explanation': f'Failed to calculate answer relevance: {str(result)}'
                    }
                else:
                    relevance_scores[index] = result
            
            # Print batch summary
            batch_scores = [relevance_scores.get(idx, {}).get('context_relevance_score', 0) for idx in range(i, min(i + batch_size, len(relevance_tasks)))]
            batch_answer_scores = [relevance_scores.get(idx, {}).get('answer_relevance_score', 0) for idx in range(i, min(i + batch_size, len(relevance_tasks)))]
            
            avg_context_score = sum(batch_scores) / len(batch_scores) if batch_scores else 0
            avg_answer_score = sum(batch_answer_scores) / len(batch_answer_scores) if batch_answer_scores else 0
            
            print(f"✅ Relevance evaluation batch {batch_start}-{batch_end} completed")
            print(f"📊 Batch Summary - Avg Context Relevance: {avg_context_score:.3f}, Avg Answer Relevance: {avg_answer_score:.3f}")
            
            # Small delay between batches
            if i + batch_size < len(relevance_tasks):
                await asyncio.sleep(1)
        
        # Step 3: Combine basic data with relevance scores
        print("🔗 Step 3: Combining results...")
        final_results = []
        
        for i, result in enumerate(basic_results):
            if 'error' in result:
                final_results.append(result)
            else:
                    # Add comprehensive relevance scores if available
                if i in relevance_scores:
                    result['answer_relevance_score'] = relevance_scores[i]['answer_relevance_score']
                    result['context_relevance_score'] = relevance_scores[i]['context_relevance_score']
                    result['context_relevance_explanation'] = relevance_scores[i].get('context_relevance_explanation', '')
                    result['answer_relevance_explanation'] = relevance_scores[i].get('answer_relevance_explanation', '')
                    result['evaluation_status'] = 'success'
                else:
                    result['answer_relevance_score'] = 0.0
                    result['context_relevance_score'] = 0.0
                    result['context_relevance_explanation'] = 'Failed to calculate context relevance'
                    result['answer_relevance_explanation'] = 'Failed to calculate answer relevance'
                    result['evaluation_status'] = 'failed'
                
                # Remove chunk_results from final output
                if 'chunk_results' in result:
                    del result['chunk_results']
                    
                final_results.append(result)
            
            # Convert to DataFrame
        df = pd.DataFrame(final_results)
            
            # Format DataFrame columns
        df = self._format_dataframe_columns(df)
            
        print(f"✅ Evaluation completed - results ready for terminal display")
        
        return df, "terminal_output"
    
    async def evaluate_comprehensive_with_overlap(self, queries: List[str], search_responses: List[Dict], 
                                                json_data: List[Tuple]) -> Tuple[pd.DataFrame, str]:
        """
        Evaluate all samples comprehensively with chunk overlap analysis for JSON input.
        
        Args:
            queries: List of queries
            search_responses: List of search API responses
            json_data: List of tuples (query, response, json_item) with original chunk data
            
        Returns:
            DataFrame with evaluation results and output file path
        """
        print(f"🔍 Evaluating {len(queries)} samples with chunk overlap analysis...")
        
        # Prepare output file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"outputs/retrieval_benchmark_with_overlap_{timestamp}.xlsx"
        print(f"💾 All results will be saved to: {output_file}")
        
        # Step 1: Extract basic data and chunk overlap
        print("📊 Step 1: Extracting basic data and chunk overlap...")
        basic_results = []
        
        for i, (query, response, json_item) in enumerate(json_data):
            try:
                # Extract data from response using helper function
                response_data = self.extract_response_data(response)
                answer = response_data['answer']
                error_message = response_data['error_message']
                chunk_results = response_data['chunk_results']
                
                # Analyze chunk usage patterns
                chunk_analysis = self.analyze_chunk_usage_patterns(chunk_results)
                
                # Extract unique record titles for each category
                qualified_record_titles = []
                sent_to_llm_record_titles = []
                used_in_answer_record_titles = []
                
                for record_title, record_data in chunk_analysis['source_breakdown'].items():
                    if record_data.get('qualified', 0) > 0:
                        qualified_record_titles.append(record_title)
                    if record_data.get('sent_to_llm', 0) > 0:
                        sent_to_llm_record_titles.append(record_title)
                    if record_data.get('used_in_answer', 0) > 0:
                        used_in_answer_record_titles.append(record_title)
                
                # Get original chunk texts from JSON data
                original_chunk_texts = json_item.get('original_chunk_texts', [])
                
                # Evaluate chunk overlap
                overlap_evaluation = self.evaluate_chunk_overlap(chunk_results, original_chunk_texts)
                
                # Store basic results
                basic_results.append({
                    'query': query,
                    'answer': answer,
                    'qualified_chunks': chunk_analysis['qualified_chunks'],
                    'sent_to_llm': chunk_analysis['sent_to_llm'],
                    'used_in_answer': chunk_analysis['used_in_answer'],
                    'qualified_record_titles': ', '.join(qualified_record_titles) if qualified_record_titles else 'None',
                    'sent_to_llm_record_titles': ', '.join(sent_to_llm_record_titles) if sent_to_llm_record_titles else 'None',
                    'used_in_answer_record_titles': ', '.join(used_in_answer_record_titles) if used_in_answer_record_titles else 'None',
                    'error_message': error_message,
                    'chunk_results': chunk_results,  # Store for later relevance calculation
                    # Chunk overlap metrics
                    'chunk_overlap_score': overlap_evaluation['chunk_overlap_score'],
                    'chunks_retrieved': overlap_evaluation['chunks_retrieved'],
                    'chunks_original': overlap_evaluation['chunks_original'],
                    'overlapping_chunks': overlap_evaluation['overlapping_chunks'],
                    'overlap_percentage': overlap_evaluation['overlap_percentage'],
                    'overlap_explanation': overlap_evaluation['overlap_explanation']
                })
            
            except Exception as e:
                print(f"❌ Error extracting basic data for sample {i}: {str(e)}")
                basic_results.append({
                    'query': query,
                    'error': str(e)
                })
        
        # Step 2: Calculate context relevance based on chunk overlap
        print("🎯 Step 2: Calculating context relevance based on chunk overlap...")
        
        # For JSON input, we calculate context relevance based on chunk overlap
        # Context relevance = how many chunks used to generate query are found in retrieved results
        for i, result in enumerate(basic_results):
            if 'error' not in result:
                # Use the chunk overlap score as context relevance
                chunk_overlap_score = result.get('chunk_overlap_score', 0.0)
                context_relevance_score = chunk_overlap_score
                
                # Get explanation from overlap evaluation
                overlap_explanation = result.get('overlap_explanation', 'Chunk overlap evaluation')
                context_explanation = f"Context relevance based on chunk overlap: {overlap_explanation}"
                
                # Debug output
                query = result.get('query', 'Unknown')
                overlapping_chunks = result.get('overlapping_chunks', 0)
                chunks_original = result.get('chunks_original', 0)
                print(f"📊 Query {i+1}: '{query[:50]}...' - Overlap: {overlapping_chunks}/{chunks_original} chunks found (Score: {chunk_overlap_score:.3f})")
                
                # Set the scores
                result['context_relevance_score'] = context_relevance_score
                result['answer_relevance_score'] = 0.0  # Not calculated for chunk-based evaluation
                result['context_relevance_explanation'] = context_explanation
                result['answer_relevance_explanation'] = 'Not calculated for chunk-based evaluation'
                result['evaluation_status'] = 'success'
        
        # Step 3: Combine results and save final results
        print("🔗 Step 3: Combining results and saving final results...")
        final_results = []
        
        for i, result in enumerate(basic_results):
            if 'error' in result:
                final_results.append(result)
            else:
                # For chunk-based evaluation, scores are already set in Step 2
                # No need to reference relevance_scores since we're not using LLM evaluation
                result['evaluation_status'] = 'success'
                
                # Remove chunk_results from final output
                if 'chunk_results' in result:
                    del result['chunk_results']
                
                final_results.append(result)
        
        # Convert to DataFrame
        df = pd.DataFrame(final_results)
        
        # Format DataFrame columns
        df = self._format_dataframe_columns_with_overlap(df)
        
        # Save final results to file
        with pd.ExcelWriter(output_file, engine='openpyxl', mode='w') as writer:
            df.to_excel(writer, sheet_name='Final_Results', index=False)
        
        print(f"💾 Final results saved to: {output_file}")
        
        return df, output_file
    
    async def evaluate_comprehensive_terminal_with_overlap(self, queries: List[str], search_responses: List[Dict], 
                                                        json_data: List[Tuple]) -> Tuple[pd.DataFrame, str]:
        """
        Evaluate all samples comprehensively with chunk overlap analysis for terminal output.
        
        Args:
            queries: List of queries
            search_responses: List of search API responses
            json_data: List of tuples (query, response, json_item) with original chunk data
            
        Returns:
            DataFrame with evaluation results and dummy output file path
        """
        print(f"🔍 Evaluating {len(queries)} samples with chunk overlap analysis (terminal output)...")
        
        # Step 1: Extract basic data and chunk overlap
        print("📊 Step 1: Extracting basic data and chunk overlap...")
        basic_results = []
        
        for i, (query, response, json_item) in enumerate(json_data):
            try:
                # Extract data from response using helper function
                response_data = self.extract_response_data(response)
                answer = response_data['answer']
                error_message = response_data['error_message']
                chunk_results = response_data['chunk_results']
                
                # Analyze chunk usage patterns
                chunk_analysis = self.analyze_chunk_usage_patterns(chunk_results)
                
                # Extract unique record titles for each category
                qualified_record_titles = []
                sent_to_llm_record_titles = []
                used_in_answer_record_titles = []
                
                for record_title, record_data in chunk_analysis['source_breakdown'].items():
                    if record_data.get('qualified', 0) > 0:
                        qualified_record_titles.append(record_title)
                    if record_data.get('sent_to_llm', 0) > 0:
                        sent_to_llm_record_titles.append(record_title)
                    if record_data.get('used_in_answer', 0) > 0:
                        used_in_answer_record_titles.append(record_title)
                
                # Get original chunk texts from JSON data
                original_chunk_texts = json_item.get('original_chunk_texts', [])
                
                # Evaluate chunk overlap
                overlap_evaluation = self.evaluate_chunk_overlap(chunk_results, original_chunk_texts)
                
                # Store basic results
                basic_results.append({
                    'query': query,
                    'answer': answer,
                    'qualified_chunks': chunk_analysis['qualified_chunks'],
                    'sent_to_llm': chunk_analysis['sent_to_llm'],
                    'used_in_answer': chunk_analysis['used_in_answer'],
                    'qualified_record_titles': ', '.join(qualified_record_titles) if qualified_record_titles else 'None',
                    'sent_to_llm_record_titles': ', '.join(sent_to_llm_record_titles) if sent_to_llm_record_titles else 'None',
                    'used_in_answer_record_titles': ', '.join(used_in_answer_record_titles) if used_in_answer_record_titles else 'None',
                    'error_message': error_message,
                    'chunk_results': chunk_results,  # Store for later relevance calculation
                    # Chunk overlap metrics
                    'chunk_overlap_score': overlap_evaluation['chunk_overlap_score'],
                    'chunks_retrieved': overlap_evaluation['chunks_retrieved'],
                    'chunks_original': overlap_evaluation['chunks_original'],
                    'overlapping_chunks': overlap_evaluation['overlapping_chunks'],
                    'overlap_percentage': overlap_evaluation['overlap_percentage'],
                    'overlap_explanation': overlap_evaluation['overlap_explanation']
                })
                
            except Exception as e:
                print(f"❌ Error extracting basic data for sample {i}: {str(e)}")
                basic_results.append({
                    'query': query,
                    'error': str(e)
                })
        
        # Step 2: Calculate context relevance based on chunk overlap
        print("🎯 Step 2: Calculating context relevance based on chunk overlap...")
        
        # For JSON input, we calculate context relevance based on chunk overlap
        # Context relevance = how many chunks used to generate query are found in retrieved results
        for i, result in enumerate(basic_results):
            if 'error' not in result:
                # Use the chunk overlap score as context relevance
                chunk_overlap_score = result.get('chunk_overlap_score', 0.0)
                context_relevance_score = chunk_overlap_score
                
                # Get explanation from overlap evaluation
                overlap_explanation = result.get('overlap_explanation', 'Chunk overlap evaluation')
                context_explanation = f"Context relevance based on chunk overlap: {overlap_explanation}"
                
                # Debug output
                query = result.get('query', 'Unknown')
                overlapping_chunks = result.get('overlapping_chunks', 0)
                chunks_original = result.get('chunks_original', 0)
                print(f"📊 Query {i+1}: '{query[:50]}...' - Overlap: {overlapping_chunks}/{chunks_original} chunks found (Score: {chunk_overlap_score:.3f})")
                
                # Set the scores
                result['context_relevance_score'] = context_relevance_score
                result['answer_relevance_score'] = 0.0  # Not calculated for chunk-based evaluation
                result['context_relevance_explanation'] = context_explanation
                result['answer_relevance_explanation'] = 'Not calculated for chunk-based evaluation'
                result['evaluation_status'] = 'success'
        
        # Step 3: Combine results and save final results
        print("🔗 Step 3: Combining results and saving final results...")
        final_results = []
        
        for i, result in enumerate(basic_results):
            if 'error' in result:
                final_results.append(result)
            else:
                # For chunk-based evaluation, scores are already set in Step 2
                # No need to reference relevance_scores since we're not using LLM evaluation
                result['evaluation_status'] = 'success'
                
                # Remove chunk_results from final output
                if 'chunk_results' in result:
                    del result['chunk_results']
                
                final_results.append(result)
        
        # Convert to DataFrame
        df = pd.DataFrame(final_results)
        
        # Format DataFrame columns
        df = self._format_dataframe_columns_with_overlap(df)
        
        print(f"✅ Evaluation completed - results ready for terminal display")
        
        return df, "terminal_output"
            

    
    async def calculate_comprehensive_relevance_with_semaphore(self, query: str, answer: str, chunk_results: List[Dict]) -> Dict:
        """
        Calculate relevance score using prompts.json format with semaphore control.
        
        Args:
            query: User query
            answer: Generated answer
            chunk_results: List of chunk results
            
        Returns:
            Dictionary with relevance scores (0-5 scale normalized to 0-1)
        """
        async with self.semaphore:
            return self.evaluate_comprehensive_relevance(query, answer, chunk_results)
    
    async def evaluate_single_sample_with_semaphore(self, index: int, query: str, search_response: Dict) -> Dict:
        """
        Evaluate a single sample with semaphore control for API rate limiting.
        
        Args:
            index: Sample index
            query: User query
            search_response: Full search API response
            
        Returns:
            Dictionary with evaluation results
        """
        async with self.semaphore:
            return await self.evaluate_single_sample(index, query, search_response)
    
    def _format_dataframe_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Format DataFrame columns for better readability.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Formatted DataFrame
        """
        # Safely round numeric columns
        numeric_columns = ['answer_relevance_score', 'context_relevance_score']
        for col in numeric_columns:
            if col in df.columns:
                try:
                    # Convert to numeric first, then round
                    numeric_series = pd.to_numeric(df[col], errors='coerce')
                    df[col] = numeric_series.round(4).fillna(0.0)
                except Exception as e:
                    print(f"Warning: Could not round column {col}: {e}")
                    # Keep original values if rounding fails
                    pass
        
        # Ensure proper column order
        column_order = [
            'query', 'answer', 'answer_relevance_score', 'context_relevance_score', 'qualified_chunks', 
            'sent_to_llm', 'used_in_answer', 
            'qualified_record_titles', 'sent_to_llm_record_titles', 'used_in_answer_record_titles',
            'context_relevance_explanation', 'answer_relevance_explanation', 'evaluation_status', 'error_message'
        ]
        
        # Add any missing columns at the end
        existing_columns = [col for col in column_order if col in df.columns]
        remaining_columns = [col for col in df.columns if col not in column_order]
        final_order = existing_columns + remaining_columns
        
        return df[final_order]
    
    def _format_dataframe_columns_with_overlap(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Format DataFrame columns for better readability with chunk overlap metrics.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Formatted DataFrame
        """
        # Safely round numeric columns
        numeric_columns = ['answer_relevance_score', 'context_relevance_score', 'chunk_overlap_score', 
                          'chunks_retrieved', 'chunks_original', 'overlapping_chunks', 'overlap_percentage']
        for col in numeric_columns:
            if col in df.columns:
                try:
                    # Convert to numeric first, then round
                    numeric_series = pd.to_numeric(df[col], errors='coerce')
                    if col in ['chunk_overlap_score', 'overlap_percentage']:
                        df[col] = numeric_series.round(4).fillna(0.0)
                    else:
                        df[col] = numeric_series.round(2).fillna(0.0)
                except Exception as e:
                    print(f"Warning: Could not round column {col}: {e}")
                    # Keep original values if rounding fails
                    pass
        
        # Ensure proper column order
        column_order = [
            'query', 'answer', 'answer_relevance_score', 'context_relevance_score', 'chunk_overlap_score',
            'qualified_chunks', 'sent_to_llm', 'used_in_answer', 
            'chunks_retrieved', 'chunks_original', 'overlapping_chunks', 'overlap_percentage',
            'qualified_record_titles', 'sent_to_llm_record_titles', 'used_in_answer_record_titles',
            'context_relevance_explanation', 'answer_relevance_explanation', 'overlap_explanation',
            'evaluation_status', 'error_message'
        ]
        
        # Add any missing columns at the end
        existing_columns = [col for col in column_order if col in df.columns]
        remaining_columns = [col for col in df.columns if col not in column_order]
        final_order = existing_columns + remaining_columns
        
        return df[final_order]
    
    def evaluate(self, queries: List[str], answers: List[str], 
                ground_truths: List[str], contexts: List[str]) -> pd.DataFrame:
        """
        Evaluate queries using the retrieval benchmark approach.
        
        Args:
            queries: List of queries
            answers: List of answers (not used in retrieval benchmark)
            ground_truths: List of ground truths (not used in retrieval benchmark)
            contexts: List of contexts (not used in retrieval benchmark)
            
        Returns:
            DataFrame with evaluation results
        """
        # For retrieval benchmark, we fetch data from Search API
        # This method is required by the base class but not used
        # The actual evaluation is done in evaluate_comprehensive
        return pd.DataFrame()
    
    def process_results(self, results: pd.DataFrame) -> Dict:
        """
        Process evaluation results and generate summary statistics.
        
        Args:
            results: DataFrame with evaluation results
            
        Returns:
            Dictionary with summary statistics
        """
        # Check if DataFrame is empty
        if results.empty:
            print("Warning: Empty DataFrame provided to process_results")
            return {
                'total_samples': 0,
                'avg_qualified_chunks': 0.0,
                'avg_sent_to_llm': 0.0,
                'avg_used_in_answer': 0.0,
                'avg_answer_relevance': 0.0,
                'utilization_rate': 0.0,
                'avg_context_relevance': 0.0
            }
        
        # Convert numeric columns to proper types, handling errors
        def safe_numeric_conversion(series, default=0.0):
            try:
                # Convert to numeric, coercing errors to NaN
                numeric_series = pd.to_numeric(series, errors='coerce')
                # Fill NaN with default value
                return numeric_series.fillna(default)
            except Exception as e:
                print(f"Warning: Error converting series to numeric: {e}")
                print(f"Series sample: {series.head() if len(series) > 0 else 'Empty series'}")
                return pd.Series([default] * len(series))
        
        # Convert numeric columns safely
        qualified_chunks = safe_numeric_conversion(results['qualified_chunks'])
        sent_to_llm = safe_numeric_conversion(results['sent_to_llm'])
        used_in_answer = safe_numeric_conversion(results['used_in_answer'])
        answer_relevance = safe_numeric_conversion(results['answer_relevance_score'])
        context_relevance = safe_numeric_conversion(results['context_relevance_score'])
        
        summary = {
            'total_samples': len(results),
            'avg_qualified_chunks': qualified_chunks.mean(),
            'avg_sent_to_llm': sent_to_llm.mean(),
            'avg_used_in_answer': used_in_answer.mean(),
            'avg_answer_relevance': answer_relevance.mean(),
            'utilization_rate': (used_in_answer / sent_to_llm).mean() if sent_to_llm.sum() > 0 else 0,
            'avg_context_relevance': context_relevance.mean()
        }
        
        return summary
    
    def generate_summary_report(self, results_df: pd.DataFrame) -> Dict:
        """
        Generate a comprehensive summary report.
        
        Args:
            results_df: DataFrame with evaluation results
            
        Returns:
            Dictionary with summary report
        """
        # Check if DataFrame is empty
        if results_df.empty:
            print("Warning: Empty DataFrame provided to generate_summary_report")
            summary = self.process_results(results_df)
            summary['llm_utilization_rate'] = 0.0
            summary['answer_utilization_rate'] = 0.0
            summary['score_distribution'] = {
                'excellent_relevance': 0,
                'good_relevance': 0,
                'fair_relevance': 0,
                'poor_relevance': 0
            }
            return summary
        
        summary = self.process_results(results_df)
        
        # Convert numeric columns safely for additional calculations
        def safe_numeric_conversion(series, default=0.0):
            try:
                numeric_series = pd.to_numeric(series, errors='coerce')
                return numeric_series.fillna(default)
            except Exception as e:
                print(f"Warning: Error converting series to numeric in summary: {e}")
                return pd.Series([default] * len(series))
        
        sent_to_llm = safe_numeric_conversion(results_df['sent_to_llm'])
        qualified_chunks = safe_numeric_conversion(results_df['qualified_chunks'])
        used_in_answer = safe_numeric_conversion(results_df['used_in_answer'])
        answer_relevance = safe_numeric_conversion(results_df['answer_relevance_score'])
        
        # Additional analysis (removed total_chunks dependency)
        summary['llm_utilization_rate'] = (sent_to_llm / qualified_chunks).mean() if qualified_chunks.sum() > 0 else 0
        summary['answer_utilization_rate'] = (used_in_answer / sent_to_llm).mean() if sent_to_llm.sum() > 0 else 0
        
        # Score distributions (based on 0-1 normalized scale)
        summary['score_distribution'] = {
            'excellent_relevance': (answer_relevance >= 0.8).sum(),  # 4-5 on original scale
            'good_relevance': ((answer_relevance >= 0.6) & (answer_relevance < 0.8)).sum(),  # 3-4 on original scale
            'fair_relevance': ((answer_relevance >= 0.4) & (answer_relevance < 0.6)).sum(),  # 2-3 on original scale
            'poor_relevance': (answer_relevance < 0.4).sum()  # 0-2 on original scale
        }
        
        return summary
    
    def attempt_api_call(self, messages: List[Dict]) -> Optional[str]:
        """
        Attempt to make an API call with retry logic.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            API response or None if failed
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
    
                if self.model_type == "azure":
                    response = self.openai_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=0.0,
                        max_tokens=500
                    )
                else:
                    response = self.openai_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=0.0,
                        max_tokens=500
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

    def evaluate_semantic_overlap(self, retrieved_chunks: List[Dict], original_chunks: List[Dict]) -> Dict:
        """
        Evaluate semantic overlap between retrieved chunks and original chunks using embeddings.
        
        Args:
            retrieved_chunks: List of chunks retrieved by the search API
            original_chunks: List of original chunks used to generate the question
            
        Returns:
            Dictionary with semantic overlap metrics
        """
        # This would require embedding comparison
        # For now, return a placeholder implementation
        return {
            'semantic_overlap_score': 0.0,
            'explanation': 'Semantic overlap evaluation requires embedding comparison (not implemented)'
        }

    def evaluate_keyword_overlap(self, retrieved_chunks: List[Dict], original_chunks: List[Dict]) -> Dict:
        """
        Evaluate keyword overlap between retrieved chunks and original chunks.
        
        Args:
            retrieved_chunks: List of chunks retrieved by the search API
            original_chunks: List of original chunks used to generate the question
            
        Returns:
            Dictionary with keyword overlap metrics
        """
        # Extract keywords from original chunks
        original_keywords = set()
        for chunk in original_chunks:
            text = chunk.get('chunkText', '')
            # Simple keyword extraction (first 10 words)
            words = text.split()[:10]
            original_keywords.update([word.lower() for word in words if len(word) > 3])
        
        # Extract keywords from retrieved chunks
        retrieved_keywords = set()
        for chunk in retrieved_chunks:
            text = chunk.get('chunkText', '')
            words = text.split()[:10]
            retrieved_keywords.update([word.lower() for word in words if len(word) > 3])
        
        # Calculate overlap
        overlapping_keywords = original_keywords.intersection(retrieved_keywords)
        overlap_count = len(overlapping_keywords)
        total_original = len(original_keywords)
        
        if total_original == 0:
            keyword_overlap_score = 0.0
        else:
            keyword_overlap_score = overlap_count / total_original
        
        return {
            'keyword_overlap_score': keyword_overlap_score,
            'original_keywords': len(original_keywords),
            'retrieved_keywords': len(retrieved_keywords),
            'overlapping_keywords': overlap_count,
            'explanation': f'Keyword overlap: {overlap_count}/{total_original} keywords matched'
        }

    def extract_response_data(self, response: Dict) -> Dict:
        """
        Extract answer, error message, and chunk results from response structure.
        
        Args:
            response: Response dictionary from search API
            
        Returns:
            Dictionary with extracted data
        """
        answer = ""
        error_message = ""
        chunk_results = []
        
        # Get API version from config
        search_api_config = self.config.get('search_api', {})
        api_version = search_api_config.get('version', 'v2')
        
        if api_version == "v2":
            # Handle v2 format (template.answer_details.response.answer)
            if 'template' in response and 'answer_details' in response['template']:
                answer_details = response['template']['answer_details']
                
                # Extract answer
                if 'response' in answer_details and 'answer' in answer_details['response']:
                    answer = answer_details['response']['answer']
                
                # Extract error message
                if 'errMsg' in answer_details:
                    error_message = answer_details['errMsg']
            
            # Extract chunk results
            chunk_results = response.get('template', {}).get('chunk_result', [])
        else:
            # Handle v1 format (response.answer_payload.center_panel)
            if 'response' in response:
                # Extract answer from center_panel
                center_panel = (response.get('response', {})
                                .get('answer_payload', {})
                                .get('center_panel', {}))
                if center_panel:
                    snippet_content = center_panel.get('data', [{}])[0].get('snippet_content', [{}])
                    answer = " ".join(content.get('answer_fragment', "No Answer Found") for content in snippet_content) if snippet_content else "No Answer Found"
                
                # Extract error message
                if 'errMsg' in response['response']:
                    error_message = response['response']['errMsg']
            
            # Extract chunk results
            chunk_results = response.get('chunk_result', {}).get('generative', [])
        
        return {
            'answer': answer,
            'error_message': error_message,
            'chunk_results': chunk_results
        }




def setup_openai_client(model: str = "azure"):
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


def get_model_name(model: str = "openai"):
    """
    Get model name based on model choice.
    
    Args:
        model: Model choice (openai or azure)
        
    Returns:
        Model name
    """
    config = ConfigManager().get_config()
    
    if model == "azure":
        return config.get('azure', {}).get('model_deployment', 'searchassist-gpt-4o-mini-2024-07-18')
    else:
        return config.get('openai', {}).get('model_name', 'gpt-4o-mini')


async def fetch_data_from_search_api(queries: List[str]) -> List[Dict]:
    """
    Fetch data from Search API for given queries.
    
    Args:
        queries: List of queries
        
    Returns:
        List of search API responses
    """
    print("🔍 Fetching data from Search API...")
    
    # Fetch responses for all queries using the simple function
    # Read concurrency from config
    config = ConfigManager().get_config()
    max_concurrent_search = config.get("max_concurrent_requests_for_search_api", 2)
    search_responses = await call_search_api_async_simple(queries, api_type='UXO', max_concurrent=max_concurrent_search)
    
    return search_responses


def load_data_from_json(file_path: str) -> List[Dict]:
    """
    Load questions and chunks from JSON file for retrieval benchmark analysis.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        List of dictionaries with query, chunks, and used_chunk_ids
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📊 Loaded {len(data)} questions from {file_path}")
        return data
        
    except Exception as e:
        print(f"❌ Error loading data from JSON file: {str(e)}")
        raise


def load_data_from_excel(file_path: str, sheet_name: str = None) -> List[str]:
    """
    Load queries from Excel file for retrieval benchmark analysis.
    
    Args:
        file_path: Path to Excel file
        sheet_name: Sheet name to load (optional)
        
    Returns:
        List of queries
    """
    try:
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
        else:
            df = pd.read_excel(file_path, engine='openpyxl')
        
        # Handle different column name variations for queries
        query_col = None
        for col in ['query', 'user_input', 'question', 'Question']:
            if col in df.columns:
                query_col = col
                break
        
        if not query_col:
            raise ValueError("Missing required column: query/user_input/question")
        
        queries = df[query_col].fillna('').tolist()
        
        print(f"📊 Loaded {len(queries)} queries from {file_path}")
        return queries
        
    except Exception as e:
        print(f"❌ Error loading data from Excel file: {str(e)}")
        raise


def print_summary_report(summary: Dict):
    """
    Print a formatted summary report.
    
    Args:
        summary: Summary dictionary from evaluation
    """
    print("\n" + "="*80)
    print("📊 RETRIEVAL BENCHMARK SUMMARY")
    print("="*80)
    
    print(f"📈 Total Samples Evaluated: {summary['total_samples']}")
    print(f"✅ Average Qualified Chunks: {summary['avg_qualified_chunks']:.2f}")
    print(f"🤖 Average Sent to LLM: {summary['avg_sent_to_llm']:.2f}")
    print(f"💡 Average Used in Answer: {summary['avg_used_in_answer']:.2f}")
    print(f"🎯 Average Answer Relevance: {summary['avg_answer_relevance']:.4f}")
    
    print(f"\n📋 Utilization Rates:")
    print(f"   LLM Utilization Rate: {summary['llm_utilization_rate']:.2%}")
    print(f"   Answer Utilization Rate: {summary['answer_utilization_rate']:.2%}")
    
    print(f"\n🎯 Context Relevance Analysis:")
    print(f"   Context Relevance: {summary['avg_context_relevance']:.4f}")
    
    print(f"\n📊 Answer Relevance Distribution (0-5 scale normalized to 0-1):")
    print(f"   Excellent (≥0.8, original 4-5): {summary['score_distribution']['excellent_relevance']}")
    print(f"   Good (0.6-0.8, original 3-4): {summary['score_distribution']['good_relevance']}")
    print(f"   Fair (0.4-0.6, original 2-3): {summary['score_distribution']['fair_relevance']}")
    print(f"   Poor (<0.4, original 0-2): {summary['score_distribution']['poor_relevance']}")
    
    print("="*80)


def ensure_outputs_directory():
    """Ensure the outputs directory exists."""
    outputs_dir = "outputs"
    if not os.path.exists(outputs_dir):
        os.makedirs(outputs_dir)
        print("📁 Created outputs directory")


async def main():
    """Main function to handle command line arguments and run evaluation."""
    parser = argparse.ArgumentParser(
        description='Retrieval Benchmark Evaluation Script - Focused on Chunk Analysis and Source Relevance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate all sheets using Search API for retrieval analysis
  python RetrievalBenchmark.py --input data.xlsx --use_search_api
  
  # Evaluate specific sheet using Search API
  python RetrievalBenchmark.py --input data.xlsx --sheet Sheet1 --use_search_api
  
  # Evaluate with custom output file
  python RetrievalBenchmark.py --input data.xlsx --output results.xlsx --use_search_api
  
  # Evaluate with high concurrency
  python RetrievalBenchmark.py --input data.xlsx --use_search_api --concurrency 10
  
  # Evaluate specific questions via command line (terminal output)
  python RetrievalBenchmark.py --questions "What is Python?" "How does machine learning work?" --use_search_api --terminal_output
  
  # Evaluate questions from Excel file with terminal output
  python RetrievalBenchmark.py --input data.xlsx --use_search_api --terminal_output
        """
    )
    
    parser.add_argument('--input', type=str, required=False,
                       help='Path to input Excel file (optional if using --questions or --json_input)')
    parser.add_argument('--json_input', type=str, required=False,
                       help='Path to JSON file with questions and chunks (optional if using --input or --questions)')
    parser.add_argument('--questions', type=str, nargs='+', required=False,
                       help='List of questions to evaluate (e.g., "question1" "question2")')
    parser.add_argument('--sheet', type=str, default=None,
                       help='Sheet name to evaluate (defaults to all sheets)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file path (default: retrieval_benchmark_<timestamp>.xlsx)')
    parser.add_argument('--sample', type=int, default=None,
                       help='Number of samples to evaluate (default: all)')
    parser.add_argument('--use_search_api', action='store_true', required=True,
                       help='Fetch data from Search API (required for retrieval benchmark)')
    parser.add_argument('--concurrency', type=int, default=5,
                       help='Number of concurrent API calls (default: 5)')
    parser.add_argument('--model', type=str, default='openai',
                       choices=['openai', 'azure'],
                       help='Model to use for evaluation (default: openai)')

    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.use_search_api:
        print("❌ Error: --use_search_api is required for retrieval benchmark evaluation")
        sys.exit(1)
    
    # Check if either input file or questions are provided
    if not args.input and not args.questions and not args.json_input:
        print("❌ Error: Either --input (Excel file), --questions (list of questions), or --json_input (JSON file) must be provided")
        sys.exit(1)
    
    if args.input and args.questions:
        print("❌ Error: Please provide either --input OR --questions, not both")
        sys.exit(1)
    
    if args.input and args.json_input:
        print("❌ Error: Please provide either --input OR --json_input, not both")
        sys.exit(1)
    
    if args.json_input and (args.questions or args.sheet):
        print("❌ Error: --json_input cannot be used with --questions or --sheet")
        sys.exit(1)
    
    try:
        # Ensure outputs directory exists
        ensure_outputs_directory()
        
        # Setup OpenAI client
        openai_client = setup_openai_client(args.model)
        model_name = get_model_name(args.model)
        
        # Initialize evaluator
        evaluator = RetrievalBenchmarkEvaluator(model_name, openai_client, args.model, args.concurrency)
        
        # Load queries from either Excel file or command line arguments
        if args.input:
            print(f"📂 Loading queries from {args.input}")
            queries = load_data_from_excel(args.input, args.sheet)
        
        # Apply sampling if specified
        if args.sample:
            queries = queries[:args.sample]
            print(f"📊 Evaluating first {len(queries)} samples")
        elif args.json_input:
            print(f"📂 Loading queries from {args.json_input}")
            data = load_data_from_json(args.json_input)
            
            # Apply sampling if specified
            if args.sample:
                data = data[:args.sample]
                print(f"📊 Evaluating first {len(data)} samples")
            else:
                print(f"📊 Evaluating all {len(data)} samples")
            
            queries = [item['query'] for item in data]
            print(f"📊 Evaluating {len(queries)} questions from JSON file")
        else: # args.questions is not None
            queries = args.questions
            print(f"📊 Evaluating {len(queries)} questions from command line")
        
        # Fetch data from Search API
        search_responses = await fetch_data_from_search_api(queries)
        
        # Filter out empty responses
        valid_data = [(q, r) for q, r in zip(queries, search_responses) if r]
        if not valid_data:
            print("❌ No valid responses received from Search API")
            sys.exit(1)
        
        queries, search_responses = zip(*valid_data)
        print(f"✅ Successfully fetched {len(queries)} valid responses")
        
        # If using JSON input, we have additional chunk overlap evaluation
        if args.json_input:
            # Re-filter data to match valid responses
            valid_json_data = []
            for i, (query, response) in enumerate(zip(queries, search_responses)):
                if response:
                    # Find corresponding JSON data
                    for json_item in data:
                        if json_item['query'] == query:
                            valid_json_data.append((query, response, json_item))
                            break
            
            # Run evaluation with chunk overlap
            results_df, output_file = await evaluator.evaluate_comprehensive_with_overlap(queries, search_responses, valid_json_data)
        else:
            # Run standard evaluation
            results_df, output_file = await evaluator.evaluate_comprehensive(queries, search_responses)
        
        # Generate summary
        summary = evaluator.generate_summary_report(results_df)
        
        # Print summary to terminal
        print("\n" + "="*80)
        print("📊 EVALUATION SUMMARY")
        print("="*80)
        print_summary_report(summary)
        
        print(f"\n💾 Results saved to: {output_file}")
        print("✅ Retrieval benchmark evaluation completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during evaluation: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 