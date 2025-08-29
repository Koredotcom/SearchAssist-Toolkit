#!/usr/bin/env python3
# Prevent Python from creating .pyc files
import sys
sys.dont_write_bytecode = True

"""
RAG Evaluator - Main Module
===========================
Provides evaluation functionality for RAG systems using RAGAS and CRAG metrics.
"""

import pandas as pd
import os
import argparse
import traceback
from datetime import datetime
from openai import OpenAI
from config.configManager import ConfigManager
from evaluators.ragasEvaluator import RagasEvaluator
from evaluators.cragEvaluator import CragEvaluator
from evaluators.llmEvaluator import LLMEvaluator
from utils.evaluationResult import ResultsConverter
from utils.dbservice import dbService
import asyncio
import aiohttp
from asyncio import Semaphore
from typing import List, Dict, Tuple, Optional
import time

# Constants for configuration defaults
DEFAULT_BATCH_SIZE = 10
DEFAULT_MAX_CONCURRENT = 5
DEFAULT_REQUIRED_COLUMNS = ['query', 'ground_truth', 'context', 'answer']
MINIMAL_REQUIRED_COLUMNS = ['query', 'ground_truth']


class TokenUsageTracker:
    """Tracks and aggregates token usage across different evaluation methods."""
    
    def __init__(self):
        self.total_usage = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'estimated_cost_usd': 0.0
        }
    
    def add_usage(self, usage_data: Dict) -> None:
        """Add token usage data to the total."""
        if not isinstance(usage_data, dict):
            return
            
        for key in self.total_usage:
            if key in usage_data:
                self.total_usage[key] += usage_data[key]
    
    def get_usage(self) -> Dict:
        """Get the current total usage."""
        return self.total_usage.copy()
    
    def has_usage(self) -> bool:
        """Check if any token usage has been recorded."""
        return self.total_usage.get('total_tokens', 0) > 0

async def call_search_api_batch(queries: List[str], ground_truths: List[str], 
                               config: Dict, batch_size: int = DEFAULT_BATCH_SIZE, 
                               max_concurrent: int = DEFAULT_MAX_CONCURRENT) -> List[Dict]:
    """
    Process search API calls asynchronously in batches.
    
    Args:
        queries: List of search queries to process
        ground_truths: Corresponding ground truth answers
        config: Configuration dictionary with API settings
        batch_size: Number of queries to process per batch
        max_concurrent: Maximum concurrent requests allowed
        
    Returns:
        List[Dict]: Results from API calls with error handling
    """
    # Use the provided session-specific config instead of creating a new one
    
    # Initialize the appropriate async API with fallback handling
    api = None
    get_bot_response_async = None
    
    # Check for valid (non-placeholder) API configurations
    sa_config = config.get('SA', {})
    uxo_config = config.get('UXO', {})
    
    def is_valid_api_config(api_conf):
        """Check if API configuration is valid (not a placeholder)."""
        if not isinstance(api_conf, dict):
            return False
        app_id = api_conf.get('app_id', '')
        return app_id and not app_id.startswith('<') and app_id.strip() != ''
    
    sa_valid = is_valid_api_config(sa_config)
    uxo_valid = is_valid_api_config(uxo_config)
    

    
    if sa_valid:
        try:
            from api.SASearch import AsyncSearchAssistAPI, get_bot_response_async
            api = AsyncSearchAssistAPI(config)
        except (ValueError, Exception):
            api = None
    elif uxo_valid:
        try:
            from api.XOSearch import AsyncXOSearchAPI, get_bot_response_async
            api = AsyncXOSearchAPI(config)
        except (ValueError, Exception):
            api = None
    else:
        api = None
    
    # If API initialization failed, return empty responses for all queries
    if api is None:
        empty_responses = []
        for i, (query, ground_truth) in enumerate(zip(queries, ground_truths)):
            empty_responses.append({
                "error": "API configuration failed",
                "query": query,
                "ground_truth": ground_truth,
                "answer": "",
                "context": ""
            })
        return empty_responses
    
    semaphore = Semaphore(max_concurrent)
    
    async def process_single_query(session, query, ground_truth):
        """Process a single query with the search API."""
        async with semaphore:
            try:
                result = await get_bot_response_async(api, session, query, ground_truth)
                if result is None:
                    return {
                        "error": "API call returned None - check credentials and configuration", 
                        "query": query,
                        "ground_truth": ground_truth,
                        "answer": "",
                        "context": ""
                    }
                return result
            except Exception as e:
                return {
                    "error": str(e), 
                    "query": query,
                    "ground_truth": ground_truth,
                    "answer": "",
                    "context": ""
                }
    
    # Process queries in batches
    all_responses = []
    total_batches = (len(queries) + batch_size - 1) // batch_size
    
    async with aiohttp.ClientSession() as session:
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(queries))
            
            batch_queries = queries[start_idx:end_idx]
            batch_ground_truths = ground_truths[start_idx:end_idx]
            

            
            batch_start_time = time.time()
            tasks = [process_single_query(session, q, gt) 
                    for q, gt in zip(batch_queries, batch_ground_truths)]
            
            batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions in responses and count success/failure
            processed_responses = []
            successful_count = 0
            failed_count = 0
            
            for i, response in enumerate(batch_responses):
                if isinstance(response, Exception):
                    processed_responses.append({
                        "error": str(response), 
                        "query": batch_queries[i],
                        "ground_truth": batch_ground_truths[i],
                        "answer": "",
                        "context": ""
                    })
                    failed_count += 1
                elif response is None:
                    processed_responses.append({
                        "error": "API returned None - check configuration", 
                        "query": batch_queries[i],
                        "ground_truth": batch_ground_truths[i],
                        "answer": "",
                        "context": ""
                    })
                    failed_count += 1
                else:
                    processed_responses.append(response)
                    successful_count += 1
            
            all_responses.extend(processed_responses)
            
            batch_time = time.time() - batch_start_time
    
    # Calculate overall summary for logging if needed
    total_successful = sum(1 for r in all_responses if 'error' not in r)
    total_failed = len(all_responses) - total_successful
    
    return all_responses

