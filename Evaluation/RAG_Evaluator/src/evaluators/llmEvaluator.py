import os
import json
import asyncio
import aiohttp
import time
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from .baseEvaluator import BaseEvaluator
import logging

logger = logging.getLogger(__name__)

class LLMEvaluator(BaseEvaluator):
    """
    LLM-based evaluator using OpenAI to assess Answer Correctness, Answer Relevancy, and Context Relevancy
    """
    
    def __init__(self, openai_config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None):
        super().__init__()
        self.openai_config = openai_config or {}
        self.azure_config = azure_config or {}
        
        logger.info("🔧 Initializing LLM Evaluator...")
        logger.info(f"📋 OpenAI config keys: {list(self.openai_config.keys())}")
        logger.info(f"📋 Azure config keys: {list(self.azure_config.keys())}")
        
        # Check configuration validity
        has_valid_openai = self._has_valid_openai_config()
        has_valid_azure = self._has_valid_azure_config()
        user_selected_openai = self._user_selected_openai_model()
        
        logger.info(f"✅ Valid OpenAI config: {has_valid_openai}")
        logger.info(f"✅ Valid Azure config: {has_valid_azure}")
        logger.info(f"🎯 User selected OpenAI model: {user_selected_openai}")
        
        self.api_key = self._get_api_key()
        self.model_name = self._get_model_name()
        self.base_url = self._get_base_url()
        self.headers = self._get_headers()
        
        # Validation
        if not self.api_key:
            logger.error("❌ No valid API key found in configuration or environment")
            raise ValueError("API key is required for LLM Evaluator. Please provide valid OpenAI or Azure OpenAI credentials.")
        
        logger.info(f"🤖 LLM Evaluator initialized successfully!")
        logger.info(f"🎯 Using model: {self.model_name}")
        logger.info(f"🌐 Using endpoint: {self.base_url.split('?')[0]}...")  # Don't log full URL with params
    
    def debug_configuration(self) -> Dict[str, Any]:
        """Debug method to show current configuration choices"""
        return {
            "has_valid_openai_config": self._has_valid_openai_config(),
            "has_valid_azure_config": self._has_valid_azure_config(),
            "user_selected_openai_model": self._user_selected_openai_model(),
            "api_key_source": "OpenAI" if self.api_key == self.openai_config.get('api_key') else "Azure" if self.api_key == self.azure_config.get('api_key') else "Environment",
            "model_name": self.model_name,
            "endpoint_type": "Azure" if "azure.com" in self.base_url or "deployments" in self.base_url else "OpenAI",
            "base_url": self.base_url.split('?')[0]  # Don't expose full URL
        }
    
    def _is_valid_config_value(self, value: str) -> bool:
        """Check if a config value is valid (not a placeholder)"""
        if not value or not isinstance(value, str):
            return False
        
        # Check for common placeholder patterns
        placeholders = [
            '<', '>', 'AZURE_BASE_URL', 'MODEL_DEPLOYMENT', 'EMBEDDING_DEPLOYMENT',
            'OPENAI_API_KEY', 'AZURE_OPENAI_API_KEY', 'YOUR_', 'REPLACE_'
        ]
        
        value_upper = value.upper()
        return not any(placeholder in value_upper for placeholder in placeholders)
    
    def _has_valid_azure_config(self) -> bool:
        """Check if Azure configuration has valid (non-placeholder) values"""
        return (
            self._is_valid_config_value(self.azure_config.get('api_key', '')) and
            self._is_valid_config_value(self.azure_config.get('base_url', '')) and
            self._is_valid_config_value(self.azure_config.get('model_deployment', ''))
        )
    
    def _has_valid_openai_config(self) -> bool:
        """Check if OpenAI configuration has valid (non-placeholder) values"""
        return self._is_valid_config_value(self.openai_config.get('api_key', ''))
    
    def _user_selected_openai_model(self) -> bool:
        """Check if user explicitly selected an OpenAI model in the UI"""
        # Check if any config has a model name starting with 'openai-'
        openai_model = self.openai_config.get('model_name', '')
        azure_model = self.azure_config.get('model_name', '')
        
        return (
            openai_model.startswith('openai-') or 
            azure_model.startswith('openai-') or
            openai_model.startswith('gpt-')  # Direct OpenAI model names
        )
    
    def _get_api_key(self) -> str:
        """Get API key from config or environment, prioritizing valid configurations"""
        # Priority 1: Valid OpenAI config (user provided OpenAI API key)
        if self._has_valid_openai_config():
            logger.info("🔑 Using OpenAI API key from config")
            return self.openai_config['api_key']
        
        # Priority 2: User selected OpenAI model, try environment
        elif self._user_selected_openai_model() and os.getenv('OPENAI_API_KEY'):
            logger.info("🔑 Using OpenAI API key from environment (user selected OpenAI model)")
            return os.getenv('OPENAI_API_KEY')
        
        # Priority 3: Valid Azure config
        elif self._has_valid_azure_config():
            logger.info("🔑 Using Azure OpenAI API key from config")
            return self.azure_config['api_key']
        
        # Priority 4: Environment variables (fallback)
        elif os.getenv('OPENAI_API_KEY'):
            logger.info("🔑 Using OpenAI API key from environment (fallback)")
            return os.getenv('OPENAI_API_KEY')
        elif os.getenv('AZURE_OPENAI_API_KEY'):
            logger.info("🔑 Using Azure OpenAI API key from environment (fallback)")
            return os.getenv('AZURE_OPENAI_API_KEY')
        else:
            return ""
    
    def _get_model_name(self) -> str:
        """Get model name from config, prioritizing valid configurations"""
        # Priority 1: Valid OpenAI config
        if self._has_valid_openai_config() and self.openai_config.get('model_name'):
            logger.info(f"🤖 Using OpenAI model: {self.openai_config['model_name']}")
            return self.openai_config['model_name']
        
        # Priority 2: Valid Azure config  
        elif self._has_valid_azure_config() and self.azure_config.get('model_name'):
            logger.info(f"🤖 Using Azure OpenAI model: {self.azure_config['model_name']}")
            return self.azure_config['model_name']
        
        # Priority 3: Fallback from any config
        elif self.openai_config.get('model_name'):
            return self.openai_config['model_name']
        elif self.azure_config.get('model_name'):
            return self.azure_config['model_name']
        else:
            return "gpt-4o"
    
    def _get_base_url(self) -> str:
        """Get base URL for API calls, prioritizing valid configurations"""
        # Use Azure only if we have valid Azure config AND user didn't explicitly select OpenAI
        if self._has_valid_azure_config() and not self._user_selected_openai_model():
            # Azure OpenAI format
            base_url = self.azure_config['base_url'].rstrip('/')
            deployment = self.azure_config.get('model_deployment', self.model_name)
            api_version = self.azure_config.get('openai_api_version', '2024-02-15-preview')
            azure_url = f"{base_url}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
            logger.info(f"🌐 Using Azure OpenAI endpoint")
            return azure_url
        else:
            # Standard OpenAI format (default, fallback, and when user selected OpenAI)
            openai_url = "https://api.openai.com/v1/chat/completions"
            logger.info(f"🌐 Using OpenAI endpoint")
            return openai_url
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests, matching the chosen API provider"""
        headers = {
            "Content-Type": "application/json"
        }
        
        # Use Azure headers only if we have valid Azure config AND user didn't select OpenAI
        if self._has_valid_azure_config() and not self._user_selected_openai_model():
            headers["api-key"] = self.api_key
            logger.info("🔐 Using Azure OpenAI authentication headers")
        else:
            # Use OpenAI headers (default, fallback, and when user selected OpenAI)
            headers["Authorization"] = f"Bearer {self.api_key}"
            logger.info("🔐 Using OpenAI authentication headers")
            
            # Add OpenAI organization if available
            if self.openai_config.get('org_id') and self._is_valid_config_value(self.openai_config.get('org_id', '')):
                headers["OpenAI-Organization"] = self.openai_config['org_id']
                logger.info(f"🏢 Using OpenAI organization: {self.openai_config['org_id']}")
        
        return headers
    
    def get_answer_relevancy_prompt(self, user_query: str, generated_answer: str) -> List[Dict[str, str]]:
        """Get the prompt for Answer Relevancy evaluation"""
        return [
            {
                "role": "system",
                "content": "You are a helpful and precise evaluator tasked with assessing the relevancy of an answer generated by a Retrieval-Augmented Generation (RAG) system. Your role is to compare the generated answer with the user query and assign a relevancy score from 1 to 5, based on how well the answer aligns with the user's intent and information need. Focus solely on whether the answer is relevant and responsive to the query, regardless of supporting context or ground truth."
            },
            {
                "role": "user",
                "content": f"""Please evaluate the following answer for relevancy to the given query, using the rubric below:

---

📌 **Rubric for Answer Relevancy (1–5):**

**5 - Fully Relevant:** The answer completely and directly addresses the user query, with no off-topic or irrelevant content.

**4 - Mostly Relevant:** The answer is strongly related to the query and mostly fulfills its intent, with only minor off-topic details or slight undercoverage.

**3 - Somewhat Relevant:** The answer has partial relevance. It touches on the topic but misses important aspects of the intent or includes moderately unrelated content.

**2 - Weakly Relevant:** The answer is only loosely related to the query and fails to meet the query's intent. It contains significant irrelevant content.

**1 - Not Relevant:** The answer is completely unrelated to the query.

---

✉️ **User Query:**
{user_query}

🧾 **RAG Generated Answer:**
{generated_answer}

---

🔍 Please return your evaluation in the following format:
```json
{{
  "score": <1-5>,
  "justification": "<Brief explanation of your rating>"
}}
```"""
            }
        ]
    
    def get_context_relevancy_prompt(self, user_query: str, retrieved_context: str) -> List[Dict[str, str]]:
        """Get the prompt for Context Relevancy evaluation"""
        return [
            {
                "role": "system",
                "content": "You are a skilled evaluator tasked with judging the relevancy of retrieved context in response to a user query. Your goal is to assess how relevant the retrieved context is to the query, on a scale from 1 to 5, based on how well it supports answering the query. Focus only on the alignment between the context and the query — not on the final answer."
            },
            {
                "role": "user",
                "content": f"""Evaluate the relevance of the retrieved context with respect to the given query using the following rubric:

