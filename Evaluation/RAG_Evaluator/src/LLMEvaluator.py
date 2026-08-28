#!/usr/bin/env python3
"""
Comprehensive RAG Evaluation Script

This script evaluates RAG systems across three key dimensions:
1. Answer Correctness - How accurate the generated answer is compared to ground truth
2. Answer Relevance - How relevant the answer is to the user query
3. Context Relevance - How relevant the retrieved context is to the user query

Usage:
    python comprehensive_evaluator.py --input data.xlsx --sheet Sheet1
    python comprehensive_evaluator.py --input data.xlsx --sheet Sheet1 --model azure
    python comprehensive_evaluator.py --input data.xlsx --sheet Sheet1 --output results.xlsx
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
from typing import List, Dict, Tuple, Optional
from openai import AzureOpenAI

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.configManager import ConfigManager
from evaluators.baseEvaluator import BaseEvaluator
from async_api_calls import call_search_api_async, AsyncAnswerProcessor


class ComprehensiveEvaluator(BaseEvaluator):
    """
    Comprehensive evaluator for RAG systems that evaluates:
    - Answer Correctness
    - Answer Relevance  
    - Context Relevance
    """
    
    def __init__(self, model_name: str, openai_client, model_type: str = "openai"):
        self.model_name = model_name
        self.openai_client = openai_client
        self.model_type = model_type
        self.config = ConfigManager().get_config()
        # Create semaphore for concurrency control (max 5 concurrent requests)
        self.semaphore = asyncio.Semaphore(5)
        
    def evaluate_answer_correctness(self, query: str, answer: str, ground_truth: str) -> Dict:
        """
        Evaluate how correct the generated answer is compared to ground truth using RAGAS framework.
        
        Args:
            query: User query
            answer: Generated answer
            ground_truth: Expected correct answer
            
        Returns:
            Dictionary with correctness score and explanation
        """
        prompt = f"""You are an evaluator assessing the quality of a generated answer from a language model using the RAGAS framework. You are provided with the following:

Query: {query}

Ground Truth: {ground_truth}

Generated Answer: {answer}

You need to evaluate two metrics:

Answer Correctness: How factually and semantically correct is the Generated Answer, based on both the Query and the Ground Truth?

Focus on factual alignment and whether the core meaning matches the Ground Truth.

Score on a scale from 0 (completely incorrect) to 1 (fully correct).

Answer Relevancy: How relevant is the Generated Answer to the Query?

Consider how well the answer addresses the user's intent and question.

Score on a scale from 0 (completely irrelevant) to 1 (fully relevant).

Provide your evaluation in this exact format:
Correctness Score: [0-1]
Relevance Score: [0-1]
Explanation: [2-3 sentences explaining both scores]"""

        messages = [
            {"role": "system", "content": "You are an expert evaluator for question-answering systems using the RAGAS framework."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.attempt_api_call(messages)
        if response:
            correctness_score, answer_relevance_score, explanation = self._parse_ragas_response(response)
            # Convert 0-1 scale to 0-5 scale for consistency
            correctness_0_5 = int(correctness_score * 5) if correctness_score >= 0 else -1
            relevance_0_5 = int(answer_relevance_score * 5) if answer_relevance_score >= 0 else -1
            
            return {
                "correctness_score": correctness_0_5,
                "answer_relevance_score": relevance_0_5,
                "correctness_explanation": explanation,
                "answer_relevance_explanation": explanation
            }
        else:
            return {
                "correctness_score": -1,
                "answer_relevance_score": -1,
                "correctness_explanation": "Failed to get evaluation response",
                "answer_relevance_explanation": "Failed to get evaluation response"
            }
    
    def evaluate_answer_relevance(self, query: str, answer: str) -> Dict:
        """
        Evaluate how relevant the generated answer is to the user query using RAGAS framework.
        This method now uses the same unified prompt as evaluate_answer_correctness.
        
        Args:
            query: User query
            answer: Generated answer
            
        Returns:
            Dictionary with relevance score and explanation
        """
        # Use the same unified evaluation as evaluate_answer_correctness
        # but with empty ground truth for relevance-only evaluation
        return self.evaluate_answer_correctness(query, answer, "")
    
    def evaluate_context_relevance(self, query: str, context: str) -> Dict:
        """
        Evaluate how relevant the retrieved context is to the user query.
        
        Args:
            query: User query
            context: Retrieved context
            
        Returns:
            Dictionary with context relevance score and explanation
        """
        prompt = f"""You are an evaluator assessing the quality of retrieved context for a question-answering system using the RAGAS framework. You are provided with the following:

Query: {query}

Retrieved Context: {context}

You need to evaluate:

Context Relevance: How relevant is the Retrieved Context to the Query?

Consider how well the context would help answer the user's question and whether it contains useful information.

Score on a scale from 0 (completely irrelevant) to 1 (fully relevant).

Provide your evaluation in this exact format:
Context Relevance Score: [0-1]
Explanation: [2-3 sentences explaining your score]"""

        messages = [
            {"role": "system", "content": "You are an expert evaluator for information retrieval systems using the RAGAS framework."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.attempt_api_call(messages)
        if response:
            score, explanation = self._parse_score_response_ragas(response, "Context Relevance Score")
            # Convert 0-1 scale to 0-5 scale for consistency
            score_0_5 = int(score * 5) if score >= 0 else -1
            return {
                "context_relevance_score": score_0_5,
                "context_relevance_explanation": explanation
            }
        else:
            return {
                "context_relevance_score": -1,
                "context_relevance_explanation": "Failed to get evaluation response"
            }
    
    async def evaluate_all_metrics(self, query: str, answer: str, ground_truth: str, context: str) -> Dict:
        """
        Evaluate all three metrics (correctness, relevance, context relevance) in a single OpenAI call.
        
        Args:
            query: User query
            answer: Generated answer
            ground_truth: Expected correct answer
            context: Retrieved context
            
        Returns:
            Dictionary with all three scores and explanations
        """
        prompt = f"""You are an expert evaluator of question-answering systems using the RAGAS framework. Be strict in your evaluation — only give 100% if the answer is fully complete, factually accurate, and the context is completely supportive of the answer. Minor omissions or partial correctness should reduce the score.

