import pandas as pd
import os
import argparse
import traceback
import asyncio
import time
from datetime import datetime
from openai import OpenAI
from config.configManager import ConfigManager
from evaluators.ragasEvaluator import RagasEvaluator
from evaluators.cragEvaluator import CragEvaluator
from utils.evaluationResult import ResultsConverter
from utils.dbservice import dbService

# Import optimized write functions
from utils.optimized_writer import unified_api_write, conditional_write_results, update_results_in_memory
from utils.batch_processor import process_sheets_with_batch_processor

# Import async API functions
from async_api_calls import call_search_api_async

def call_search_api(queries, ground_truths):
    config_manager = ConfigManager()
    config = config_manager.get_config()    
    if config.get('SA'):
        from api.SASearch import SearchAssistAPI, get_bot_response
        api = SearchAssistAPI()
    elif config.get('UXO'):
        from api.XOSearch import XOSearchAPI, get_bot_response
        api = XOSearchAPI()
        
    results = []
    for query, truth in zip(queries, ground_truths):
        response = get_bot_response(api, query, truth)
        if response:
            results.append(response)
        else:
            results.append({
                'query': query,
                'ground_truth': truth,
                'context': [],
                'context_url': '',
                'answer': "Failed to get response"
            })
    return results


async def call_search_api_async_wrapper(queries, ground_truths, max_concurrent=3):
    """
    Async wrapper for search API calls with configurable concurrency limit
    
    Args:
        queries: List of search queries
        ground_truths: List of ground truths
        max_concurrent: Maximum number of concurrent API calls (default: 10)
    """
    config_manager = ConfigManager()
    config = config_manager.get_config()
    # Determine API type based on config
    api_type = 'UXO'  # default
    if config.get('SA'):
        api_type = 'SA'
    elif config.get('UXO'):
        api_type = 'UXO'
    
    return await call_search_api_async(queries, ground_truths, api_type, max_concurrent)