---

📌 **Rubric for Context Relevancy (1–5):**

**5 - Highly Relevant:** The context directly supports answering the core intent of the query with high specificity and usefulness.

**4 - Mostly Relevant:** The context covers most aspects of the query, with minor gaps or generalizations.

**3 - Somewhat Relevant:** The context is partially related to the query but lacks specificity or focus; helpful to some extent.

**2 - Weakly Relevant:** The context contains only loose or tangential references to the query, offering little support.

**1 - Not Relevant:** The context is unrelated or off-topic and does not help in answering the query.

---

✉️ **User Query:**
{user_query}

📚 **Retrieved Context:**
{retrieved_context}

---

🔍 Please return your evaluation in the following format:
```json
{{
  "score": <1-5>,
  "justification": "<Brief explanation of your rating>"
}}
```"""
            }
        ]
    
    def get_answer_correctness_prompt(self, user_query: str, ground_truth_answer: str, generated_answer: str) -> List[Dict[str, str]]:
        """Get the prompt for Answer Correctness evaluation"""
        return [
            {
                "role": "system",
                "content": "You are an expert evaluator assessing the correctness of an answer generated by a Retrieval-Augmented Generation (RAG) system. Your goal is to determine how accurately the generated answer aligns with the ground truth and how well it addresses the user's original query. You will assign a score from 1 (Completely Incorrect) to 5 (Completely Correct), using a detailed rubric."
            },
            {
                "role": "user",
                "content": f"""Given a user query, a ground truth answer, and a RAG-generated answer, please evaluate the correctness of the generated answer using the rubric below:

🎯 **Rubric for Answer Correctness**

**5 - Completely Correct:** The generated answer fully matches the ground truth in meaning and detail. It accurately answers the query without introducing any errors or omissions.

**4 - Mostly Correct:** The generated answer is largely accurate and aligns closely with the ground truth, with only minor omissions or slight differences in wording that do not affect the core meaning.