You are provided with the following:

Query: {query}

Ground Truth: {ground_truth}

Generated Answer: {answer}

Retrieved Context: {context}

---

Evaluate the following three metrics, each scored between 0% and 100%, based on the definitions below:

📌 Metric Definitions:

1. **Answer Relevancy**  
Measures how well the Generated Answer addresses the user's original query, regardless of factual accuracy.  
- Check if the answer directly relates to the question.  
- Focus on topical and intent alignment.  
**Key Question:** Is this answer relevant to what the user asked?  
Score Range:  
0% = Completely irrelevant  
100% = Fully aligned and directly relevant to the query  

2. **Answer Correctness**  
Measures whether the Generated Answer is factually correct and semantically aligned with the Ground Truth.  
- Check for factual accuracy.  
- Ensure the meaning is preserved.  
- Penalize if information is missing, wrong, or hallucinated.  
**Key Question:** Is this answer factually and semantically correct compared to the ground truth?  
Score Range:  
0% = Entirely incorrect or misleading  
100% = Fully accurate and matches the ground truth  

3. **Context Relevancy**  
Measures how relevant and useful the Retrieved Context is for answering the Query, regardless of how the model used it.  
- Check if the context contains enough information to answer the question.  
**Key Question:** Would this context help someone answer the question correctly?  
**Important Note:** Context Relevancy should be evaluated using only the Query and the Retrieved Context. Do not consider the Ground Truth or Generated Answer in this score.
Score Range:  
0% = Totally unrelated or unhelpful  
100% = Highly relevant to the query  

---

📝 Output Format:
Return your evaluation in this exact format:

Correctness Score: [0–100]%  
Correctness Explanation: [Explain why you gave that score.]

Answer Relevance Score: [0–100]%  
Answer Relevance Explanation: [Explain why you gave that score.]

Context Relevance Score: [0–100]%  
Context Relevance Explanation: [Explain why you gave that score.]

