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
from evaluators.llmEvaluator import LLMEvaluator
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
    
    # Initialize the appropriate async API with fallback handling
    api = None
    get_bot_response_async = None
    
    if config.get('SA'):
        print("🔄 Using SearchAssist (SA) API configuration...")
        try:
            from api.SASearch import AsyncSearchAssistAPI, get_bot_response_async
            api = AsyncSearchAssistAPI()
            print("✅ SearchAssist API initialized successfully")
        except ValueError as e:
            print(f"❌ SearchAssist configuration error: {e}")
            print("⚠️  Continuing with empty responses for all queries")
            api = None
        except Exception as e:
            print(f"❌ SearchAssist initialization failed: {e}")
            print("⚠️  Continuing with empty responses for all queries")
            api = None
    elif config.get('UXO'):
        print("🔄 Using UXO API configuration...")
        try:
            from api.XOSearch import AsyncXOSearchAPI, get_bot_response_async
            api = AsyncXOSearchAPI()
            print("✅ UXO API initialized successfully")
        except ValueError as e:
            print(f"❌ UXO configuration error: {e}")
            print("⚠️  Continuing with empty responses for all queries")
            api = None
        except Exception as e:
            print(f"❌ UXO initialization failed: {e}")
            print("⚠️  Continuing with empty responses for all queries")
            api = None
    else:
        print("❌ No valid API configuration found (SA or UXO)")
        print("⚠️  Continuing with empty responses for all queries")
        api = None
    
    # If API initialization failed, return empty responses for all queries
    if api is None:
        print("🔄 Generating empty responses for all queries due to API initialization failure...")
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
        async with semaphore:
            try:
                result = await get_bot_response_async(api, session, query, ground_truth)
                if result is None:
                    return {"error": "API call returned None - check credentials and configuration", "query": query}
                return result
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
            print(f"Batch {batch_num + 1} completed in {batch_time:.2f} seconds")
            print(f"  ✅ Successful: {successful_count}, ❌ Failed: {failed_count}")
    
    # Print overall summary
    total_successful = sum(1 for r in all_responses if 'error' not in r)
    total_failed = len(all_responses) - total_successful
    success_rate = (total_successful / len(all_responses)) * 100 if all_responses else 0
    
    print(f"\n📊 API Processing Summary:")
    print(f"  Total queries: {len(all_responses)}")
    print(f"  ✅ Successful: {total_successful} ({success_rate:.1f}%)")
    print(f"  ❌ Failed: {total_failed} ({100-success_rate:.1f}%)")
    
    if total_failed > 0:
        print(f"⚠️  {total_failed} queries failed but evaluation will continue with available data")
    
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
        
        # Call search API with error handling
        try:
            responses = await call_search_api_batch(queries, ground_truths, batch_size, max_concurrent)
            
            processing_time = time.time() - start_time
            print(f"API processing completed in {processing_time:.2f} seconds")
            if len(queries) > 0:
                print(f"Average time per query: {processing_time/len(queries):.2f} seconds")
            
        except Exception as api_error:
            print(f"❌ Search API processing failed completely: {api_error}")
            print("⚠️  Generating empty responses for all queries to continue evaluation")
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
        error_count = 0
        
        for response in responses:
            if response is None or (isinstance(response, dict) and 'error' in response):
                answers.append("")
                contexts.append("")
                error_count += 1
            else:
                answers.append(response.get('answer', ''))
                contexts.append(response.get('context', ''))
        
        if error_count > 0:
            print(f"⚠️  {error_count} queries had errors but evaluation will continue with available data")
        
        return queries, answers, ground_truths, contexts
        
    except Exception as e:
        print(f"❌ Critical error in data loading: {e}")
        print("⚠️  Returning minimal data to allow evaluation to continue")
        
        # Return minimal data to prevent complete failure
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
            queries = df.get('query', []).tolist() if 'query' in df.columns else ["sample query"]
            ground_truths = df.get('ground_truth', []).tolist() if 'ground_truth' in df.columns else ["sample ground truth"]
            
            # Fill with empty responses
            answers = [""] * len(queries)
            contexts = [""] * len(queries)
            
            return queries, answers, ground_truths, contexts
        except:
            # Last resort - return dummy data
            return ["sample query"], [""], ["sample ground truth"], [""]