**3 - Partially Correct:** The answer includes some correct information relevant to the query and ground truth, but misses important points or includes minor factual inaccuracies.

**2 - Weakly Correct:** The answer contains fragments of relevant information but is mostly incorrect or significantly incomplete compared to the ground truth.

**1 - Completely Incorrect:** The answer does not match the ground truth at all. It is factually wrong, irrelevant, or misleading with respect to the query.

---

📥 **Input Format**

**User Query:**
{user_query}

**Ground Truth Answer:**
{ground_truth_answer}

**RAG Generated Answer:**
{generated_answer}

---

🧠 **Instructions**
- Carefully read the query, ground truth, and generated answer.
- Compare the generated answer with the ground truth, considering how well it answers the original query.
- Assign a correctness score (1–5) based on the rubric above.
- Provide a brief justification (1–2 sentences) for your score.

---

📝 **Output Format**
```json
{{
  "score": <1-5>,
  "justification": "<Brief explanation of your rating>"
}}
```"""
            }
        ]
    
    async def call_openai_api(self, session: aiohttp.ClientSession, messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """Make an API call to OpenAI/Azure OpenAI"""
        try:
            payload = {
                "messages": messages,
                "model": self.model_name,
                "temperature": 0.1,
                "max_tokens": 500,
                "response_format": {"type": "json_object"}
            }
            
            async with session.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '{}')
                    
                    # Parse the JSON response
                    try:
                        evaluation = json.loads(content)
                        return evaluation
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON response: {content}")
                        return {"score": 3, "justification": "Failed to parse LLM response"}
                else:
                    error_text = await response.text()
                    logger.error(f"API request failed with status {response.status}: {error_text}")
                    return None
        
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return None
    
    async def evaluate_answer_relevancy(self, session: aiohttp.ClientSession, query: str, answer: str) -> Dict[str, Any]:
        """Evaluate answer relevancy using LLM"""
        try:
            messages = self.get_answer_relevancy_prompt(query, answer)
            result = await self.call_openai_api(session, messages)
            
            if result and 'score' in result:
                # Convert 1-5 scale to 0-1 scale for consistency with RAGAS
                score = float(result['score']) / 5.0
                justification = result.get('justification', 'No justification provided')
                logger.info(f"🎯 Answer Relevancy: {score:.3f} - {justification}")
                return {'score': score, 'justification': justification}
            else:
                logger.warning("Failed to get answer relevancy score, using default")
                return {'score': 0.5, 'justification': 'Failed to get evaluation from LLM'}
        
        except Exception as e:
            logger.error(f"Error evaluating answer relevancy: {e}")
            return {'score': 0.5, 'justification': f'Error during evaluation: {str(e)}'}
    
    async def evaluate_context_relevancy(self, session: aiohttp.ClientSession, query: str, context: str) -> Dict[str, Any]:
        """Evaluate context relevancy using LLM"""
        try:
            messages = self.get_context_relevancy_prompt(query, context)
            result = await self.call_openai_api(session, messages)
            
            if result and 'score' in result:
                # Convert 1-5 scale to 0-1 scale for consistency with RAGAS
                score = float(result['score']) / 5.0
                justification = result.get('justification', 'No justification provided')
                logger.info(f"🎯 Context Relevancy: {score:.3f} - {justification}")
                return {'score': score, 'justification': justification}
            else:
                logger.warning("Failed to get context relevancy score, using default")
                return {'score': 0.5, 'justification': 'Failed to get evaluation from LLM'}
        
        except Exception as e:
            logger.error(f"Error evaluating context relevancy: {e}")
            return {'score': 0.5, 'justification': f'Error during evaluation: {str(e)}'}
    
    async def evaluate_answer_correctness(self, session: aiohttp.ClientSession, query: str, ground_truth: str, answer: str) -> Dict[str, Any]:
        """Evaluate answer correctness using LLM"""
        try:
            messages = self.get_answer_correctness_prompt(query, ground_truth, answer)
            result = await self.call_openai_api(session, messages)
            
            if result and 'score' in result:
                # Convert 1-5 scale to 0-1 scale for consistency with RAGAS
                score = float(result['score']) / 5.0
                justification = result.get('justification', 'No justification provided')
                logger.info(f"🎯 Answer Correctness: {score:.3f} - {justification}")
                return {'score': score, 'justification': justification}
            else:
                logger.warning("Failed to get answer correctness score, using default")
                return {'score': 0.5, 'justification': 'Failed to get evaluation from LLM'}
        
        except Exception as e:
            logger.error(f"Error evaluating answer correctness: {e}")
            return {'score': 0.5, 'justification': f'Error during evaluation: {str(e)}'}
    
    async def evaluate_batch(self, session: aiohttp.ClientSession, data_batch: List[Dict[str, Any]], 
                           batch_size: int = 5) -> List[Dict[str, Any]]:
        """Evaluate a batch of data using LLM metrics with concurrent processing"""
        logger.info(f"🤖 Starting LLM evaluation for batch of {len(data_batch)} items")
        
        # Process items in smaller concurrent batches for better performance
        semaphore = asyncio.Semaphore(batch_size)
        
        async def evaluate_single_item(item: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    query = item.get('query', '')
                    answer = item.get('answer', '')
                    ground_truth = item.get('ground_truth', '')
                    context = item.get('context', [])
                    
                    # Convert context to string if it's a list
                    context_str = ' '.join(context) if isinstance(context, list) else str(context)
                    
                    # Initialize result
                    result = {}
                    
                    # Evaluate each metric concurrently
                    tasks = []
                    
                    if answer and query:
                        tasks.append(self.evaluate_answer_relevancy(session, query, answer))
                    else:
                        tasks.append(asyncio.create_task(self._return_default_result(0.5, 'No answer or query provided')))
                    
                    if context_str and query:
                        tasks.append(self.evaluate_context_relevancy(session, query, context_str))
                    else:
                        tasks.append(asyncio.create_task(self._return_default_result(0.5, 'No context or query provided')))
                    
                    if answer and ground_truth and query:
                        tasks.append(self.evaluate_answer_correctness(session, query, ground_truth, answer))
                    else:
                        tasks.append(asyncio.create_task(self._return_default_result(0.5, 'No answer, ground truth, or query provided')))
                    
                    # Execute all evaluations concurrently for this item
                    evaluation_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Handle results and extract scores and justifications
                    default_result = {'score': 0.5, 'justification': 'Error during evaluation'}
                    
                    answer_relevancy_result = evaluation_results[0] if not isinstance(evaluation_results[0], Exception) else default_result
                    context_relevancy_result = evaluation_results[1] if not isinstance(evaluation_results[1], Exception) else default_result
                    answer_correctness_result = evaluation_results[2] if not isinstance(evaluation_results[2], Exception) else default_result
                    
                    # Add LLM metrics to result with both scores and justifications
                    result.update({
                        'LLM Answer Relevancy': answer_relevancy_result.get('score', 0.5),
                        'LLM Answer Relevancy Justification': answer_relevancy_result.get('justification', 'No justification available'),
                        'LLM Context Relevancy': context_relevancy_result.get('score', 0.5),
                        'LLM Context Relevancy Justification': context_relevancy_result.get('justification', 'No justification available'),
                        'LLM Answer Correctness': answer_correctness_result.get('score', 0.5),
                        'LLM Answer Correctness Justification': answer_correctness_result.get('justification', 'No justification available')
                    })
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error evaluating item: {e}")
                    # Return item with default scores and justifications
                    return {
                        'query': item.get('query', ''),
                        'answer': item.get('answer', ''),
                        'ground_truth': item.get('ground_truth', ''),
                        'context': item.get('context', []),
                        'LLM Answer Relevancy': 0.5,
                        'LLM Answer Relevancy Justification': f'Error during evaluation: {str(e)}',
                        'LLM Context Relevancy': 0.5,
                        'LLM Context Relevancy Justification': f'Error during evaluation: {str(e)}',
                        'LLM Answer Correctness': 0.5,
                        'LLM Answer Correctness Justification': f'Error during evaluation: {str(e)}'
                    }
        
        # Process all items concurrently with controlled concurrency
        logger.info(f"🔄 Processing {len(data_batch)} items with max {batch_size} concurrent evaluations")
        start_time = time.time()
        
        results = await asyncio.gather(*[evaluate_single_item(item) for item in data_batch], 
                                     return_exceptions=True)
        
        # Handle any exceptions in results
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Exception in item evaluation: {result}")
                final_results.append({
                    'query': '', 'answer': '', 'ground_truth': '', 'context': [],
                    'LLM Answer Relevancy': 0.5,
                    'LLM Answer Relevancy Justification': f'Exception during evaluation: {str(result)}',
                    'LLM Context Relevancy': 0.5,
                    'LLM Context Relevancy Justification': f'Exception during evaluation: {str(result)}',
                    'LLM Answer Correctness': 0.5,
                    'LLM Answer Correctness Justification': f'Exception during evaluation: {str(result)}'
                })
            else:
                final_results.append(result)
        
        eval_time = time.time() - start_time
        logger.info(f"✅ Completed LLM evaluation for {len(final_results)} items in {eval_time:.2f}s")
        return final_results

    async def _return_default_result(self, score: float, justification: str) -> Dict[str, Any]:
        """Helper function to return a default result with score and justification asynchronously"""
        await asyncio.sleep(0)
        return {'score': score, 'justification': justification}
    
    def get_average_scores(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate average scores for LLM metrics"""
        if not results:
            return {}
        
        llm_metrics = ['LLM Answer Relevancy', 'LLM Context Relevancy', 'LLM Answer Correctness']
        averages = {}
        
        for metric in llm_metrics:
            scores = [r.get(metric, 0) for r in results if isinstance(r.get(metric), (int, float))]
            if scores:
                averages[metric] = sum(scores) / len(scores)
                logger.info(f"📊 Average {metric}: {averages[metric]:.4f}")
            else:
                averages[metric] = 0.0
        
        return averages

    # Required abstract methods from BaseEvaluator
    async def evaluate(self, queries: List[str], answers: List[str], ground_truths: List[str], contexts: List[str]) -> tuple:
        """
        Implement the abstract evaluate method from BaseEvaluator.
        This method provides compatibility with the base class interface.
        """
        try:
            logger.info(f"🤖 Starting LLM evaluation for {len(queries)} queries")
            
            # Prepare data for evaluation
            eval_data = []
            for i in range(len(queries)):
                eval_data.append({
                    'query': queries[i] if i < len(queries) else '',
                    'answer': answers[i] if i < len(answers) else '',
                    'ground_truth': ground_truths[i] if i < len(ground_truths) else '',
                    'context': contexts[i] if i < len(contexts) else []
                })
            
            # Run evaluation with async session
            async with aiohttp.ClientSession() as session:
                results_list = await self.evaluate_batch(session, eval_data)
            
            # Convert to DataFrame
            if results_list:
                results_df = pd.DataFrame(results_list)
                averages = self.get_average_scores(results_list)
                logger.info(f"✅ LLM evaluation completed: {len(results_df)} rows")
                return results_df, averages
            else:
                logger.warning("⚠️ No LLM results generated")
                return pd.DataFrame(), {}
                
        except Exception as e:
            logger.error(f"❌ LLM evaluation failed: {e}")
            return pd.DataFrame(), {}

    def process_results(self, results) -> Dict[str, Any]:
        """
        Implement the abstract process_results method from BaseEvaluator.
        This method processes evaluation results and returns summary statistics.
        """
        try:
            if hasattr(results, 'to_dict'):
                # If results is a DataFrame, convert to dict
                results_dict = results.to_dict('records')
            elif isinstance(results, list):
                results_dict = results
            else:
                results_dict = []
            
            # Calculate averages and summary statistics
            averages = self.get_average_scores(results_dict)
            
            summary = {
                'total_queries': len(results_dict),
                'averages': averages,
                'evaluator_type': 'LLM',
                'metrics_included': ['LLM Answer Relevancy', 'LLM Context Relevancy', 'LLM Answer Correctness']
            }
            
            logger.info(f"📊 LLM evaluation summary: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error processing LLM results: {e}")
            return {
                'total_queries': 0,
                'averages': {},
                'evaluator_type': 'LLM',
                'metrics_included': [],
                'error': str(e)
            } 