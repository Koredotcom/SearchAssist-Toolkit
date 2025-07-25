#!/usr/bin/env python3
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
from utils.evaluationResult import ResultsConverter
from utils.dbservice import dbService
import asyncio
import aiohttp
from asyncio import Semaphore
from typing import List, Dict, Tuple, Optional
import time

async def call_search_api_batch(queries: List[str], ground_truths: List[str], 
                               batch_size: int = 10, max_concurrent: int = 5) -> List[Dict]:
    """Process search API calls asynchronously in batches."""
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # Initialize the appropriate async API
    if config.get('SA'):
        from api.SASearch import AsyncSearchAssistAPI, get_bot_response_async
        api = AsyncSearchAssistAPI()
    elif config.get('UXO'):
        from api.XOSearch import AsyncXOSearchAPI, get_bot_response_async
        api = AsyncXOSearchAPI()
    else:
        raise ValueError("No valid API configuration found (SA or UXO)")
    
    semaphore = Semaphore(max_concurrent)
    
    async def process_single_query(session, query, ground_truth):
        async with semaphore:
            try:
                return await get_bot_response_async(api, session, query, ground_truth)
            except Exception as e:
                print(f"Error processing query: {str(e)}")
                return {"error": str(e), "query": query}
    
    # Process queries in batches
    all_responses = []
    total_batches = (len(queries) + batch_size - 1) // batch_size
    
    async with aiohttp.ClientSession() as session:
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(queries))
            
            batch_queries = queries[start_idx:end_idx]
            batch_ground_truths = ground_truths[start_idx:end_idx]
            
            print(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_queries)} queries)")
            
            batch_start_time = time.time()
            tasks = [process_single_query(session, q, gt) 
                    for q, gt in zip(batch_queries, batch_ground_truths)]
            
            batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions in responses
            processed_responses = []
            for response in batch_responses:
                if isinstance(response, Exception):
                    processed_responses.append({"error": str(response)})
                else:
                    processed_responses.append(response)
            
            all_responses.extend(processed_responses)
            
            batch_time = time.time() - batch_start_time
            print(f"Batch {batch_num + 1} completed in {batch_time:.2f} seconds")
    
    return all_responses

def load_data(excel_file: str, sheet_name: str) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Load data from Excel file."""
    try:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
        
        # Validate required columns
        required_columns = ['query', 'ground_truth', 'context', 'answer']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        return (df['query'].tolist(), df['answer'].tolist(), 
                df['ground_truth'].tolist(), df['context'].tolist())
    
    except Exception as e:
        print(f"Error loading data from {excel_file}, sheet '{sheet_name}': {e}")
        raise

async def load_data_and_call_api(excel_file: str, sheet_name: str, config: Dict,
                                batch_size: int = 10, max_concurrent: int = 5) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Load data and call search API for responses."""
    try:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
        
        required_columns = ['query', 'ground_truth']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        queries = df['query'].tolist()
        ground_truths = df['ground_truth'].tolist()
        
        print(f"Starting API processing for {len(queries)} queries")
        start_time = time.time()
        
        # Call search API
        responses = await call_search_api_batch(queries, ground_truths, batch_size, max_concurrent)
        
        processing_time = time.time() - start_time
        print(f"API processing completed in {processing_time:.2f} seconds")
        print(f"Average time per query: {processing_time/len(queries):.2f} seconds")
        
        # Extract data from responses
        answers, contexts = [], []
        for response in responses:
            if 'error' in response:
                answers.append("")
                contexts.append("")
            else:
                answers.append(response.get('answer', ''))
                contexts.append(response.get('context', ''))
        
        return queries, answers, ground_truths, contexts
        
    except Exception as e:
        print(f"Error in API processing: {e}")
        raise

async def evaluate_with_ragas_and_crag(excel_file: str, sheet_name: str, config: Dict,
                                     run_ragas: bool = True, run_crag: bool = True,
                                     use_search_api: bool = False, llm_model: str = "",
                                     batch_size: int = 10, max_concurrent: int = 5) -> Tuple[pd.DataFrame, Dict]:
    """Main evaluation function using RAGAS and CRAG."""
    try:
        # Load data
        if use_search_api:
            queries, answers, ground_truths, contexts = await load_data_and_call_api(
                excel_file, sheet_name, config, batch_size, max_concurrent)
        else:
            queries, answers, ground_truths, contexts = load_data(excel_file, sheet_name)

        ragas_results = pd.DataFrame()
        crag_results = pd.DataFrame()
        total_set_result = {}

        # Run RAGAS evaluation
        if run_ragas:
            print("Starting RAGAS evaluation...")
            ragas_evaluator = RagasEvaluator()
            ragas_eval_result = await ragas_evaluator.evaluate(queries, answers, ground_truths, contexts, model=llm_model)
            ragas_results = ragas_eval_result[0]
            total_set_result = ragas_eval_result[1].__dict__ if len(ragas_eval_result) > 1 else {}

        # Run CRAG evaluation
        if run_crag:
            print("Starting CRAG evaluation...")
            openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            crag_evaluator = CragEvaluator(config.get('openai', {}).get('model_name', 'gpt-4'), openai_client)
            crag_results = crag_evaluator.evaluate(queries, answers, ground_truths, contexts)
            
        # Combine results
        result_converter = ResultsConverter(ragas_results, crag_results)

        if run_ragas and not ragas_results.empty:
            result_converter.convert_ragas_results()

        if run_crag and not crag_results.empty:
            result_converter.convert_crag_results()

        # Return final results
        if not ragas_results.empty and not crag_results.empty:
            final_results = result_converter.get_combined_results()
        elif not ragas_results.empty:
            final_results = result_converter.get_ragas_results()
        elif not crag_results.empty:
            final_results = result_converter.get_crag_results()
        else:
            final_results = pd.DataFrame()

        return final_results, total_set_result

    except Exception as e:
        print(f"Error in evaluation: {e}")
        traceback.print_exc()
        raise