Each explanation must be specific to the metric. Do not repeat the same explanation for multiple metrics."""

        messages = [
            {"role": "system", "content": "You are an expert evaluator for question-answering systems using the RAGAS framework. Be strict in your evaluation — only give 100% if the answer is fully complete, factually accurate, and the context is completely supportive of the answer."},
            {"role": "user", "content": prompt}
        ]
        response = await self.attempt_api_call_async(messages)
        if response:
            correctness_score, answer_relevance_score, context_score, explanations = self._parse_all_metrics_response(response)
            
            return {
                "correctness_score": correctness_score,
                "answer_relevance_score": answer_relevance_score,
                "context_relevance_score": context_score,
                "correctness_explanation": explanations['correctness'],
                "answer_relevance_explanation": explanations['relevance'],
                "context_relevance_explanation": explanations['context']
            }
        else:
            return {
                "correctness_score": -1,
                "answer_relevance_score": -1,
                "context_relevance_score": -1,
                "correctness_explanation": "Failed to get evaluation response",
                "answer_relevance_explanation": "Failed to get evaluation response",
                "context_relevance_explanation": "Failed to get evaluation response"
            }
    
    def _parse_ragas_response(self, response: str) -> Tuple[float, float, str]:
        """
        Parse RAGAS evaluation response to extract correctness score, relevance score, and explanation.
        
        Args:
            response: Raw response from evaluation API
            
        Returns:
            Tuple of (correctness_score, answer_relevance_score, explanation)
        """
        try:
            import re
            
            # Extract correctness score
            correctness_pattern = r'Correctness Score:\s*([0-9]*\.?[0-9]+)'
            correctness_match = re.search(correctness_pattern, response, re.IGNORECASE)
            correctness_score = float(correctness_match.group(1)) if correctness_match else -1
            
            # Extract relevance score
            answer_relevance_pattern = r'Answer Relevance Score:\s*([0-9]*\.?[0-9]+)'
            answer_relevance_match = re.search(answer_relevance_pattern, response, re.IGNORECASE)
            answer_relevance_score = float(answer_relevance_match.group(1)) if answer_relevance_match else -1
            
            # Extract explanation
            explanation_pattern = r'Explanation:\s*(.+?)(?:\n|$)'
            explanation_match = re.search(explanation_pattern, response, re.IGNORECASE | re.DOTALL)
            explanation = explanation_match.group(1).strip() if explanation_match else "No explanation provided"
            
            # Validate score ranges
            if correctness_score < 0 or correctness_score > 1:
                correctness_score = -1
            if answer_relevance_score < 0 or answer_relevance_score > 1:
                answer_relevance_score = -1
            
            return correctness_score, answer_relevance_score, explanation
            
        except Exception as e:
            print(f"Error parsing RAGAS response: {str(e)}")
            return -1, -1, f"Error parsing response: {str(e)}"
    
    def _parse_score_response_ragas(self, response: str, score_type: str) -> Tuple[float, str]:
        """
        Parse evaluation response to extract score and explanation for RAGAS framework (0-1 scale).
        
        Args:
            response: Raw response from evaluation API
            score_type: Type of score being parsed
            
        Returns:
            Tuple of (score, explanation)
        """
        try:
            import re
            
            # Extract score using regex for 0-1 scale
            score_pattern = f"{score_type}:\\s*([0-9]*\\.?[0-9]+)"
            score_match = re.search(score_pattern, response, re.IGNORECASE)
            
            if score_match:
                score = float(score_match.group(1))
            else:
                # Try to find any number between 0-1 in the response
                score_match = re.search(r'\b([0-9]*\.?[0-9]+)\b', response)
                score = float(score_match.group(1)) if score_match else -1
            
            # Extract explanation
            explanation_pattern = r'Explanation:\s*(.+?)(?:\n|$)'
            explanation_match = re.search(explanation_pattern, response, re.IGNORECASE | re.DOTALL)
            explanation = explanation_match.group(1).strip() if explanation_match else "No explanation provided"
            
            # Validate score range (0-1 for RAGAS)
            if score < 0 or score > 1:
                score = -1
                explanation = "Invalid score extracted from response"
            
            return score, explanation
            
        except Exception as e:
            print(f"Error parsing {score_type} response: {str(e)}")
            return -1, f"Error parsing response: {str(e)}"
    
    def _parse_all_metrics_response(self, response: str) -> Tuple[float, float, float, Dict[str, str]]:
        """
        Parse evaluation response to extract all three scores and their individual explanations.

        Args:
            response: Raw response from evaluation API

        Returns:
            Tuple of (correctness_score, answer_relevance_score, context_score, explanations_dict)
        """
        try:
            import re

            # Patterns to extract scores - match the exact format from the prompt
            correctness_score = float(re.search(r'Correctness Score:\s*([0-9]+)%', response, re.IGNORECASE).group(1))
            answer_relevance_score = float(re.search(r'Answer Relevance Score:\s*([0-9]+)%', response, re.IGNORECASE).group(1))
            context_score = float(re.search(r'Context Relevance Score:\s*([0-9]+)%', response, re.IGNORECASE).group(1))

            # More precise extraction of explanations using lookahead and lookbehind
            # Find the start and end of each explanation section
            correctness_pattern = r'Correctness Explanation:\s*(.*?)(?=\n\s*Answer Relevance Score:)'
            relevance_pattern = r'Answer Relevance Explanation:\s*(.*?)(?=\n\s*Context Relevance Score:)'
            context_pattern = r'Context Relevance Explanation:\s*(.*?)(?=\n\s*$|\Z)'
            
            # Extract explanations with fallback patterns
            correctness_exp = re.search(correctness_pattern, response, re.DOTALL | re.IGNORECASE)
            relevance_exp = re.search(relevance_pattern, response, re.DOTALL | re.IGNORECASE)
            context_exp = re.search(context_pattern, response, re.DOTALL | re.IGNORECASE)
            
            # Fallback patterns if the above don't work
            if not correctness_exp:
                correctness_pattern_fallback = r'Correctness Explanation:\s*(.*?)(?=\n\s*[A-Z][a-z]+)'
                correctness_exp = re.search(correctness_pattern_fallback, response, re.DOTALL | re.IGNORECASE)
            
            if not relevance_exp:
                relevance_pattern_fallback = r'Answer Relevance Explanation:\s*(.*?)(?=\n\s*[A-Z][a-z]+)'
                relevance_exp = re.search(relevance_pattern_fallback, response, re.DOTALL | re.IGNORECASE)
            
            if not context_exp:
                context_pattern_fallback = r'Context Relevance Explanation:\s*(.*?)(?=\n\s*$|\Z)'
                context_exp = re.search(context_pattern_fallback, response, re.DOTALL | re.IGNORECASE)
            
            explanations = {
                'correctness': correctness_exp.group(1).strip() if correctness_exp else "No correctness explanation provided",
                'relevance': relevance_exp.group(1).strip() if relevance_exp else "No relevance explanation provided",
                'context': context_exp.group(1).strip() if context_exp else "No context explanation provided"
            }

            return correctness_score, answer_relevance_score, context_score, explanations

        except Exception as e:
            print(f"❌ Error parsing all metrics response: {str(e)}")
            print(f"🔍 Raw response for debugging:")
            print(response)
            return -1, -1, -1, {
                'correctness': 'Error parsing response - check format',
                'relevance': 'Error parsing response - check format',
                'context': 'Error parsing response - check format'
            }
    
    async def evaluate_comprehensive(self, queries: List[str], answers: List[str], 
                             ground_truths: List[str], contexts: List[str]) -> pd.DataFrame:
        """
        Perform comprehensive evaluation across all three dimensions using a single OpenAI call per sample.
        
        Args:
            queries: List of user queries
            answers: List of generated answers
            ground_truths: List of ground truth answers
            contexts: List of retrieved contexts
            
        Returns:
            DataFrame with comprehensive evaluation results
        """
        results = []
        
        print(f"🔄 Starting comprehensive evaluation for {len(queries)} samples...")
        print(f"📊 Using {self.model_name} OpenAI call per sample for all three metrics")
        
        # Create tasks for concurrent evaluation
        tasks = []
        for i, (query, answer, ground_truth, context) in enumerate(zip(queries, answers, ground_truths, contexts)):
            task = self.evaluate_single_sample(i, query, answer, ground_truth, context)
            tasks.append(task)
        
        # Execute all tasks concurrently with progress bar
        print(f"🚀 Running {len(tasks)} evaluations concurrently...")
        
        # Create progress bar
        progress_bar = tqdm(total=len(tasks), desc="Evaluating", unit="sample")
        
        # Track completed tasks
        completed_results = []
        completed_count = 0
        
        # Process tasks as they complete
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                completed_results.append(result)
                completed_count += 1
                progress_bar.update(1)
                progress_bar.set_postfix({
                    'Completed': f"{completed_count}/{len(tasks)}",
                    'Success': f"{len([r for r in completed_results if not isinstance(r, Exception)])}"
                })
            except Exception as e:
                print(f"❌ Error in evaluation: {str(e)}")
                completed_count += 1
                progress_bar.update(1)
        
        progress_bar.close()
        
        # Sort results by sample_id to maintain order
        completed_results.sort(key=lambda x: x.get('sample_id', 0) if not isinstance(x, Exception) else 0)
        
        # Process results and handle any exceptions
        processed_results = []
        for i, result in enumerate(completed_results):
            if isinstance(result, Exception):
                print(f"❌ Error evaluating sample {i+1}: {str(result)}")
                # Create error result
                error_result = {
                    "query": queries[i] if i < len(queries) else "Error",
                    "answer": answers[i] if i < len(answers) else "Error",
                    "ground_truth": ground_truths[i] if i < len(ground_truths) else "Error",
                    "context": contexts[i] if i < len(contexts) else "Error",
                    "sample_id": i + 1,
                    "correctness_score": -1,
                    "answer_relevance_score": -1,
                    "context_relevance_score": -1,
                    "correctness_explanation": f"Evaluation failed: {str(result)}",
                    "answer_relevance_explanation": f"Evaluation failed: {str(result)}",
                    "context_relevance_explanation": f"Evaluation failed: {str(result)}"
                }
                processed_results.append(error_result)
            else:
                processed_results.append(result)
        
        successful_count = len([r for r in processed_results if r.get('correctness_score', -1) >= 0])
        print(f"✅ Completed {successful_count}/{len(tasks)} evaluations successfully")
        
        df = pd.DataFrame(processed_results)
        df = self._format_dataframe_columns(df)
        return df
    
    async def evaluate_single_sample(self, index: int, query: str, answer: str, ground_truth: str, context: str) -> Dict:
        """
        Evaluate a single sample asynchronously.
        
        Args:
            index: Sample index
            query: User query
            answer: Generated answer
            ground_truth: Expected correct answer
            context: Retrieved context
            
        Returns:
            Dictionary with evaluation results
        """
        result = {
            "query": query,
            "answer": answer,
            "ground_truth": ground_truth,
            "context": context,
        }
        
        # Evaluate all three metrics in a single OpenAI call
        all_metrics_result = await self.evaluate_all_metrics(query, answer, ground_truth, context)
        result.update(all_metrics_result)
        
        return result
    
    def _format_dataframe_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure DataFrame columns are properly formatted and not truncated.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Formatted DataFrame
        """
        # Ensure all explanation columns have proper content
        explanation_columns = ['correctness_explanation', 'answer_relevance_explanation', 'context_relevance_explanation']
        
        for col in explanation_columns:
            if col in df.columns:
                # Fill empty or very short explanations
                df[col] = df[col].fillna("No explanation provided")
                df[col] = df[col].apply(lambda x: "No explanation provided" if len(str(x)) < 5 else x)
                
        
        return df
    
    def evaluate(self, queries: List[str], answers: List[str], 
                ground_truths: List[str], contexts: List[str]) -> pd.DataFrame:
        """
        Abstract method implementation - alias for evaluate_comprehensive.
        
        Args:
            queries: List of user queries
            answers: List of generated answers
            ground_truths: List of ground truth answers
            contexts: List of retrieved contexts
            
        Returns:
            DataFrame with evaluation results
        """
        return self.evaluate_comprehensive(queries, answers, ground_truths, contexts)
    
    def process_results(self, results: pd.DataFrame) -> Dict:
        """
        Abstract method implementation - alias for generate_summary_report.
        
        Args:
            results: DataFrame with evaluation results
            
        Returns:
            Dictionary with summary statistics
        """
        return self.generate_summary_report(results)
    
    def attempt_api_call(self, messages: List[Dict]) -> Optional[str]:
        """
        Attempt to make an API call to the OpenAI model.
        
        Args:
            messages: List of message dictionaries for the API call
            
        Returns:
            Response string if successful, None if failed
        """
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_msg = str(e)
            print(f"❌ API call failed: {error_msg}")
            
            # Provide specific guidance for common Azure errors
            if "404" in error_msg and "Resource not found" in error_msg:
                print("🔍 Azure 404 Error - Possible causes:")
                print("   • Model deployment name is incorrect")
                print("   • Model deployment doesn't exist in your Azure resource")
                print("   • API version is not supported")
                print(f"   • Current model: {self.model_name}")
                print(f"   • Current model type: {self.model_type}")
            elif "401" in error_msg:
                print("🔍 Azure 401 Error - Authentication failed:")
                print("   • Check if AZURE_OPENAI_API_KEY is set correctly")
                print("   • Verify the API key has access to the Azure resource")
            elif "403" in error_msg:
                print("🔍 Azure 403 Error - Access denied:")
                print("   • Check if your API key has permission to use this model")
                print("   • Verify the model deployment is active")
            
            return None
    
    async def attempt_api_call_async(self, messages: List[Dict]) -> Optional[str]:
        """
        Attempt to make an async API call to the OpenAI model.
        
        Args:
            messages: List of message dictionaries for the API call
            
        Returns:
            Response string if successful, None if failed
        """
        async with self.semaphore:  # Limit concurrent requests
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: self.openai_client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=0.0,
                        max_tokens=500
                    )
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Async API call failed: {error_msg}")
                
                # Provide specific guidance for common Azure errors
                if "404" in error_msg and "Resource not found" in error_msg:
                    print("🔍 Azure 404 Error - Possible causes:")
                    print("   • Model deployment name is incorrect")
                    print("   • Model deployment doesn't exist in your Azure resource")
                    print("   • API version is not supported")
                    print(f"   • Current model: {self.model_name}")
                    print(f"   • Current model type: {self.model_type}")
                elif "401" in error_msg:
                    print("🔍 Azure 401 Error - Authentication failed:")
                    print("   • Check if AZURE_OPENAI_API_KEY is set correctly")
                    print("   • Verify the API key has access to the Azure resource")
                elif "403" in error_msg:
                    print("🔍 Azure 403 Error - Access denied:")
                    print("   • Check if your API key has permission to use this model")
                    print("   • Verify the model deployment is active")
                elif "rate limit" in error_msg.lower():
                    print("🔍 Rate limit error - Consider reducing concurrency")
                
                return None
    
    def generate_summary_report(self, results_df: pd.DataFrame) -> Dict:
        """
        Generate a comprehensive summary report of evaluation results.
        
        Args:
            results_df: DataFrame with evaluation results
            
        Returns:
            Dictionary with summary statistics
        """
        if results_df.empty:
            return {"error": "No results to analyze"}
        
        # Filter valid results (scores >= 0)
        valid_correctness = results_df[results_df['correctness_score'] >= 0]
        valid_relevance = results_df[results_df['answer_relevance_score'] >= 0]
        valid_context = results_df[results_df['context_relevance_score'] >= 0]
        
        summary = {
            "total_samples": len(results_df),
            "evaluation_timestamp": datetime.now().isoformat(),
            "model_used": self.model_name,
            "model_type": self.model_type,
            
            # Answer Correctness Statistics (0-100% scale)
            "answer_correctness": {
                "total_evaluations": len(results_df),
                "valid_evaluations": len(valid_correctness),
                "average_score": valid_correctness['correctness_score'].mean() if not valid_correctness.empty else 0,
                "median_score": valid_correctness['correctness_score'].median() if not valid_correctness.empty else 0,
                "min_score": valid_correctness['correctness_score'].min() if not valid_correctness.empty else 0,
                "max_score": valid_correctness['correctness_score'].max() if not valid_correctness.empty else 0,
                "std_score": valid_correctness['correctness_score'].std() if not valid_correctness.empty else 0,
                "scale": "0-100%"
            },
            
            # Answer Relevance Statistics (0-100% scale)
            "answer_relevance": {
                "total_evaluations": len(results_df),
                "valid_evaluations": len(valid_relevance),
                "average_score": valid_relevance['answer_relevance_score'].mean() if not valid_relevance.empty else 0,
                "median_score": valid_relevance['answer_relevance_score'].median() if not valid_relevance.empty else 0,
                "min_score": valid_relevance['answer_relevance_score'].min() if not valid_relevance.empty else 0,
                "max_score": valid_relevance['answer_relevance_score'].max() if not valid_relevance.empty else 0,
                "std_score": valid_relevance['answer_relevance_score'].std() if not valid_relevance.empty else 0,
                "scale": "0-100%"
            },
            
            # Context Relevance Statistics (0-100% scale)
            "context_relevance": {
                "total_evaluations": len(results_df),
                "valid_evaluations": len(valid_context),
                "average_score": valid_context['context_relevance_score'].mean() if not valid_context.empty else 0,
                "median_score": valid_context['context_relevance_score'].median() if not valid_context.empty else 0,
                "min_score": valid_context['context_relevance_score'].min() if not valid_context.empty else 0,
                "max_score": valid_context['context_relevance_score'].max() if not valid_context.empty else 0,
                "std_score": valid_context['context_relevance_score'].std() if not valid_context.empty else 0,
                "scale": "0-100%"
            }
        }
        
        return summary