async def evaluate_with_ragas_and_crag(excel_file: str, sheet_name: str, config: Dict,
                                     run_ragas: bool = True, run_crag: bool = True, run_llm: bool = False,
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

        # Initialize results
        ragas_results = pd.DataFrame()
        crag_results = pd.DataFrame()
        llm_results = pd.DataFrame()
        total_set_result = {}

        # Define async evaluation functions for parallel execution
        async def run_ragas_evaluation():
            if not run_ragas:
                print("⏭️ RAGAS evaluation skipped (not enabled)")
                return pd.DataFrame(), {}
            
            print("🚀 Starting RAGAS evaluation...")
            print(f"📊 Data summary: {len(queries)} queries, {len(answers)} answers, {len(ground_truths)} ground truths, {len(contexts)} contexts")
            
            # Check data quality
            non_empty_answers = sum(1 for a in answers if a and str(a).strip())
            non_empty_contexts = sum(1 for c in contexts if c and str(c).strip())
            print(f"📊 Non-empty answers: {non_empty_answers}/{len(answers)}")
            print(f"📊 Non-empty contexts: {non_empty_contexts}/{len(contexts)}")
            
            try:
                ragas_evaluator = RagasEvaluator()
                ragas_eval_result = await ragas_evaluator.evaluate(queries, answers, ground_truths, contexts, model=llm_model)
                
                if isinstance(ragas_eval_result, tuple) and len(ragas_eval_result) == 2:
                    results_df = ragas_eval_result[0]
                    total_result = ragas_eval_result[1].__dict__ if hasattr(ragas_eval_result[1], '__dict__') else {}
                    print(f"✅ RAGAS evaluation completed: {len(results_df)} rows")
                    print(f"✅ RAGAS columns returned: {list(results_df.columns)}")
                    return results_df, total_result
                else:
                    print(f"⚠️ Unexpected RAGAS result format: {type(ragas_eval_result)}")
                    return pd.DataFrame(), {}
                    
            except Exception as e:
                print(f"❌ RAGAS evaluation failed: {e}")
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}")
                return pd.DataFrame(), {}

        async def run_crag_evaluation():
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

        async def run_llm_evaluation():
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

        # Run all evaluations in parallel
        print("🔄 Running evaluations in parallel...")
        start_time = time.time()
        
        results = await asyncio.gather(
            run_ragas_evaluation(),
            run_crag_evaluation(), 
            run_llm_evaluation(),
            return_exceptions=True
        )
        
        parallel_time = time.time() - start_time
        print(f"⚡ Parallel evaluation completed in {parallel_time:.2f} seconds")
        
        # Process results
        ragas_result = results[0] if not isinstance(results[0], Exception) else (pd.DataFrame(), {})
        crag_result = results[1] if not isinstance(results[1], Exception) else pd.DataFrame()
        llm_result = results[2] if not isinstance(results[2], Exception) else (pd.DataFrame(), {})
        
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

        # Return final results
        has_ragas = not ragas_results.empty
        has_crag = not crag_results.empty
        has_llm = not llm_results.empty
        
        print(f"🎯 Final Results Decision:")
        print(f"   has_ragas: {has_ragas} (shape: {ragas_results.shape if not ragas_results.empty else 'empty'})")
        print(f"   has_crag: {has_crag} (shape: {crag_results.shape if not crag_results.empty else 'empty'})")
        print(f"   has_llm: {has_llm} (shape: {llm_results.shape if not llm_results.empty else 'empty'})")
        
        if has_ragas and has_crag and has_llm:
            print("📊 Using combined results (RAGAS + CRAG + LLM)")
            final_results = result_converter.get_combined_results()
        elif has_ragas and has_crag:
            print("📊 Using combined results (RAGAS + CRAG)")
            final_results = result_converter.get_combined_results()
        elif has_ragas and has_llm:
            print("📊 Using combined results (RAGAS + LLM)")
            final_results = result_converter.get_combined_results()
        elif has_crag and has_llm:
            print("📊 Using combined results (CRAG + LLM)")
            final_results = result_converter.get_combined_results()
        elif has_ragas:
            print("📊 Using RAGAS results only")
            final_results = result_converter.get_ragas_results()
        elif has_crag:
            print("📊 Using CRAG results only")
            final_results = result_converter.get_crag_results()
        elif has_llm:
            print("📊 Using LLM results only")
            final_results = result_converter.get_llm_results()
        else:
            # Create a basic DataFrame with the original queries if no evaluation succeeded
            print("⚠️ No evaluation methods succeeded, creating basic results DataFrame")
            basic_data = {
                'query': queries[:len(answers)] if queries else ['No data'],
                'answer': answers if answers else [''],
                'ground_truth': ground_truths[:len(answers)] if ground_truths else [''],
                'context': contexts[:len(answers)] if contexts else [''],
                'evaluation_status': ['No evaluation performed'] * len(answers) if answers else ['No data']
            }
            final_results = pd.DataFrame(basic_data)

        print(f"🎯 Final results summary:")
        print(f"   Shape: {final_results.shape}")
        print(f"   Columns: {list(final_results.columns)}")
        
        return final_results, total_set_result

    except Exception as e:
        print(f"❌ Error in evaluation: {e}")
        print("⚠️ Returning minimal results to prevent complete failure")
        
        # Create minimal results DataFrame to prevent complete failure
        try:
            basic_data = {
                'query': queries[:min(len(queries), len(answers))] if queries else ['Error in evaluation'],
                'answer': answers[:min(len(queries), len(answers))] if answers else [''],
                'ground_truth': ground_truths[:min(len(queries), len(answers))] if ground_truths else [''],
                'context': contexts[:min(len(queries), len(answers))] if contexts else [''],
                'error': [f'Evaluation failed: {str(e)}'] * min(len(queries), len(answers)) if queries and answers else ['Critical evaluation error']
            }
            error_df = pd.DataFrame(basic_data)
            return error_df, {'error': str(e)}
        except:
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
                             batch_size: int, max_concurrent: int) -> Tuple[pd.DataFrame, Dict]:
    """Process a single sheet asynchronously."""
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
             batch_size: int = 10, max_concurrent: int = 5) -> str:
    """Main run function for API usage."""
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()

        # Default to RAGAS evaluation if none specified
        if not evaluate_ragas and not evaluate_crag and not evaluate_llm:
            raise ValueError("At least one evaluation method (RAGAS, CRAG, or LLM) must be selected")

        # Remove the auto-enable LLM logic since LLM can now run standalone
        # if (evaluate_ragas or evaluate_crag) and not evaluate_llm:
        #     evaluate_llm = True
        #     print("🤖 LLM Evaluation automatically enabled alongside RAGAS/CRAG")

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

        # Generate summary
        if successful_sheets == 0:
            return f"⚠️ No sheets processed successfully. Check the output file for error details: {output_file_path}"
        
        success_message = f"✅ Parallel processing completed: {successful_sheets}/{total_sheets} sheets successful"
        if successful_sheets < total_sheets:
            success_message += f" ({total_sheets - successful_sheets} failed)"
        success_message += f"\n⚡ Processing time: {parallel_processing_time:.2f} seconds (parallel execution)"
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
    parser.add_argument('--evaluate_llm', action='store_true', help='Run LLM evaluation')
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