async def run(input_file: str, sheet_name: str = "", evaluate_ragas: bool = False,
             evaluate_crag: bool = False, use_search_api: bool = False,
             llm_model: Optional[str] = None, save_db: bool = False,
             batch_size: int = 10, max_concurrent: int = 5) -> str:
    """Main run function for API usage."""
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()

        # Default to both evaluations if none specified
        if not evaluate_ragas and not evaluate_crag:
            evaluate_ragas = evaluate_crag = True

        # Get sheet names
        if sheet_name:
            sheet_names = [sheet_name]
        else:
            try:
                sheet_names = pd.ExcelFile(input_file, engine='openpyxl').sheet_names
            except Exception as e:
                raise Exception(f"Error reading Excel file: {e}")

        # Setup output file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_dir, "outputs")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_filename = os.path.splitext(os.path.basename(input_file))[0]
        output_filename = f"{base_filename}_evaluation_output_{timestamp}.xlsx"
        output_file_path = os.path.join(output_dir, output_filename)

        if use_search_api:
            print(f"Using batch processing: batch_size={batch_size}, max_concurrent={max_concurrent}")

        # Process all sheets
        successful_sheets = 0
        total_sheets = len(sheet_names)
        
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            for i, sheet in enumerate(sheet_names, 1):
                print(f"\nProcessing sheet {i}/{total_sheets}: '{sheet}'")
                
                try:
                    results = await evaluate_with_ragas_and_crag(
                        input_file, sheet, config,
                        run_ragas=evaluate_ragas, run_crag=evaluate_crag,
                        use_search_api=use_search_api, llm_model=llm_model,
                        batch_size=batch_size, max_concurrent=max_concurrent
                    )
                    
                    if not results or len(results) < 2:
                        raise ValueError(f"Invalid results for sheet '{sheet}'")
                    
                    results_df, total_set_result = results[0], results[1]
                    
                    if results_df is None or results_df.empty:
                        print(f"Warning: No results for sheet '{sheet}'")
                        continue
                    
                    # Write to Excel
                    results_df.to_excel(writer, sheet_name=sheet, index=False)
                    successful_sheets += 1
                    
                    print(f"✅ Sheet '{sheet}' processed successfully: {len(results_df)} rows")
                    
                    # Save to database if requested
                    if save_db:
                        try:
                            db_service = dbService()
                            db_service.insert_sheet_result(sheet, results_df, total_set_result)
                            print(f"✅ Results saved to database for sheet '{sheet}'")
                        except Exception as db_error:
                            print(f"⚠️ Database save failed for sheet '{sheet}': {db_error}")
                    
                except Exception as sheet_error:
                    print(f"❌ Error processing sheet '{sheet}': {sheet_error}")
                    continue

        # Generate summary
        if successful_sheets == 0:
            return f"❌ No sheets processed successfully. Output file: {output_file_path}"
        
        success_message = f"✅ Processing completed: {successful_sheets}/{total_sheets} sheets successful"
        if successful_sheets < total_sheets:
            success_message += f" ({total_sheets - successful_sheets} failed)"
        success_message += f"\n📁 Output file: {output_file_path}"
        success_message += f"\n📊 File size: {os.path.getsize(output_file_path):,} bytes"
        
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
    parser.add_argument('--use_search_api', action='store_true', help='Use search API for responses')
    parser.add_argument('--llm_model', type=str, help='LLM model for evaluation')
    parser.add_argument('--save_db', action='store_true', help='Save results to database')
    parser.add_argument('--batch_size', type=int, default=10, help='Batch size for API calls')
    parser.add_argument('--max_concurrent', type=int, default=5, help='Max concurrent requests')
    
    args = parser.parse_args()
    
    result = await run(
        input_file=args.input_file,
        sheet_name=args.sheet_name or "",
        evaluate_ragas=args.evaluate_ragas,
        evaluate_crag=args.evaluate_crag,
        use_search_api=args.use_search_api,
        llm_model=args.llm_model,
        save_db=args.save_db,
        batch_size=args.batch_size,
        max_concurrent=args.max_concurrent
    )
    
    print(f"\n{result}")

if __name__ == "__main__":
    asyncio.run(main())