def setup_openai_client(model_type: str = "openai"):
    """
    Setup OpenAI client based on model type.
    
    Args:
        model_type: "openai" or "azure"
        
    Returns:
        OpenAI client instance
    """
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    if model_type == "azure":
        azure_conf = config["azure"]
        return AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=azure_conf["openai_api_version"],
            azure_endpoint=azure_conf["base_url"]
        )
    else:
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_model_name(model_type: str = "openai"):
    """
    Get model name from config.
    
    Args:
        model_type: "openai" or "azure"
        
    Returns:
        Model name string
    """
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    if model_type == "azure":
        # For Azure, this should be the deployment name from Azure Portal
        return config["azure"]["model_deployment"]
    else:
        return config["openai"]["model_name"]


async def fetch_missing_data_with_search_api(queries: List[str], answers: List[str], 
                                           ground_truths: List[str], contexts: List[str]) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Fetch missing answers or contexts using Search API.
    
    Args:
        queries: List of user queries
        answers: List of generated answers
        ground_truths: List of ground truth answers
        contexts: List of retrieved contexts
        
    Returns:
        Updated lists with missing data filled
    """
    config_manager = ConfigManager()
    config = config_manager.get_config()
    max_concurrent_requests = config.get("max_concurrent_requests_for_search_api", 2)
    # Determine API type based on config
    api_type = 'UXO'  # default
    if config.get('SA'):
        api_type = 'SA'
    elif config.get('UXO'):
        api_type = 'UXO'
    
    print(f"🔍 Checking for missing data and fetching from {api_type} Search API...")
    
    # Find indices where we need to fetch data
    missing_indices = []
    for i, (query, answer, context) in enumerate(zip(queries, answers, contexts)):
        # Check if answer is missing or empty
        if not answer or answer.strip() == "" or answer == "Failed to get response":
            missing_indices.append(i)
        # Check if context is missing or empty
        elif not context or (isinstance(context, list) and len(context) == 0) or context == "":
            missing_indices.append(i)
    
    if not missing_indices:
        print("✅ No missing data found, proceeding with existing data")
        return queries, answers, ground_truths, contexts
    
    print(f"📊 Found {len(missing_indices)} samples with missing data, fetching from Search API...")
    
    # Prepare queries for missing data
    missing_queries = [queries[i] for i in missing_indices]
    missing_ground_truths = [ground_truths[i] for i in missing_indices]
    
    # Generate persistent filename for this operation
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    persistent_filename = f"outputs/search_api_results_{api_type}_{timestamp}.xlsx"
    
    try:
        # Call Search API for missing data with persistent file saving
        api_results = await call_search_api_async(missing_queries, missing_ground_truths, api_type, 
                                                save_batches=True, persistent_filename=persistent_filename)
        
        # Update the original lists with fetched data
        for i, api_result in zip(missing_indices, api_results):
            if api_result and 'answer' in api_result and 'context' in api_result:
                # Update answer
                if not answers[i] or answers[i].strip() == "" or answers[i] == "Failed to get response":
                    answers[i] = api_result['answer']
                
                # Update context
                if not contexts[i] or (isinstance(contexts[i], list) and len(contexts[i]) == 0) or contexts[i] == "":
                    contexts[i] = api_result['context']
                
                print(f"✅ Fetched data for query {i+1}: {queries[i][:50]}...")
            else:
                print(f"⚠️  Failed to fetch data for query {i+1}")
        
        print(f"✅ Successfully fetched data for {len([r for r in api_results if r])} samples")
        print(f"💾 All batch data saved to persistent file: {persistent_filename}")
        
    except Exception as e:
        print(f"❌ Error fetching data from Search API: {str(e)}")
        print("⚠️  Proceeding with existing data")
    
    return queries, answers, ground_truths, contexts


async def fetch_all_data_from_search_api(queries: List[str], ground_truths: List[str]) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Fetch all answers and contexts from Search API.
    
    Args:
        queries: List of user queries
        ground_truths: List of ground truth answers
        
    Returns:
        Lists of queries, answers, ground_truths, and contexts
    """
    config_manager = ConfigManager()
    config = config_manager.get_config()
    max_concurrent_requests = config.get("max_concurrent_requests_for_search_api", 2)
    # Determine API type based on config
    api_type = 'UXO'  # default
    if config.get('SA'):
        api_type = 'SA'
    elif config.get('UXO'):
        api_type = 'UXO'
    
    print(f"🔍 Fetching all answers and contexts from {api_type} Search API...")
    print(f"📊 Fetching data for {len(queries)} queries...")
    
    # Generate persistent filename for this operation
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    persistent_filename = f"outputs/sa_api_outputs/search_api_results_{api_type}_{timestamp}.xlsx"
    
    try:
        # Call Search API for all data with persistent file saving
        api_results = await call_search_api_async(queries, ground_truths, api_type, 
                                                save_batches=True, persistent_filename=persistent_filename, max_concurrent=max_concurrent_requests)
        
        # Extract answers and contexts from API results
        answers = []
        contexts = []
        
        print(f"📊 Processing {len(api_results)} API results...")
        api_progress = tqdm(api_results, desc="Processing API results", unit="result")
        
        for i, api_result in enumerate(api_progress):
            if api_result and 'answer' in api_result and 'context' in api_result:
                answers.append(api_result['answer'])
                contexts.append(api_result['context'])
                api_progress.set_postfix({'Success': f"{len(answers)}/{i+1}"})
            else:
                # Fallback if API call failed
                answers.append("Failed to get response")
                contexts.append([])
                api_progress.set_postfix({'Failed': f"{i+1-len(answers)}/{i+1}"})
        
        api_progress.close()
        
        print(f"✅ Successfully fetched data for {len([r for r in api_results if r])} samples")
        print(f"💾 All batch data saved to persistent file: {persistent_filename}")
        
        return queries, answers, ground_truths, contexts
        
    except Exception as e:
        print(f"❌ Error fetching data from Search API: {str(e)}")
        print("⚠️  Proceeding with empty data")
        # Return empty data if API fails
        answers = ["Failed to get response"] * len(queries)
        contexts = [[]] * len(queries)
        return queries, answers, ground_truths, contexts