def load_data(excel_file: str, sheet_name: str) -> Tuple[List[str], List[str], List[str], List[str], List[Dict]]:
    """
    Load data from Excel file with required columns validation.
    
    Args:
        excel_file: Path to the Excel file
        sheet_name: Name of the sheet to load
        
    Returns:
        Tuple containing (queries, answers, ground_truths, contexts)
        
    Raises:
        ValueError: If required columns are missing
        FileNotFoundError: If Excel file doesn't exist
        Exception: Other pandas/openpyxl related errors
    """
    try:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
        
        # Validate required columns
        missing_columns = [col for col in DEFAULT_REQUIRED_COLUMNS if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Create empty chunk statistics for non-search API mode
        chunk_statistics_list = [{}] * len(df)
        
        return (df['query'].tolist(), df['answer'].tolist(), 
                df['ground_truth'].tolist(), df['context'].tolist(), chunk_statistics_list)
    
    except Exception as e:
        raise

async def load_data_and_call_api(excel_file: str, sheet_name: str, config: Dict,
                                batch_size: int = DEFAULT_BATCH_SIZE, 
                                max_concurrent: int = DEFAULT_MAX_CONCURRENT) -> Tuple[List[str], List[str], List[str], List[str], List[Dict]]:
    """
    Load data from Excel and call search API for responses.
    
    Args:
        excel_file: Path to the Excel file
        sheet_name: Name of the sheet to load
        config: Configuration dictionary for API calls
        batch_size: Number of queries to process per batch
        max_concurrent: Maximum concurrent requests allowed
        
    Returns:
        Tuple containing (queries, answers, ground_truths, contexts)
    """
    try:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
        
        missing_columns = [col for col in MINIMAL_REQUIRED_COLUMNS if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        queries = df['query'].tolist()
        ground_truths = df['ground_truth'].tolist()
        
        start_time = time.time()
        
        # Call search API with error handling
        try:
            responses = await call_search_api_batch(queries, ground_truths, config, batch_size, max_concurrent)
            processing_time = time.time() - start_time
            
        except Exception as api_error:
            # Create empty responses for all queries
            responses = []
            for query, ground_truth in zip(queries, ground_truths):
                responses.append({
                    "error": f"API processing failed: {str(api_error)}",
                    "query": query,
                    "ground_truth": ground_truth,
                    "answer": "",
                    "context": ""
                })
        
        # Extract data from responses
        answers, contexts = [], []
        chunk_statistics_list = []
        error_count = 0
        
        for response in responses:
            if response is None or (isinstance(response, dict) and 'error' in response):
                answers.append("")
                contexts.append("")
                chunk_statistics_list.append({})
                error_count += 1
            else:
                answers.append(response.get('answer', ''))
                contexts.append(response.get('context', ''))
                chunk_statistics_list.append(response.get('chunk_statistics', {}))
        

        
        return queries, answers, ground_truths, contexts, chunk_statistics_list
        
    except Exception as e:

        
        # Return minimal data to prevent complete failure
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
            queries = df.get('query', []).tolist() if 'query' in df.columns else ["sample query"]
            ground_truths = df.get('ground_truth', []).tolist() if 'ground_truth' in df.columns else ["sample ground truth"]
            
            # Fill with empty responses
            answers = [""] * len(queries)
            contexts = [""] * len(queries)
            chunk_statistics_list = [{}] * len(queries)
            
            return queries, answers, ground_truths, contexts, chunk_statistics_list
        except:
            # Last resort - return dummy data
            return ["sample query"], [""], ["sample ground truth"], [""], [{}]


async def run_ragas_evaluation(queries: List[str], answers: List[str], 
                              ground_truths: List[str], contexts: List[str], 
                              run_ragas: bool, llm_model: str) -> Tuple[pd.DataFrame, Dict]:
    """Run RAGAS evaluation with error handling."""
    if not run_ragas:
        return pd.DataFrame(), {}
    
    # Check data quality
    non_empty_answers = sum(1 for a in answers if a and str(a).strip())
    non_empty_contexts = sum(1 for c in contexts if c and str(c).strip())
    
    try:
        ragas_evaluator = RagasEvaluator()
        ragas_eval_result = await ragas_evaluator.evaluate(queries, answers, ground_truths, contexts, model=llm_model)
        
        if isinstance(ragas_eval_result, tuple) and len(ragas_eval_result) == 2:
            results_df = ragas_eval_result[0]
            enhanced_result = ragas_eval_result[1]
            
            # Extract token usage information if available
            if isinstance(enhanced_result, dict) and 'token_usage' in enhanced_result:
                token_info = enhanced_result['token_usage']
            else:
                # Fallback to extract from result object if needed
                enhanced_result = enhanced_result.__dict__ if hasattr(enhanced_result, '__dict__') else {}
            
            return results_df, enhanced_result
        else:
            return pd.DataFrame(), {}
            
    except Exception:
        return pd.DataFrame(), {}


async def run_crag_evaluation(queries: List[str], answers: List[str], 
                             ground_truths: List[str], contexts: List[str], 
                             run_crag: bool, config: Dict) -> pd.DataFrame:
    """Run CRAG evaluation with error handling."""
    if not run_crag:
        return pd.DataFrame()
    
    print("🚀 Starting CRAG evaluation...")
    try:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        crag_evaluator = CragEvaluator(config.get('openai', {}).get('model_name', 'gpt-4'), openai_client)
        results_df = crag_evaluator.evaluate(queries, answers, ground_truths, contexts)
        print(f"✅ CRAG evaluation completed: {len(results_df)} rows")
        return results_df
    except Exception as e:
        print(f"❌ CRAG evaluation failed: {e}")
        return pd.DataFrame()


async def run_llm_evaluation(queries: List[str], answers: List[str], 
                           ground_truths: List[str], contexts: List[str], 
                           run_llm: bool, config: Dict) -> Tuple[pd.DataFrame, Dict]:
    """Run LLM evaluation with error handling."""
    if not run_llm:
        return pd.DataFrame(), {}
    
    print("🚀 Starting LLM evaluation...")
    try:
        # Get LLM configuration
        openai_config = config.get('openai', {})
        azure_config = config.get('azure', {})
        
        # Initialize LLM evaluator
        llm_evaluator = LLMEvaluator(openai_config=openai_config, azure_config=azure_config)
        
        # Debug configuration choice
        debug_info = llm_evaluator.debug_configuration()
        print(f"🔍 LLM Evaluator configuration: {debug_info}")
        
        # Use the standard evaluate method from BaseEvaluator
        results_df, llm_averages = await llm_evaluator.evaluate(queries, answers, ground_truths, contexts)
        
        if not results_df.empty:
            print(f"✅ LLM evaluation completed: {len(results_df)} rows")
            return results_df, llm_averages
        else:
            print("⚠️ No LLM results generated")
            return pd.DataFrame(), {}
            
    except Exception as e:
        print(f"❌ LLM evaluation failed: {e}")
        return pd.DataFrame(), {}


def create_basic_results_dataframe(queries: List[str], answers: List[str], 
                                 ground_truths: List[str], contexts: List[str], 
                                 error_message: str = "No evaluation performed") -> pd.DataFrame:
    """Create a basic results DataFrame when no evaluation methods succeed."""
    basic_data = {
        'query': queries[:len(answers)] if queries else ['No data'],
        'answer': answers if answers else [''],
        'ground_truth': ground_truths[:len(answers)] if ground_truths else [''],
        'context': contexts[:len(answers)] if contexts else [''],
        'evaluation_status': [error_message] * len(answers) if answers else ['No data']
    }
    return pd.DataFrame(basic_data)


def determine_final_results(result_converter: ResultsConverter, 
                          has_ragas: bool, has_crag: bool, has_llm: bool) -> pd.DataFrame:
    """Determine which results to return based on available evaluations."""
    print(f"🎯 Final Results Decision:")
    print(f"   has_ragas: {has_ragas}")
    print(f"   has_crag: {has_crag}")
    print(f"   has_llm: {has_llm}")
    
    if has_ragas and has_crag and has_llm:
        print("📊 Using combined results (RAGAS + CRAG + LLM)")
        return result_converter.get_combined_results()
    elif has_ragas and has_crag:
        print("📊 Using combined results (RAGAS + CRAG)")
        return result_converter.get_combined_results()
    elif has_ragas and has_llm:
        print("📊 Using combined results (RAGAS + LLM)")
        return result_converter.get_combined_results()
    elif has_crag and has_llm:
        print("📊 Using combined results (CRAG + LLM)")
        return result_converter.get_combined_results()
    elif has_ragas:
        print("📊 Using RAGAS results only")
        return result_converter.get_ragas_results()
    elif has_crag:
        print("📊 Using CRAG results only")
        return result_converter.get_crag_results()
    elif has_llm:
        print("📊 Using LLM results only")
        return result_converter.get_llm_results()
    else:
        return None

async def evaluate_with_ragas_and_crag(excel_file: str, sheet_name: str, config: Dict,
                                     run_ragas: bool = True, run_crag: bool = True, run_llm: bool = False,
                                     use_search_api: bool = False, llm_model: str = "",
                                     batch_size: int = DEFAULT_BATCH_SIZE, 
                                     max_concurrent: int = DEFAULT_MAX_CONCURRENT) -> Tuple[pd.DataFrame, Dict]:
    """
    Main evaluation function using RAGAS and CRAG.
    
    Args:
        excel_file: Path to the Excel file containing evaluation data
        sheet_name: Name of the sheet to process
        config: Configuration dictionary for evaluators
        run_ragas: Whether to run RAGAS evaluation
        run_crag: Whether to run CRAG evaluation  
        run_llm: Whether to run LLM evaluation
        use_search_api: Whether to use search API for getting responses
        llm_model: LLM model to use for evaluations
        batch_size: Batch size for API calls
        max_concurrent: Maximum concurrent requests
        
    Returns:
        Tuple of (results_dataframe, summary_metrics)
    """
    try:
        # Load data
        if use_search_api:
            queries, answers, ground_truths, contexts, chunk_statistics_list = await load_data_and_call_api(
                excel_file, sheet_name, config, batch_size, max_concurrent)
        else:
            queries, answers, ground_truths, contexts, chunk_statistics_list = load_data(excel_file, sheet_name)

        # Initialize token usage tracker
        token_tracker = TokenUsageTracker()
        total_set_result = {}

        # Run all evaluations in parallel
        print("🔄 Running evaluations in parallel...")
        start_time = time.time()
        
        results = await asyncio.gather(
            run_ragas_evaluation(queries, answers, ground_truths, contexts, run_ragas, llm_model),
            run_crag_evaluation(queries, answers, ground_truths, contexts, run_crag, config), 
            run_llm_evaluation(queries, answers, ground_truths, contexts, run_llm, config),
            return_exceptions=True
        )
        
        parallel_time = time.time() - start_time
        print(f"⚡ Parallel evaluation completed in {parallel_time:.2f} seconds")
        
        # Process results
        ragas_result = results[0] if not isinstance(results[0], Exception) else (pd.DataFrame(), {})
        crag_result = results[1] if not isinstance(results[1], Exception) else pd.DataFrame()
        llm_result = results[2] if not isinstance(results[2], Exception) else (pd.DataFrame(), {})
        
        # Extract token usage information using TokenUsageTracker
        if isinstance(ragas_result, tuple) and len(ragas_result) == 2:
            ragas_df, ragas_metadata = ragas_result
            if isinstance(ragas_metadata, dict) and 'token_usage' in ragas_metadata:
                token_tracker.add_usage(ragas_metadata['token_usage'])
                print(f"💰 RAGAS token usage extracted")
        
        if isinstance(llm_result, tuple) and len(llm_result) == 2:
            llm_df, llm_metadata = llm_result
            if isinstance(llm_metadata, dict) and 'token_usage' in llm_metadata:
                token_tracker.add_usage(llm_metadata['token_usage'])
                print(f"💰 LLM token usage extracted")
        
        # Extract DataFrames and metrics
        if isinstance(ragas_result, tuple) and len(ragas_result) == 2:
            ragas_results, ragas_totals = ragas_result
            total_set_result.update(ragas_totals)
        else:
            ragas_results = ragas_result if isinstance(ragas_result, pd.DataFrame) else pd.DataFrame()
            
        crag_results = crag_result if isinstance(crag_result, pd.DataFrame) else pd.DataFrame()
        
        if isinstance(llm_result, tuple) and len(llm_result) == 2:
            llm_results, llm_totals = llm_result
            total_set_result.update(llm_totals)
        else:
            llm_results = llm_result if isinstance(llm_result, pd.DataFrame) else pd.DataFrame()
        
        # Add token usage to total results
        if token_tracker.has_usage():
            total_set_result['token_usage'] = token_tracker.get_usage()
            print(f"💰 Combined token usage: {token_tracker.get_usage()}")
            
        # Debug RAGAS results
        if not ragas_results.empty:
            print(f"🔍 RAGAS Results Debug:")
            print(f"   Shape: {ragas_results.shape}")
            print(f"   Columns: {list(ragas_results.columns)}")
            print(f"   Sample row: {ragas_results.iloc[0].to_dict() if len(ragas_results) > 0 else 'No data'}")
        else:
            print(f"⚠️ RAGAS Results is empty!")
            
        # Debug CRAG results
        if not crag_results.empty:
            print(f"🔍 CRAG Results Debug:")
            print(f"   Shape: {crag_results.shape}")
            print(f"   Columns: {list(crag_results.columns)}")
        else:
            print(f"⚠️ CRAG Results is empty!")
            
        # Debug LLM results
        if not llm_results.empty:
            print(f"🔍 LLM Results Debug:")
            print(f"   Shape: {llm_results.shape}")
            print(f"   Columns: {list(llm_results.columns)}")
        else:
            print(f"⚠️ LLM Results is empty!")
            
        # Combine results
        result_converter = ResultsConverter(ragas_results, crag_results, llm_results)

        if run_ragas and not ragas_results.empty:
            result_converter.convert_ragas_results()

        if run_crag and not crag_results.empty:
            result_converter.convert_crag_results()

        if run_llm and not llm_results.empty:
            result_converter.convert_llm_results()

        # Determine final results based on available evaluations
        has_ragas = not ragas_results.empty
        has_crag = not crag_results.empty  
        has_llm = not llm_results.empty
        
        print(f"🎯 Results available - RAGAS: {has_ragas}, CRAG: {has_crag}, LLM: {has_llm}")
        
        final_results = determine_final_results(result_converter, has_ragas, has_crag, has_llm)
        
        if final_results is None:
            # Create a basic DataFrame with the original queries if no evaluation succeeded
            print("⚠️ No evaluation methods succeeded, creating basic results DataFrame")
            final_results = create_basic_results_dataframe(queries, answers, ground_truths, contexts)
        
        # Add chunk statistics to the final results
        if chunk_statistics_list and len(chunk_statistics_list) > 0:
            print("📊 Adding chunk statistics to final results...")
            try:
                # Create a DataFrame from chunk statistics
                chunk_stats_df = pd.DataFrame(chunk_statistics_list)
                
                # Ensure the chunk statistics DataFrame has the same number of rows as final_results
                if len(chunk_stats_df) == len(final_results):
                    # Add chunk statistics columns to final results
                    for col in chunk_stats_df.columns:
                        final_results[col] = chunk_stats_df[col].values
                    print(f"✅ Added {len(chunk_stats_df.columns)} chunk statistics columns to final results")
                else:
                    print(f"⚠️ Chunk statistics length ({len(chunk_stats_df)}) doesn't match final results length ({len(final_results)})")
            except Exception as e:
                print(f"⚠️ Error adding chunk statistics: {e}")
        else:
            print("ℹ️ No chunk statistics available to add")

        print(f"🎯 Final results summary:")
        print(f"   Shape: {final_results.shape}")
        print(f"   Columns: {list(final_results.columns)}")
        
        return final_results, total_set_result

    except Exception as e:
        print(f"❌ Error in evaluation: {e}")
        print("⚠️ Returning minimal results to prevent complete failure")
        
        # Create minimal results DataFrame to prevent complete failure
        try:
            # Try to use any loaded data, otherwise use defaults
            safe_queries = queries if 'queries' in locals() else ['Error in evaluation']
            safe_answers = answers if 'answers' in locals() else ['']
            safe_ground_truths = ground_truths if 'ground_truths' in locals() else ['']
            safe_contexts = contexts if 'contexts' in locals() else ['']
            
            return create_basic_results_dataframe(
                safe_queries, safe_answers, safe_ground_truths, safe_contexts, 
                f'Evaluation failed: {str(e)}'
            ), {'error': str(e)}
        except Exception as fallback_error:
            # Last resort
            error_df = pd.DataFrame({
                'query': ['Critical evaluation error'],
                'answer': [''],
                'ground_truth': [''],
                'context': [''],
                'error': [f'Critical evaluation failure: {str(e)}']
            })
            return error_df, {'error': str(e)}

async def process_single_sheet(input_file: str, sheet_name: str, config: Dict,
                             sheet_index: int, total_sheets: int,
                             evaluate_ragas: bool, evaluate_crag: bool, evaluate_llm: bool,
                             use_search_api: bool, llm_model: Optional[str], save_db: bool,
                             batch_size: int = DEFAULT_BATCH_SIZE, 
                             max_concurrent: int = DEFAULT_MAX_CONCURRENT) -> Tuple[pd.DataFrame, Dict]:
    """
    Process a single sheet asynchronously.
    
    Args:
        input_file: Path to the Excel file
        sheet_name: Name of the sheet to process
        config: Configuration dictionary
        sheet_index: Current sheet index for progress tracking
        total_sheets: Total number of sheets being processed
        evaluate_ragas: Whether to run RAGAS evaluation
        evaluate_crag: Whether to run CRAG evaluation
        evaluate_llm: Whether to run LLM evaluation
        use_search_api: Whether to use search API
        llm_model: LLM model to use
        save_db: Whether to save results to database
        batch_size: Batch size for API calls
        max_concurrent: Maximum concurrent requests
        
    Returns:
        Tuple of (results_dataframe, summary_metrics)
    """
    try:
        print(f"🔄 Processing sheet {sheet_index}/{total_sheets}: '{sheet_name}'")
        
        # Call the evaluation function
        results = await evaluate_with_ragas_and_crag(
            input_file, sheet_name, config,
            run_ragas=evaluate_ragas, run_crag=evaluate_crag, run_llm=evaluate_llm,
            use_search_api=use_search_api, llm_model=llm_model,
            batch_size=batch_size, max_concurrent=max_concurrent
        )
        
        if not results or len(results) < 2:
            print(f"⚠️ Invalid results for sheet '{sheet_name}'")
            return None
        
        results_df, total_set_result = results[0], results[1]
        
        if results_df is None or results_df.empty:
            print(f"⚠️ Empty results for sheet '{sheet_name}'")
            return None
        
        # Save to database if requested
        if save_db:
            try:
                db_service = dbService()
                db_service.insert_sheet_result(sheet_name, results_df, total_set_result)
                print(f"✅ Results saved to database for sheet '{sheet_name}'")
            except Exception as db_error:
                print(f"⚠️ Database save failed for sheet '{sheet_name}': {db_error}")
        
        print(f"✨ Completed processing sheet '{sheet_name}': {len(results_df)} rows")
        return results_df, total_set_result
        
    except Exception as sheet_error:
        print(f"❌ Error processing sheet '{sheet_name}': {sheet_error}")
        raise sheet_error


async def run(input_file: str, sheet_name: str = "", evaluate_ragas: bool = False,
             evaluate_crag: bool = False, evaluate_llm: bool = False, use_search_api: bool = False,
             llm_model: Optional[str] = None, save_db: bool = False,
             batch_size: int = DEFAULT_BATCH_SIZE, max_concurrent: int = DEFAULT_MAX_CONCURRENT, 
             session_id: Optional[str] = None, config_data: Optional[Dict] = None) -> str:
    """
    Main run function for API usage with session-specific configuration support.
    
    Args:
        input_file: Path to the Excel file containing evaluation data
        sheet_name: Specific sheet name to process (empty = all sheets)
        evaluate_ragas: Whether to run RAGAS evaluation
        evaluate_crag: Whether to run CRAG evaluation
        evaluate_llm: Whether to run LLM evaluation
        use_search_api: Whether to use search API for responses
        llm_model: LLM model to use for evaluations
        save_db: Whether to save results to database
        batch_size: Batch size for API calls
        max_concurrent: Maximum concurrent requests
        session_id: Session ID for multi-user support
        config_data: In-memory configuration data (secure)
        
    Returns:
        Success/error message string
    """
    total_token_usage = {}  # Initialize token usage tracking
    try:
        # Use in-memory config if provided, otherwise use default
        if config_data:
            print(f"🔒 Using in-memory configuration (secure)")
            config = config_data
        else:
            config_manager = ConfigManager()
            config = config_manager.get_config()
            print(f"🔧 No config provided, using default minimal config")

        # Default to RAGAS evaluation if none specified
        if not evaluate_ragas and not evaluate_crag and not evaluate_llm:
            raise ValueError("At least one evaluation method (RAGAS, CRAG, or LLM) must be selected")

        # Remove the auto-enable LLM logic since LLM can now run standalone
        # if (evaluate_ragas or evaluate_crag) and not evaluate_llm:
        #     evaluate_llm = True
        #     print("🤖 LLM Evaluation automatically enabled alongside RAGAS/CRAG")

        # Enhanced input file validation with debugging
        print(f"🚀 Starting evaluation process...")
        print(f"📄 Input file: {input_file}")
        print(f"📋 Sheet selection: '{sheet_name}' (empty = all sheets)")
        print(f"⚙️ Session ID: {session_id[:8] if session_id else 'None'}")
        
        print(f"🔍 Checking if input file exists: {input_file}")
        if not os.path.exists(input_file):
            print(f"❌ Input file NOT found: {input_file}")
            # List files in the directory to help debug
            input_dir = os.path.dirname(input_file)
            if os.path.exists(input_dir):
                print(f"📂 Files in directory {input_dir}:")
                for file in os.listdir(input_dir):
                    print(f"   - {file}")
            else:
                print(f"❌ Input directory doesn't exist: {input_dir}")
            raise FileNotFoundError(f"Excel file not found: {input_file}")
        else:
            print(f"✅ Input file found: {input_file}")
            print(f"✅ File size: {os.path.getsize(input_file)} bytes")

        # Get sheet names based on user selection
        if sheet_name:
            # Validate that the specified sheet exists in the file
            try:
                excel_file = pd.ExcelFile(input_file, engine='openpyxl')
                available_sheets = excel_file.sheet_names
                excel_file.close()
                
                if sheet_name not in available_sheets:
                    raise ValueError(f"Specified sheet '{sheet_name}' not found in Excel file. Available sheets: {available_sheets}")
                
                sheet_names = [sheet_name]
                print(f"📋 Processing SPECIFIC SHEET: '{sheet_name}' (validated)")
            except Exception as e:
                raise Exception(f"Error validating sheet name: {e}")
        else:
            try:
                sheet_names = pd.ExcelFile(input_file, engine='openpyxl').sheet_names
                print(f"📋 Processing ALL SHEETS: {sheet_names}")
            except Exception as e:
                raise Exception(f"Error reading Excel file: {e}")

        # Setup output file with session-specific directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        if session_id:
            # Use session-specific directory
            from utils.sessionManager import get_session_manager
            session_manager = get_session_manager()
            output_dir = session_manager.get_session_directory(session_id)
            print(f"🔐 Using session-specific output directory: {output_dir}")
        else:
            # Fallback to general outputs directory for backward compatibility
            output_dir = os.path.join(current_dir, "outputs")
            print(f"⚠️ No session ID provided, using general output directory: {output_dir}")
        
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_filename = os.path.splitext(os.path.basename(input_file))[0]
        
        if session_id:
            output_filename = f"{base_filename}_evaluation_output_{session_id[:8]}_{timestamp}.xlsx"
        else:
            output_filename = f"{base_filename}_evaluation_output_{timestamp}.xlsx"
            
        output_file_path = os.path.join(output_dir, output_filename)

        if use_search_api:
            print(f"Using batch processing: batch_size={batch_size}, max_concurrent={max_concurrent}")

        # Process all sheets in parallel
        total_sheets = len(sheet_names)
        print(f"\n🚀 Starting parallel processing of {total_sheets} sheets...")
        
        # Create tasks for parallel processing
        sheet_tasks = []
        for i, sheet in enumerate(sheet_names):
            task = process_single_sheet(
                input_file, sheet, config, i+1, total_sheets,
                evaluate_ragas, evaluate_crag, evaluate_llm,
                use_search_api, llm_model, save_db,
                batch_size, max_concurrent
            )
            sheet_tasks.append(task)
        
        # Execute all sheets in parallel with timing
        start_time = time.time()
        print(f"⚡ Processing {len(sheet_tasks)} sheets concurrently...")
        sheet_results = await asyncio.gather(*sheet_tasks, return_exceptions=True)
        parallel_processing_time = time.time() - start_time
        print(f"🏁 Parallel processing completed in {parallel_processing_time:.2f} seconds")
        
        # Process results and write to Excel
        successful_sheets = 0
        processed_sheets = []
        
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            for i, (sheet_name, result) in enumerate(zip(sheet_names, sheet_results)):
                if isinstance(result, Exception):
                    print(f"❌ Error processing sheet '{sheet_name}': {result}")
                    # Create error sheet
                    error_df = pd.DataFrame({
                        'query': ['Processing failed'],
                        'answer': [''],
                        'ground_truth': [''],
                        'context': [''],
                        'error': [f'Error: {str(result)}']
                    })
                    error_df.to_excel(writer, sheet_name=f"{sheet_name}_error", index=False)
                    continue
                
                if result is None or not result:
                    print(f"⚠️ No results for sheet '{sheet_name}', creating empty result")
                    empty_df = pd.DataFrame({
                        'query': ['No data processed'],
                        'answer': [''],
                        'ground_truth': [''],
                        'context': [''],
                        'error': [f'No results generated for sheet {sheet_name}']
                    })
                    empty_df.to_excel(writer, sheet_name=f"{sheet_name}_empty", index=False)
                    continue
                
                # Unpack results
                results_df, total_set_result = result[0], result[1]
                
                if results_df is None or results_df.empty:
                    print(f"⚠️ Empty results for sheet '{sheet_name}', creating empty result")
                    empty_df = pd.DataFrame({
                        'query': ['No data processed'],
                        'answer': [''],
                        'ground_truth': [''],
                        'context': [''],
                        'error': [f'Empty results for sheet {sheet_name}']
                    })
                    empty_df.to_excel(writer, sheet_name=f"{sheet_name}_empty", index=False)
                    continue
                
                # Write successful results to Excel
                results_df.to_excel(writer, sheet_name=sheet_name, index=False)
                successful_sheets += 1
                processed_sheets.append(sheet_name)
                
                print(f"✅ Sheet '{sheet_name}' processed successfully: {len(results_df)} rows")
            
            # Ensure at least one sheet exists to prevent openpyxl error
            if successful_sheets == 0:
                print("⚠️ No sheets processed successfully, creating summary sheet")
                summary_df = pd.DataFrame({
                    'status': ['All sheets failed to process'],
                    'total_sheets': [total_sheets],
                    'successful_sheets': [0],
                    'recommendation': ['Check configuration and try again']
                })
                summary_df.to_excel(writer, sheet_name="Processing_Summary", index=False)

        # Add output file to session manager if session_id provided
        if session_id and os.path.exists(output_file_path):
            session_manager.add_output_file(session_id, output_file_path)
            print(f"📂 Output file registered with session {session_id[:8]}...")
        
        # Generate summary
        if successful_sheets == 0:
            return f"⚠️ No sheets processed successfully. Check the output file for error details: {output_file_path}"
        
        success_message = f"✅ Parallel processing completed: {successful_sheets}/{total_sheets} sheets successful"
        if successful_sheets < total_sheets:
            success_message += f" ({total_sheets - successful_sheets} failed)"
        success_message += f"\n⚡ Processing time: {parallel_processing_time:.2f} seconds (parallel execution)"
        success_message += f"\n📁 Output file: {output_file_path}"
        success_message += f"\n📊 File size: {os.path.getsize(output_file_path):,} bytes"
        
        # Include token usage information if available
        if 'token_usage' in locals() and total_token_usage and 'total_tokens' in total_token_usage:
            success_message += f"\n💰 Total Tokens for Evaluation: Input={total_token_usage.get('prompt_tokens', 0)} Output={total_token_usage.get('completion_tokens', 0)}"
            if 'estimated_cost_usd' in total_token_usage:
                success_message += f"\n💰 Total Cost in $: {total_token_usage['estimated_cost_usd']}"
        
        return success_message

    except Exception as e:
        error_message = f"❌ Critical error: {e}"
        print(error_message)
        traceback.print_exc()
        return error_message

def run_sync(*args, **kwargs):
    """Synchronous wrapper for the async run function."""
    return asyncio.run(run(*args, **kwargs))

async def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(description='RAG Evaluation Tool')
    parser.add_argument('--input_file', type=str, required=True, help='Input Excel file path')
    parser.add_argument('--sheet_name', type=str, help='Specific sheet name (default: all sheets)')
    parser.add_argument('--evaluate_ragas', action='store_true', help='Run RAGAS evaluation')
    parser.add_argument('--evaluate_crag', action='store_true', help='Run CRAG evaluation')
    parser.add_argument('--evaluate_llm', action='store_true', help='Run LLM evaluation')
    parser.add_argument('--use_search_api', action='store_true', help='Use search API for responses')
    parser.add_argument('--llm_model', type=str, help='LLM model for evaluation')
    parser.add_argument('--save_db', action='store_true', help='Save results to database')
    parser.add_argument('--batch_size', type=int, default=DEFAULT_BATCH_SIZE, help='Batch size for API calls')
    parser.add_argument('--max_concurrent', type=int, default=DEFAULT_MAX_CONCURRENT, help='Max concurrent requests')
    
    args = parser.parse_args()
    
    result = await run(
        input_file=args.input_file,
        sheet_name=args.sheet_name or "",
        evaluate_ragas=args.evaluate_ragas,
        evaluate_crag=args.evaluate_crag,
        evaluate_llm=args.evaluate_llm,
        use_search_api=args.use_search_api,
        llm_model=args.llm_model,
        save_db=args.save_db,
        batch_size=args.batch_size,
        max_concurrent=args.max_concurrent
    )
    
    print(f"\n{result}")

if __name__ == "__main__":
    asyncio.run(main())