def load_data_and_call_api(excel_file, sheet_name, config):
    df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
    queries = df['query'].fillna('').tolist()
    ground_truths = df['ground_truth'].fillna('').tolist()

    api_results = call_search_api(queries, ground_truths)

    # Create a new DataFrame with API results
    results_df = pd.DataFrame(api_results)
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    relative_output_dir = os.path.join(current_file_dir, "outputs", "sa_api_outputs")
    os.makedirs(relative_output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_filename = os.path.splitext(os.path.basename(excel_file))[0]
    output_filename = f"{base_filename}_sa_api_results_{timestamp}.xlsx"
    output_file_path = os.path.join(relative_output_dir, output_filename)
    results_df.to_excel(output_file_path, index=False)

    print(f"API results saved to {output_file_path}")

    # Return the data in the format expected by the evaluators
    return (
        results_df['query'].tolist(),
        results_df['answer'].tolist(),
        results_df['ground_truth'].tolist(),
        results_df['context'].tolist()
    )


async def load_data_and_call_api_async(excel_file, sheet_name, config):
    """
    Async version of load_data_and_call_api with timing
    """
    start_time = time.time()
    
    df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
    queries = df['query'].fillna('').tolist()
    ground_truths = df['ground_truth'].fillna('').tolist()

    print(f"🔄 Starting Search API calls for {len(queries)} queries...")
    api_start_time = time.time()
    
    api_results = await call_search_api_async_wrapper(queries, ground_truths)
    api_end_time = time.time()
    api_duration = api_end_time - api_start_time

    
    
    print(f"✅ Search API calls completed in {api_duration:.2f} seconds")
    print(f"📊 Average time per query: {api_duration/len(queries):.2f} seconds")

    # Create a new DataFrame with API results
    results_df = pd.DataFrame(api_results)
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    relative_output_dir = os.path.join(current_file_dir, "outputs", "sa_api_outputs")
    os.makedirs(relative_output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_filename = os.path.splitext(os.path.basename(excel_file))[0]
    output_filename = f"{base_filename}_async_sa_api_results_{timestamp}.xlsx"
    output_file_path = os.path.join(relative_output_dir, output_filename)
    results_df.to_excel(output_file_path, index=False)

    print(f"Async API results saved to {output_file_path}")

    # Return the data in the format expected by the evaluators
    return (
        results_df['query'].tolist(),
        results_df['answer'].tolist(),
        results_df['ground_truth'].tolist(),
        results_df['context'].tolist()
    ), api_duration


def load_data(excel_file, sheet_name):
    if sheet_name:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
    else:
        df = pd.read_excel(excel_file, engine='openpyxl')

    queries = df['query'].fillna('').tolist()
    ground_truths = df['ground_truth'].fillna('').tolist()
    contexts = df['contexts'].fillna('[]').apply(eval).tolist()
    answers = df['answer'].fillna('').tolist()

    return queries, answers, ground_truths, contexts


async def evaluate_with_ragas_and_crag_async(excel_file, sheet_name, config, run_ragas=True, run_crag=True, use_search_api=False, llm_model="", use_async_ragas=False):
    """
    Async version of evaluate_with_ragas_and_crag with optional async Ragas and timing
    """
    pipeline_start_time = time.time()
    search_api_time = 0
    ragas_time = 0
    crag_time = 0
    
    try:
        if use_search_api:
            print(f"🔄 Loading data and calling Search API...")
            data_result = await load_data_and_call_api_async(excel_file, sheet_name, config)
            queries, answers, ground_truths, contexts = data_result[0]
            print('quiries: ', queries)
            print('answers: ', answers)
            print('ground_truths: ', ground_truths)
            search_api_time = data_result[1]
        else:
            queries, answers, ground_truths, contexts = load_data(excel_file, sheet_name)

        ragas_results = pd.DataFrame([])
        crag_results = pd.DataFrame([])
        total_set_result = {}  # Initialize as empty dict instead of None

        if run_ragas:
            print("🔄 Running Ragas evaluation...")
            ragas_start_time = time.time()
            
            if use_async_ragas:
                print("🔄 Running Ragas evaluation asynchronously...")
                from evaluators.asyncRagasEvaluator import AsyncRagasEvaluator
                ragas_evaluator = AsyncRagasEvaluator()
                ragas_eval_result = await ragas_evaluator.evaluate_async(queries, answers, ground_truths, contexts, model=llm_model)
            else:
                print("🔄 Running Ragas evaluation synchronously...")
                from evaluators.ragasEvaluator import RagasEvaluator
                ragas_evaluator = RagasEvaluator()
                ragas_eval_result = ragas_evaluator.evaluate(queries, answers, ground_truths, contexts, model=llm_model)
            
            ragas_end_time = time.time()
            print('ragas_eval_result: ', ragas_eval_result)
            ragas_time = ragas_end_time - ragas_start_time
            print(f"✅ Ragas evaluation completed in {ragas_time:.2f} seconds")
            
            ragas_results = ragas_eval_result[0]  # DataFrame
            total_set_result = ragas_eval_result[1].__dict__ if len(ragas_eval_result) > 1 else {}  # Convert result object to dict

        if run_crag:
            print("🔄 Running Crag evaluation...")
            crag_start_time = time.time()
            
            openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            crag_evaluator = CragEvaluator(config['openai']['model_name'], openai_client)
            crag_results = crag_evaluator.evaluate(queries, answers, ground_truths, contexts)
            
            crag_end_time = time.time()
            crag_time = crag_end_time - crag_start_time
            print(f"✅ Crag evaluation completed in {crag_time:.2f} seconds")
            
        result_converter = ResultsConverter(ragas_results, crag_results)

        if run_ragas:
            result_converter.convert_ragas_results()

        if run_crag:
            result_converter.convert_crag_results()

        # Single return point based on review feedback
        final_results = pd.DataFrame([])
        if len(ragas_results.index) > 0 and len(crag_results.index) > 0:
            final_results = result_converter.get_combined_results()
        elif len(ragas_results.index) > 0:
            final_results = result_converter.get_ragas_results()
        elif len(crag_results.index) > 0:
            final_results = result_converter.get_crag_results()
        
        # Calculate total pipeline time
        pipeline_end_time = time.time()
        total_pipeline_time = pipeline_end_time - pipeline_start_time
        
        # Print timing summary
        print("\n⏱️  TIMING SUMMARY")
        print("=" * 50)
        if use_search_api:
            print(f"🔍 Search API Calls: {search_api_time:.2f}s")
        if run_ragas:
            print(f"📊 Ragas Evaluation: {ragas_time:.2f}s")
        if run_crag:
            print(f"🎯 Crag Evaluation: {crag_time:.2f}s")
        print(f"🚀 Total Pipeline Time: {total_pipeline_time:.2f}s")
        
        # Calculate percentages
        if total_pipeline_time > 0:
            if use_search_api:
                search_percent = (search_api_time / total_pipeline_time) * 100
                print(f"   📈 Search API: {search_percent:.1f}% of total time")
            if run_ragas:
                ragas_percent = (ragas_time / total_pipeline_time) * 100
                print(f"   📈 Ragas: {ragas_percent:.1f}% of total time")
            if run_crag:
                crag_percent = (crag_time / total_pipeline_time) * 100
                print(f"   📈 Crag: {crag_percent:.1f}% of total time")
        
        return final_results, total_set_result
        
    except Exception as e:
        print("Encountered error while running evaluation: ", traceback.format_exc())
        return pd.DataFrame([]), {}


def evaluate_with_ragas_and_crag(excel_file, sheet_name, config, run_ragas=True, run_crag=True, use_search_api=False, llm_model=""):
    """
    Synchronous version with timing
    """
    pipeline_start_time = time.time()
    search_api_time = 0
    ragas_time = 0
    crag_time = 0
    
    try:
        if use_search_api:
            print(f"🔄 Loading data and calling Search API...")
            search_start_time = time.time()
            queries, answers, ground_truths, contexts = load_data_and_call_api(excel_file, sheet_name, config)
            search_end_time = time.time()
            search_api_time = search_end_time - search_start_time
            print(f"✅ Search API calls completed in {search_api_time:.2f} seconds")
        else:
            queries, answers, ground_truths, contexts = load_data(excel_file, sheet_name)

        ragas_results = pd.DataFrame([])
        crag_results = pd.DataFrame([])
        total_set_result = {}  # Initialize as empty dict instead of None

        if run_ragas:
            print("🔄 Running Ragas evaluation...")
            ragas_start_time = time.time()
            ragas_evaluator = RagasEvaluator()
            ragas_eval_result = ragas_evaluator.evaluate(queries, answers, ground_truths, contexts, model=llm_model)
            ragas_end_time = time.time()
            ragas_time = ragas_end_time - ragas_start_time
            print(f"✅ Ragas evaluation completed in {ragas_time:.2f} seconds")
            
            ragas_results = ragas_eval_result[0]  # DataFrame
            total_set_result = ragas_eval_result[1].__dict__ if len(ragas_eval_result) > 1 else {}  # Convert result object to dict

        if run_crag:
            print("🔄 Running Crag evaluation...")
            crag_start_time = time.time()
            openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            crag_evaluator = CragEvaluator(config['openai']['model_name'], openai_client)
            crag_results = crag_evaluator.evaluate(queries, answers, ground_truths, contexts)
            crag_end_time = time.time()
            crag_time = crag_end_time - crag_start_time
            print(f"✅ Crag evaluation completed in {crag_time:.2f} seconds")
            
        result_converter = ResultsConverter(ragas_results, crag_results)

        if run_ragas:
            result_converter.convert_ragas_results()

        if run_crag:
            result_converter.convert_crag_results()

        # Single return point based on review feedback
        final_results = pd.DataFrame([])
        if len(ragas_results.index) > 0 and len(crag_results.index) > 0:
            combined_results = result_converter.get_combined_results()
            return combined_results, total_set_result if 'total_set_result' in locals() else {}
        elif len(ragas_results.index) > 0:
            return result_converter.get_ragas_results(), total_set_result if 'total_set_result' in locals() else {}   
        elif len(crag_results.index) > 0:
            final_results = result_converter.get_crag_results()
            return final_results, {}
        
        # Calculate total pipeline time
        pipeline_end_time = time.time()
        total_pipeline_time = pipeline_end_time - pipeline_start_time
        
        # Print timing summary
        print("\n⏱️  TIMING SUMMARY")
        print("=" * 50)
        if use_search_api:
            print(f"🔍 Search API Calls: {search_api_time:.2f}s")
        if run_ragas:
            print(f"📊 Ragas Evaluation: {ragas_time:.2f}s")
        if run_crag:
            print(f"🎯 Crag Evaluation: {crag_time:.2f}s")
        print(f"🚀 Total Pipeline Time: {total_pipeline_time:.2f}s")
        
        # Calculate percentages
        if total_pipeline_time > 0:
            if use_search_api:
                search_percent = (search_api_time / total_pipeline_time) * 100
                print(f"   📈 Search API: {search_percent:.1f}% of total time")
            if run_ragas:
                ragas_percent = (ragas_time / total_pipeline_time) * 100
                print(f"   📈 Ragas: {ragas_percent:.1f}% of total time")
            if run_crag:
                crag_percent = (crag_time / total_pipeline_time) * 100
                print(f"   📈 Crag: {crag_percent:.1f}% of total time")
        
        return pd.DataFrame([]), {}
        
    except Exception as e:
        print("Encountered error while running evaluation: ", traceback.format_exc())
        return pd.DataFrame([]), {}


def add_context_relevancy_to_output(output_file_path, model_type="openai", sheet_name=None):
    """
    Add context relevancy scores to the existing Ragas output file.
    
    Args:
        output_file_path: Path to the Ragas output Excel file
        model_type: "openai" or "azure" to specify which model to use
        sheet_name: Optional sheet name to filter results for context relevancy.
    """
    try:
        if sheet_name:
            print(f"🔄 Adding Context Relevancy to sheet '{sheet_name}' in output file: {output_file_path}")
        else:
            print(f"🔄 Adding Context Relevancy to output file: {output_file_path}")
        
        # Check if output file exists
        if not os.path.exists(output_file_path):
            print(f"❌ Output file not found: {output_file_path}")
            return False
        
        # Check file size with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            file_size = os.path.getsize(output_file_path)
            print(f"📊 File size (attempt {attempt + 1}): {file_size} bytes")
            
            if file_size > 0:
                break
            elif attempt < max_retries - 1:
                print(f"⚠️  File is empty, waiting 2 seconds before retry...")
                import time as time_module
                time_module.sleep(2)
            else:
                print(f"❌ File is still empty after {max_retries} attempts")
                return False
        
        # Import the check_relevance functionality
        from check_relevance import extract_data_from_ragas_output, evaluate_relevance_batch, setup_openai_client, get_model_from_config
        
        # Extract data from the Ragas output file for specific sheet
        data_df = extract_data_from_ragas_output(output_file_path, sheet_name)
        
        if data_df is None:
            if sheet_name:
                print(f"❌ Failed to extract data from Ragas output file for sheet '{sheet_name}'")
            else:
                print("❌ Failed to extract data from Ragas output file")
            return False
            
        # Evaluate context relevancy for this sheet
        if sheet_name:
            print(f"🔄 Evaluating context relevancy for sheet '{sheet_name}' using {model_type.upper()}...")
        else:
            print(f"🔄 Evaluating context relevancy for existing data using {model_type.upper()}...")
        results_df = evaluate_relevance_batch(data_df, output_file=None, model_type=model_type)  # Don't save to new file
        
        if results_df is None:
            if sheet_name:
                print(f"❌ Failed to evaluate context relevancy for sheet '{sheet_name}'")
            else:
                print("❌ Failed to evaluate context relevancy")
            return False
        
        # Read the original output file with error handling
        try:
            original_df = pd.read_excel(output_file_path, sheet_name=sheet_name if sheet_name else 0, engine='openpyxl')
        except Exception as read_error:
            print(f"❌ Error reading original file: {str(read_error)}")
            print(f"Trying alternative reading method...")
            try:
                original_df = pd.read_excel(output_file_path, sheet_name=sheet_name if sheet_name else 0)
            except Exception as alt_read_error:
                print(f"❌ Alternative reading method also failed: {str(alt_read_error)}")
                return False
        
        # Add context relevancy scores to the original DataFrame
        if 'relevance_score' in results_df.columns:
            # Match rows by query to add context relevancy scores
            relevancy_scores = []
            for _, original_row in original_df.iterrows():
                query = original_row.get('user_input', '')
                # Find matching row in results
                matching_row = results_df[results_df['query'] == query]
                if not matching_row.empty:
                    relevancy_scores.append(matching_row.iloc[0]['relevance_score'])
                else:
                    relevancy_scores.append(-1)  # No match found
            
            original_df['context_relevancy'] = relevancy_scores
            
            # Save back to the same file with sheet name
            try:
                with pd.ExcelWriter(output_file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    original_df.to_excel(writer, sheet_name=sheet_name if sheet_name else 'Sheet1', index=False)
            except Exception as write_error:
                print(f"❌ Error writing to file: {str(write_error)}")
                return False
            
            if sheet_name:
                print(f"✅ Context Relevancy scores added to sheet '{sheet_name}'")
            else:
                print("✅ Context Relevancy scores added to output file")
            
            # Show summary
            valid_scores = original_df['context_relevancy'][original_df['context_relevancy'] >= 0]
            if not valid_scores.empty:
                print(f"📊 Context Relevancy Summary for {sheet_name if sheet_name else 'main sheet'}:")
                print(f"   Total evaluations: {len(original_df)}")
                print(f"   Valid scores: {len(valid_scores)}")
                print(f"   Average score: {valid_scores.mean():.2f}/5")
                print(f"   Min score: {valid_scores.min():.2f}/5")
                print(f"   Max score: {valid_scores.max():.2f}/5")
            
            return True
        else:
            if sheet_name:
                print(f"❌ Context relevancy column not found in results for sheet '{sheet_name}'")
            else:
                print("❌ Context relevancy column not found in results")
            return False
            
    except Exception as e:
        if sheet_name:
            print(f"❌ Error adding context relevancy for sheet '{sheet_name}': {str(e)}")
        else:
            print(f"❌ Error adding context relevancy: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def add_rag_analysis_to_output(output_file_path, model_type="openai"):
    """
    Add RAG system analysis to the evaluation output.
    
    Args:
        output_file_path: Path to the evaluation output Excel file
        model_type: "openai" or "azure" to specify which model to use for analysis
    """
    try:
        print(f"🔍 Adding RAG System Analysis to output file: {output_file_path}")
        
        # Import the RAG analysis functionality
        from rag_analysis import RAGAnalyzer
        
        # Create analyzer
        analyzer = RAGAnalyzer(model_type=model_type)
        
        # Run analysis
        analysis_result = analyzer.analyze_rag_system(output_file_path)
        
        if analysis_result:
            print("✅ RAG System Analysis completed successfully!")
            
            # Save analysis to a separate file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_file = f"rag_analysis_report_{timestamp}.txt"
            analyzer.save_analysis_results(analysis_result, analysis_file)
            
            return True
        else:
            print("❌ Failed to generate RAG analysis")
            return False
            
    except Exception as e:
        print(f"❌ Error adding RAG analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# for running from api
def run(input_file, sheet_name="", evaluate_ragas=False, evaluate_crag=False, use_search_api=False, llm_model=None, save_db=False, use_async_api=False, use_async_ragas=False ,run_analysis=False):
    try:
        overall_start_time = time.time()
        
        config_manager = ConfigManager()
        config = config_manager.get_config()

        run_ragas = evaluate_ragas
        run_crag = evaluate_crag
         # If no specific sheet is provided, get all sheet names
        if sheet_name:
            sheet_names = [sheet_name]
        else:
            excel_file_path = input_file
            try:
                sheet_names = pd.ExcelFile(excel_file_path, engine='openpyxl').sheet_names
            except Exception as e:
                raise Exception("Error in reading the excel file: " + str(e))
        # Define the relative path directory where you want to save the output file
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        relative_output_dir = os.path.join(current_file_dir, "outputs")
        os.makedirs(relative_output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_filename = os.path.splitext(os.path.basename(input_file))[0]
        output_filename = f"{base_filename}_evaluation_output_{timestamp}.xlsx"
        output_file_path = os.path.join(relative_output_dir, output_filename)

        run_ragas = evaluate_ragas
        run_crag = evaluate_crag
        if not run_ragas and not run_crag:
            run_crag = True
            run_ragas = True

        print("🚀 Starting RAG Evaluation Pipeline")
        print("=" * 60)
        if run_ragas:
            print("✅ Ragas evaluation started")
            if use_async_ragas:
                print("⚡ Using async Ragas evaluation")
        if run_crag:
            print("✅ Crag evaluation started")
        if use_async_api:
            print("⚡ Using async API calls for better performance")
        print(f"📁 Output will be saved to: {output_filename}")
        print()

        pipeline_start_time = time.time()
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            sheets_processed = False
            for i, current_sheet_name in enumerate(sheet_names):
                print(f"📋 Processing sheet {i+1}/{len(sheet_names)}: {current_sheet_name}")
                
                if use_async_api or use_async_ragas:
                    # Use async evaluation
                    results = asyncio.run(evaluate_with_ragas_and_crag_async(input_file, current_sheet_name, config,
                                                        run_crag=run_crag,
                                                        run_ragas=run_ragas,
                                                        use_search_api=use_search_api, 
                                                        llm_model=llm_model,
                                                        use_async_ragas=use_async_ragas))
                else:
                    # Use sync evaluation
                    results = evaluate_with_ragas_and_crag(input_file, current_sheet_name, config,
                                                       run_crag=run_crag,
                                                       run_ragas=run_ragas,
                                                       use_search_api=use_search_api, 
                                                       llm_model=llm_model)
                
                # Handle the case where results might be None or empty
                if results and len(results) >= 1 and not results[0].empty:
                    # Add context relevancy scores if Ragas was run
                    if run_ragas:
                        print(f"🔄 Adding Context Relevancy for sheet '{current_sheet_name}'...")
                        model_type = "azure" if llm_model == "azure" else "openai"
                        
                        # Import the check_relevance functionality
                        from check_relevance import extract_data_from_ragas_output, evaluate_relevance_batch, setup_openai_client, get_model_from_config
                        
                        # Extract data from the results DataFrame
                        data_df = pd.DataFrame({
                            'user_input': results[0]['user_input'].tolist(),
                            'retrieved_contexts': results[0]['retrieved_contexts'].tolist()
                        })
                        
                        # Evaluate context relevancy
                        print(f"🔄 Evaluating context relevancy for sheet '{current_sheet_name}' using {model_type.upper()}...")
                        relevancy_results_df = evaluate_relevance_batch(data_df, output_file=None, model_type=model_type)
                        
                        if relevancy_results_df is not None and 'relevance_score' in relevancy_results_df.columns:
                            # Add context relevancy scores to the results DataFrame
                            relevancy_scores = []
                            for _, original_row in results[0].iterrows():
                                query = original_row.get('user_input', '')
                                # Find matching row in relevancy results
                                matching_row = relevancy_results_df[relevancy_results_df['query'] == query]
                                if not matching_row.empty:
                                    relevancy_scores.append(matching_row.iloc[0]['relevance_score'])
                                else:
                                    relevancy_scores.append(-1)  # No match found
                            
                            results[0]['context_relevancy'] = relevancy_scores
                            print(f"✅ Context Relevancy scores added to sheet '{current_sheet_name}'")
                            
                            # Show summary
                            valid_scores = [score for score in relevancy_scores if score >= 0]
                            if valid_scores:
                                print(f"📊 Context Relevancy Summary for {current_sheet_name}:")
                                print(f"   Total evaluations: {len(results[0])}")
                                print(f"   Valid scores: {len(valid_scores)}")
                                print(f"   Average score: {sum(valid_scores)/len(valid_scores):.2f}/5")
                                print(f"   Min score: {min(valid_scores):.2f}/5")
                                print(f"   Max score: {max(valid_scores):.2f}/5")
                        else:
                            print(f"⚠️  Failed to calculate context relevancy for sheet '{current_sheet_name}'")
                    
                    # Write results to Excel with context relevancy included
                    results[0].to_excel(writer, sheet_name=current_sheet_name, index=False)
                    if(save_db):
                        dbService(results[0], results[1], timestamp)
                    print(f"✅ Results for sheet '{current_sheet_name}' saved to '{output_filename}'.")
                    sheets_processed = True
                else:
                    print(f"⚠️  No results to save for sheet '{current_sheet_name}'. Skipping.")
            
            # If no sheets were processed, create a dummy sheet to avoid Excel error
            if not sheets_processed:
                print("⚠️  No results generated for any sheet. Creating empty result file.")
                empty_df = pd.DataFrame({'message': ['No evaluation results generated']})
                empty_df.to_excel(writer, sheet_name='No_Results', index=False)

        pipeline_end_time = time.time()
        pipeline_time = pipeline_end_time - pipeline_start_time

        # Add RAG analysis if requested (only once for all sheets)
        run_analysis = False  # Default to False, can be set based on args if needed
        if run_analysis:
            print("\n🔍 Running RAG System Analysis...")
            analysis_start_time = time.time()
            model_type = "azure" if llm_model == "azure" else "openai"
            analysis_success = add_rag_analysis_to_output(output_file_path, model_type)
            analysis_end_time = time.time()
            analysis_time = analysis_end_time - analysis_start_time
            
            if analysis_success:
                print(f"✅ RAG System Analysis completed successfully ({analysis_time:.2f}s)")
            else:
                print("⚠️  Failed to complete RAG System Analysis")

        # Calculate overall execution time
        overall_end_time = time.time()
        total_execution_time = overall_end_time - overall_start_time

        print(f"\n🎉 All results have been saved to '{output_filename}'.")
        print("📊 The output file includes Context Relevancy scores and RAG analysis report.")
        
        # Print comprehensive timing summary
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE TIMING SUMMARY")
        print("="*60)
        print(f"🚀 Total Execution Time: {total_execution_time:.2f}s")
        print(f"📋 Pipeline Processing: {pipeline_time:.2f}s")
        if run_analysis:
            print(f"🔍 RAG Analysis: {analysis_time:.2f}s")
        
        # Calculate time breakdown percentages
        if total_execution_time > 0:
            pipeline_percent = (pipeline_time / total_execution_time) * 100
            print(f"   📈 Pipeline: {pipeline_percent:.1f}% of total time")
            if run_analysis:
                analysis_percent = (analysis_time / total_execution_time) * 100
                print(f"   📈 RAG Analysis: {analysis_percent:.1f}% of total time")
        
        return f"All results have been saved to '{output_filename}'. Total execution time: {total_execution_time:.2f}s"
    except Exception as e:
        raise Exception(f"RAG Evaluation has been failed with an error: {e}")

def main():
    try:
        overall_start_time = time.time()
        
        # Setup command-line argument parsing
        parser = argparse.ArgumentParser(description='Evaluate Ragas and Crag based on Excel input.')
        parser.add_argument('--input_file', type=str, required=True, help='Path to the input Excel file.')
        parser.add_argument('--sheet_name', type=str, help='Specific sheet name to evaluate (defaults to all sheets).')
        parser.add_argument('--evaluate_ragas', action='store_true', help='Run only Ragas evaluation.')
        parser.add_argument('--evaluate_crag', action='store_true', help='Run only Crag evaluation.')
        parser.add_argument('--use_search_api', action='store_true', help='Use SearchAssist API to fetch responses.')
        parser.add_argument('--llm_model', type=str, help="Use Azure OpenAI to evaluate the responses.")
        parser.add_argument('--save_db', action='store_true', help='Save the results to MongoDB.')
        parser.add_argument('--use_async_api', action='store_true', help='Use async API calls for better performance.')
        parser.add_argument('--use_async_ragas', action='store_true', help='Use async Ragas evaluation for better performance.')
        args = parser.parse_args()

        config_manager = ConfigManager()
        config = config_manager.get_config()

        # If no specific sheet is provided, get all sheet names
        if args.sheet_name:
            sheet_names = [args.sheet_name]
        else:
            excel_file_path = args.input_file
            sheet_names = pd.ExcelFile(excel_file_path).sheet_names

        # Define the relative path directory where you want to save the output file
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        relative_output_dir = os.path.join(current_file_dir, "outputs")
        os.makedirs(relative_output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_filename = os.path.splitext(os.path.basename(args.input_file))[0]
        output_filename = f"{base_filename}_evaluation_output_{timestamp}.xlsx"
        output_file_path = os.path.join(relative_output_dir, output_filename)

        run_ragas = args.evaluate_ragas
        run_crag = args.evaluate_crag
        if not run_ragas and not run_crag:
            run_crag = True
            run_ragas = True

        llm_model = args.llm_model

        print("🚀 Starting RAG Evaluation Pipeline")
        print("=" * 60)
        if run_ragas:
            print("✅ Ragas evaluation ")
            if args.use_async_ragas:
                print("⚡ Using async Ragas evaluation")
        if run_crag:
            print("✅ Crag evaluation")
        if args.use_async_api:
            print("⚡ Using async API calls for better performance")
        print(f"📁 Output will be saved to: {output_filename}")
        print()

        pipeline_start_time = time.time()
        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            sheets_processed = False
            for i, current_sheet_name in enumerate(sheet_names):
                print(f"📋 Processing sheet {i+1}/{len(sheet_names)}: {current_sheet_name}")
                
                if args.use_async_api or args.use_async_ragas:
                    # Use async evaluation
                    results = asyncio.run(evaluate_with_ragas_and_crag_async(args.input_file, current_sheet_name, config,
                                                        run_crag=run_crag,
                                                        run_ragas=run_ragas,
                                                        use_search_api=args.use_search_api, 
                                                        llm_model=llm_model,
                                                        use_async_ragas=args.use_async_ragas))
                else:
                    # Use sync evaluation
                    results = evaluate_with_ragas_and_crag(args.input_file, current_sheet_name, config,
                                                       run_crag=run_crag,
                                                       run_ragas=run_ragas,
                                                       use_search_api=args.use_search_api, 
                                                       llm_model=llm_model)
                
                # Handle the case where results might be None or empty
                if results and len(results) >= 1 and not results[0].empty:
                    # Add context relevancy scores if Ragas was run
                    if run_ragas:
                        print(f"🔄 Adding Context Relevancy for sheet '{current_sheet_name}'...")
                        model_type = "azure" if llm_model == "azure" else "openai"
                        
                        # Import the check_relevance functionality
                        from check_relevance import extract_data_from_ragas_output, evaluate_relevance_batch, setup_openai_client, get_model_from_config
                        
                        # Extract data from the results DataFrame
                        data_df = pd.DataFrame({
                            'user_input': results[0]['user_input'].tolist(),
                            'retrieved_contexts': results[0]['retrieved_contexts'].tolist()
                        })
                        
                        # Evaluate context relevancy
                        print(f"🔄 Evaluating context relevancy for sheet '{current_sheet_name}' using {model_type.upper()}...")
                        relevancy_results_df = evaluate_relevance_batch(data_df, output_file=None, model_type=model_type)
                        
                        if relevancy_results_df is not None and 'relevance_score' in relevancy_results_df.columns:
                            # Add context relevancy scores to the results DataFrame
                            relevancy_scores = []
                            for _, original_row in results[0].iterrows():
                                query = original_row.get('user_input', '')
                                # Find matching row in relevancy results
                                matching_row = relevancy_results_df[relevancy_results_df['query'] == query]
                                if not matching_row.empty:
                                    relevancy_scores.append(matching_row.iloc[0]['relevance_score'])
                                else:
                                    relevancy_scores.append(-1)  # No match found
                            
                            results[0]['context_relevancy'] = relevancy_scores
                            print(f"✅ Context Relevancy scores added to sheet '{current_sheet_name}'")
                            
                            # Show summary
                            valid_scores = [score for score in relevancy_scores if score >= 0]
                            if valid_scores:
                                print(f"📊 Context Relevancy Summary for {current_sheet_name}:")
                                print(f"   Total evaluations: {len(results[0])}")
                                print(f"   Valid scores: {len(valid_scores)}")
                                print(f"   Average score: {sum(valid_scores)/len(valid_scores):.2f}/5")
                                print(f"   Min score: {min(valid_scores):.2f}/5")
                                print(f"   Max score: {max(valid_scores):.2f}/5")
                        else:
                            print(f"⚠️  Failed to calculate context relevancy for sheet '{current_sheet_name}'")
                    
                    # Write results to Excel with context relevancy included
                    results[0].to_excel(writer, sheet_name=current_sheet_name, index=False)
                    if(args.save_db):
                        dbService(results[0], results[1], timestamp)
                    print(f"✅ Results for sheet '{current_sheet_name}' saved to '{output_filename}'.")
                    sheets_processed = True
                else:
                    print(f"⚠️  No results to save for sheet '{current_sheet_name}'. Skipping.")
            
            # If no sheets were processed, create a dummy sheet to avoid Excel error
            if not sheets_processed:
                print("⚠️  No results generated for any sheet. Creating empty result file.")
                empty_df = pd.DataFrame({'message': ['No evaluation results generated']})
                empty_df.to_excel(writer, sheet_name='No_Results', index=False)

        pipeline_end_time = time.time()
        pipeline_time = pipeline_end_time - pipeline_start_time

        # Add RAG analysis if requested (only once for all sheets)
        run_analysis = False  # Default to False, can be set based on args if needed
        if run_analysis:
            print("\n🔍 Running RAG System Analysis...")
            analysis_start_time = time.time()
            model_type = "azure" if llm_model == "azure" else "openai"
            analysis_success = add_rag_analysis_to_output(output_file_path, model_type)
            analysis_end_time = time.time()
            analysis_time = analysis_end_time - analysis_start_time
            
            if analysis_success:
                print(f"✅ RAG System Analysis completed successfully ({analysis_time:.2f}s)")
            else:
                print("⚠️  Failed to complete RAG System Analysis")

        # Calculate overall execution time
        overall_end_time = time.time()
        total_execution_time = overall_end_time - overall_start_time

        print(f"\n🎉 All results have been saved to '{output_filename}'.")
        print("📊 The output file includes Context Relevancy scores and RAG analysis report.")
        
        # Print comprehensive timing summary
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE TIMING SUMMARY")
        print("="*60)
        print(f"🚀 Total Execution Time: {total_execution_time:.2f}s")
        print(f"📋 Pipeline Processing: {pipeline_time:.2f}s")
        if run_analysis:
            print(f"🔍 RAG Analysis: {analysis_time:.2f}s")
        
        # Calculate time breakdown percentages
        if total_execution_time > 0:
            pipeline_percent = (pipeline_time / total_execution_time) * 100
            print(f"   📈 Pipeline: {pipeline_percent:.1f}% of total time")
            if run_analysis:
                analysis_percent = (analysis_time / total_execution_time) * 100
                print(f"   📈 RAG Analysis: {analysis_percent:.1f}% of total time")
        
    except Exception as e:
        raise Exception("RAG Evaluation has been failed with an error!!!")

if __name__ == "__main__":
    main()