def load_data_from_excel(file_path: str, sheet_name: str = None, use_search_api: bool = False) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Load data from Excel file.
    
    Args:
        file_path: Path to Excel file
        sheet_name: Sheet name to load (optional)
        use_search_api: Whether to fetch answers/contexts from Search API
        
    Returns:
        Tuple of (queries, answers, ground_truths, contexts)
    """
    try:
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
        else:
            df = pd.read_excel(file_path, engine='openpyxl')
        
        # Handle different column name variations
        query_col = None
        for col in ['query', 'user_input', 'question']:
            if col in df.columns:
                query_col = col
                break
        
        answer_col = None
        for col in ['answer', 'response', 'prediction']:
            if col in df.columns:
                answer_col = col
                break
        
        ground_truth_col = None
        for col in ['ground_truth', 'reference', 'expected_answer']:
            if col in df.columns:
                ground_truth_col = col
                break
        
        context_col = None
        for col in ['context', 'contexts', 'retrieved_contexts']:
            if col in df.columns:
                context_col = col
                break
        
        # Check required columns based on use_search_api flag
        missing_cols = []
        if not query_col:
            missing_cols.append("query/user_input/question")
        if not ground_truth_col:
            missing_cols.append("ground_truth/reference/expected_answer")
        
        # Only require answer/context columns if not using Search API
        if not use_search_api:
            if not answer_col:
                missing_cols.append("answer/response/prediction")
            if not context_col:
                missing_cols.append("context/contexts/retrieved_contexts")
        
        if missing_cols:
            raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")
        
        queries = df[query_col].fillna('').tolist()
        ground_truths = df[ground_truth_col].fillna('').tolist()
        
        # Handle answers and contexts based on use_search_api flag
        if use_search_api:
            # When using Search API, we don't need existing answers/contexts
            # They will be fetched from the API
            answers = [""] * len(queries)  # Empty answers, will be filled by API
            contexts = [[]] * len(queries)  # Empty contexts, will be filled by API
        else:
            # Use existing answers and contexts from the file
            answers = df[answer_col].fillna('').tolist()
            contexts = df[context_col].fillna('').tolist()
        
        # Convert contexts to string if they're lists
        processed_contexts = []
        for context in contexts:
            if isinstance(context, list):
                processed_contexts.append('\n'.join(context))
            else:
                processed_contexts.append(str(context))
        
        return queries, answers, ground_truths, processed_contexts
        
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
    print("📊 COMPREHENSIVE EVALUATION SUMMARY")
    print("="*80)
    
    print(f"📋 Total Samples: {summary['total_samples']}")
    print(f"🤖 Model Used: {summary['model_used']} ({summary['model_type'].upper()})")
    print(f"⏰ Evaluation Time: {summary['evaluation_timestamp']}")
    
    print("\n" + "-"*80)
    print("✅ ANSWER CORRECTNESS (0-100% Scale)")
    print("-"*80)
    correctness = summary['answer_correctness']
    print(f"   Valid Evaluations: {correctness['valid_evaluations']}/{correctness['total_evaluations']}")
    print(f"   Average Score: {correctness['average_score']:.1f}%")
    print(f"   Median Score: {correctness['median_score']:.1f}%")
    print(f"   Score Range: {correctness['min_score']:.1f}% - {correctness['max_score']:.1f}%")
    print(f"   Standard Deviation: {correctness['std_score']:.1f}%")
    
    print("\n" + "-"*80)
    print("🔍 ANSWER RELEVANCE (0-100% Scale)")
    print("-"*80)
    relevance = summary['answer_relevance']
    print(f"   Valid Evaluations: {relevance['valid_evaluations']}/{relevance['total_evaluations']}")
    print(f"   Average Score: {relevance['average_score']:.1f}%")
    print(f"   Median Score: {relevance['median_score']:.1f}%")
    print(f"   Score Range: {relevance['min_score']:.1f}% - {relevance['max_score']:.1f}%")
    print(f"   Standard Deviation: {relevance['std_score']:.1f}%")
    
    print("\n" + "-"*80)
    print("📚 CONTEXT RELEVANCE (0-100% Scale)")
    print("-"*80)
    context = summary['context_relevance']
    print(f"   Valid Evaluations: {context['valid_evaluations']}/{context['total_evaluations']}")
    print(f"   Average Score: {context['average_score']:.1f}%")
    print(f"   Median Score: {context['median_score']:.1f}%")
    print(f"   Score Range: {context['min_score']:.1f}% - {context['max_score']:.1f}%")
    print(f"   Standard Deviation: {context['std_score']:.1f}%")
    
    print("\n" + "="*80)


def ensure_outputs_directory():
    """Ensure the outputs directory exists."""
    if not os.path.exists("outputs"):
        os.makedirs("outputs", exist_ok=True)
        print("📁 Created outputs directory")


async def main():
    """Main function to handle command line arguments and run evaluation."""
    parser = argparse.ArgumentParser(
        description='Comprehensive RAG Evaluation Script - Multi-Sheet Support with Search API Integration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate all sheets using data from input file (with missing data auto-fetch)
  python comprehensive_evaluator.py --input data.xlsx
  
  # Evaluate all sheets using Search API for all answers and contexts
  python comprehensive_evaluator.py --input data.xlsx --use_search_api
  
  # Evaluate specific sheet using Search API with high concurrency
  python comprehensive_evaluator.py --input data.xlsx --sheet Sheet1 --use_search_api --concurrency 10
  
  # Evaluate first 5 samples from all sheets using input file data
  python comprehensive_evaluator.py --input data.xlsx --sample 5
  
  # Evaluate specific sheet with custom output using Search API
  python comprehensive_evaluator.py --input data.xlsx --sheet Sheet1 --output results.xlsx --use_search_api
        """
    )
    
    parser.add_argument('--input', type=str, required=True,
                       help='Path to input Excel file')
    parser.add_argument('--sheet', type=str, default=None,
                       help='Sheet name to evaluate (defaults to all sheets)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file path (default: comprehensive_evaluation_<timestamp>.xlsx)')
    parser.add_argument('--sample', type=int, default=None,
                       help='Number of samples to evaluate (default: all)')
    parser.add_argument('--use_search_api', action='store_true',
                       help='Fetch answers and contexts from Search API instead of using input file data')
    parser.add_argument('--concurrency', type=int, default=5,
                       help='Number of concurrent API calls (default: 5, overrides config setting)')
    
    args = parser.parse_args()
    
    try:
        # Ensure outputs directory exists
        ensure_outputs_directory()
        
        # Auto-detect model type from config
        config_manager = ConfigManager()
        config = config_manager.get_config()
        model_type = config["model_type"]
        # Check which model configuration is available
        if not model_type:
            if "azure" in config and config["azure"].get("model_name") and config["azure"]["model_name"] != "<MODEL NAME>":
                model_type = "azure"
                print("🤖 Using Azure OpenAI model from config")
            else:
                model_type = "openai"
                print("🤖 Using OpenAI model from config")
        
        print("🚀 Starting Comprehensive RAG Evaluation")
        print("="*60)
        print(f"📁 Input File: {args.input}")
        print(f"🤖 Model Type: {model_type.upper()}")
        if args.sample:
            print(f"📊 Sample Size: {args.sample}")
        if args.use_search_api:
            print(f"🔍 Using Search API to fetch answers and contexts")
        else:
            print(f"📄 Using answers and contexts from input file")
        print()
        
        # Setup evaluator
        print("🔄 Setting up evaluator...")
        openai_client = setup_openai_client(model_type)
        model_name = get_model_name(model_type)
        evaluator = ComprehensiveEvaluator(model_name, openai_client, model_type)
        
        # Set concurrency level from config or command line
        config_concurrency = config.get("max_concurrent_requests_for_evaluation", 5)
        concurrency_level = args.concurrency if args.concurrency != 5 else config_concurrency
        evaluator.semaphore = asyncio.Semaphore(concurrency_level)
        print(f"⚡ Concurrency level set to {concurrency_level} concurrent API calls (from config: {config_concurrency})")
        
        # Show search API concurrency setting
        search_api_concurrency = config.get("max_concurrent_requests_for_search_api", 2)
        print(f"🔍 Search API concurrency: {search_api_concurrency} concurrent requests")
        
        if args.concurrency != 5:
            print(f"🔧 Command line concurrency ({args.concurrency}) overrides config setting ({config_concurrency})")
        else:
            print(f"🔧 Using concurrency setting from config file: {config_concurrency}")
        
        # Get all sheet names from the Excel file
        try:
            excel_file = pd.ExcelFile(args.input, engine='openpyxl')
            sheet_names = excel_file.sheet_names
            print(f"📋 Found {len(sheet_names)} sheets: {', '.join(sheet_names)}")
        except Exception as e:
            print(f"❌ Error reading Excel file: {str(e)}")
            return
        
        # Filter sheets if specific sheet is requested
        if args.sheet:
            if args.sheet in sheet_names:
                sheet_names = [args.sheet]
                print(f"📋 Processing specific sheet: {args.sheet}")
            else:
                print(f"❌ Sheet '{args.sheet}' not found. Available sheets: {', '.join(sheet_names)}")
                return
        else:
            print(f"📋 Processing all {len(sheet_names)} sheets")
        
        # Initialize results storage
        all_results = []
        all_summaries = []
        
        # Generate output filename
        if not args.output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            args.output = f"outputs/comprehensive_evaluation_{timestamp}.xlsx"
        
        print(f"💾 Results will be saved to: {args.output}")
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Process each sheet
        print(f"📋 Processing {len(sheet_names)} sheets...")
        sheet_progress = tqdm(sheet_names, desc="Processing sheets", unit="sheet")
        
        for i, current_sheet_name in enumerate(sheet_progress):
            sheet_progress.set_description(f"Processing {current_sheet_name}")
            print(f"\n📋 Processing sheet: {current_sheet_name}")
            print("-" * 60)
            
            try:
                # Load data from current sheet
                print(f"🔄 Loading data from sheet '{current_sheet_name}'...")
                queries, answers, ground_truths, contexts = load_data_from_excel(args.input, current_sheet_name,args.use_search_api)
                
                if args.sample:
                    queries = queries[:args.sample]
                    ground_truths = ground_truths[:args.sample]
                    
                    # Only slice answers and contexts if not using Search API
                    if not args.use_search_api:
                        answers = answers[:args.sample]
                        contexts = contexts[:args.sample]
                print(f"✅ Loaded {len(queries)} samples from sheet '{current_sheet_name}'")
                
                if len(queries) == 0:
                    print(f"⚠️  No data found in sheet '{current_sheet_name}', skipping...")
                    continue
                
                # Handle data fetching based on use_search_api flag
                if args.use_search_api:
                    print(f"🔍 Fetching data from Search API for {len(queries)} queries...")
                    queries, answers, ground_truths, contexts = await fetch_all_data_from_search_api(queries, ground_truths)
                    print(f"✅ Data fetching completed")
                else:
                    # Check for missing data and fetch from Search API if needed
                    print(f"🔍 Checking for missing answers or contexts...")
                    queries, answers, ground_truths, contexts = await fetch_missing_data_with_search_api(
                        queries, answers, ground_truths, contexts
                    )
                
                # Run evaluation
                print(f"🔄 Running comprehensive evaluation for sheet '{current_sheet_name}'...")
                start_time = time.time()
                
                results_df = await evaluator.evaluate_comprehensive(queries, answers, ground_truths, contexts)
                
                evaluation_time = time.time() - start_time
                
                # Generate summary
                print(f"🔄 Generating summary report for sheet '{current_sheet_name}'...")
                summary = evaluator.generate_summary_report(results_df)
                
                # Add sheet information to summary
                summary['sheet_name'] = current_sheet_name
                summary['evaluation_time'] = evaluation_time
                
                # Print summary for this sheet
                print(f"\n📊 RESULTS FOR SHEET: {current_sheet_name}")
                print("=" * 60)
                print_summary_report(summary)
                
                # Store results
                all_results.append((current_sheet_name, results_df))
                all_summaries.append(summary)
                
                # Save this sheet's results immediately
                print(f"💾 Saving results for sheet '{current_sheet_name}'...")
                try:
                    # Ensure the output directory exists
                    output_dir = os.path.dirname(args.output)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                    
                    with pd.ExcelWriter(args.output, engine='openpyxl', mode='a' if i > 0 else 'w') as writer:
                        # Save detailed results for this sheet
                        results_df.to_excel(writer, sheet_name=f'{current_sheet_name}', index=False)
                        
                        # Save summary for this sheet
        
                    
                    print(f"✅ Sheet '{current_sheet_name}' results saved successfully")
                except Exception as save_error:
                    print(f"⚠️  Warning: Could not save sheet '{current_sheet_name}' results: {str(save_error)}")
                    # Try to save to a different file as fallback
                    try:
                        fallback_file = args.output.replace('.xlsx', f'_{current_sheet_name}_only.xlsx')
                        results_df.to_excel(fallback_file, sheet_name=current_sheet_name, index=False)
                        print(f"✅ Sheet saved to fallback file: {fallback_file}")
                    except Exception as fallback_error:
                        print(f"❌ Could not save to fallback file either: {str(fallback_error)}")
                
                print(f"✅ Sheet '{current_sheet_name}' completed in {evaluation_time:.2f} seconds")
                
            except Exception as e:
                print(f"❌ Error processing sheet '{current_sheet_name}': {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        # Generate overall summary
        if all_summaries:
            print(f"\n🎉 OVERALL EVALUATION SUMMARY")
            print("=" * 80)
            print(f"📋 Total Sheets Processed: {len(all_summaries)}")
            print(f"🤖 Model Used: {model_name} ({model_type.upper()})")
            
            # Calculate overall statistics
            total_samples = sum(s['total_samples'] for s in all_summaries)
            total_evaluation_time = sum(s['evaluation_time'] for s in all_summaries)
            successful_samples = sum(s['answer_correctness']['valid_evaluations'] for s in all_summaries)
            
            print(f"📊 Total Samples Evaluated: {total_samples}")
            print(f"✅ Successful Evaluations: {successful_samples}")
            print(f"⏰ Total Evaluation Time: {total_evaluation_time:.2f} seconds")
            print(f"🚀 Average Time per Sample: {total_evaluation_time/total_samples:.2f} seconds")
            
            # Print per-sheet summary
            print(f"\n📋 PER-SHEET SUMMARY:")
            print("-" * 80)
            for summary in all_summaries:
                sheet_name = summary['sheet_name']
                correctness_avg = summary['answer_correctness']['average_score']
                relevance_avg = summary['answer_relevance']['average_score']
                context_avg = summary['context_relevance']['average_score']
                samples = summary['total_samples']
                eval_time = summary['evaluation_time']
                
                print(f"📄 {sheet_name}:")
                print(f"   Samples: {samples}")
                print(f"   Answer Correctness: {correctness_avg:.1f}%")
                print(f"   Answer Relevance: {relevance_avg:.1f}%")
                print(f"   Context Relevance: {context_avg:.1f}%")
                print(f"   Time: {eval_time:.2f}s")
                print()
            
            # Save overall summary to the same file
            print(f"💾 Saving overall summary...")
            try:
                # Check if the file exists, if not create it in write mode
                file_exists = os.path.exists(args.output)
                mode = 'a' if file_exists else 'w'
                
                with pd.ExcelWriter(args.output, engine='openpyxl', mode=mode) as writer:
                    # Save overall summary
                    summary_df = pd.DataFrame(all_summaries)
                    summary_df.to_excel(writer, sheet_name='Overall_Summary', index=False)
                    
                    # Auto-adjust column widths for overall summary
                    worksheet = writer.sheets['Overall_Summary']
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                        worksheet.column_dimensions[column_letter].width = adjusted_width
                
                print(f"✅ Overall summary saved successfully")
                print(f"🎉 All results saved to: {args.output}")
                print(f"🎉 Evaluation completed successfully!")
                
            except Exception as save_error:
                print(f"⚠️  Warning: Could not save overall summary: {str(save_error)}")
                # Try to save to a different file as fallback
                try:
                    fallback_file = args.output.replace('.xlsx', '_summary_only.xlsx')
                    summary_df = pd.DataFrame(all_summaries)
                    summary_df.to_excel(fallback_file, sheet_name='Overall_Summary', index=False)
                    print(f"✅ Overall summary saved to fallback file: {fallback_file}")
                except Exception as fallback_error:
                    print(f"❌ Could not save to fallback file either: {str(fallback_error)}")
                print(f"✅ Individual sheet results were saved successfully")
            
        else:
            print("❌ No sheets were processed successfully")
            print(f"📁 No files were saved")
        
    except Exception as e:
        print(f"❌ Error during evaluation: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 