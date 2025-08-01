# src/evaluators/ragasEvaluator.py

import asyncio
import concurrent.futures
from datasets import Dataset
# Ragas Metrics updated to work with latest version
from ragas.metrics import (
    ResponseRelevancy,
    Faithfulness,
    ContextRecall,
    LLMContextPrecisionWithReference,
    AnswerCorrectness,
    SemanticSimilarity
)
from langchain_openai.chat_models import AzureChatOpenAI
from langchain_openai.embeddings import AzureOpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.cost import get_token_usage_for_openai
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from ragas import evaluate
from .baseEvaluator import BaseEvaluator
from config.configManager import ConfigManager


class RagasEvaluator(BaseEvaluator):
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()

    def _run_ragas_sync(self, queries, answers, ground_truths, contexts, model=""):
        """
        Synchronous RAGAS evaluation that runs in a separate thread.
        This avoids uvloop/nest_asyncio conflicts.
        """
        # Set up a new event loop for this thread
        # This is required because RAGAS internally uses asyncio.run()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print(f"✅ Set up new event loop in worker thread: {type(loop)}")
        except Exception as e:
            print(f"⚠️  Warning: Could not set up event loop in thread: {e}")
        
        try:
            llm_model = model if model else "openai"
            
            if llm_model == "azure":
                evaluator_llm = LangchainLLMWrapper(AzureChatOpenAI(
                    model=self.config["azure"]["model_name"],
                    openai_api_version=self.config["azure"]["openai_api_version"],
                    azure_endpoint=self.config["azure"]["base_url"],
                    deployment_name=self.config["azure"]["model_deployment"],
                    openai_api_key=self.config["azure"].get("api_key"),
                ))
                evaluator_embeddings = LangchainEmbeddingsWrapper(AzureOpenAIEmbeddings(
                    model=self.config["azure"]["embedding_name"],
                    openai_api_version=self.config["azure"]["openai_api_version"],
                    azure_endpoint=self.config["azure"]["base_url"],
                    deployment_name=self.config["azure"]["embedding_deployment"],
                    openai_api_key=self.config["azure"].get("api_key"),
                ))
            else:
                evaluator_llm = LangchainLLMWrapper(ChatOpenAI(
                    model=self.config["openai"]["model_name"],
                    openai_api_key=self.config["openai"].get("api_key"),
                    openai_organization=self.config["openai"].get("org_id"),
                ))
                evaluator_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(
                    model=self.config["openai"]["embedding_name"],
                    openai_api_key=self.config["openai"].get("api_key"),
                    openai_organization=self.config["openai"].get("org_id"),
                ))
                
            # Define the metrics to evaluate and set the per metric evaluation models
            metrics = [
                ResponseRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
                Faithfulness(llm=evaluator_llm),
                ContextRecall(llm=evaluator_llm),
                LLMContextPrecisionWithReference(llm=evaluator_llm, name="context_precision"),
                AnswerCorrectness(llm=evaluator_llm, embeddings=evaluator_embeddings),
                SemanticSimilarity(embeddings=evaluator_embeddings, name="answer_similarity")
            ]
            
            ground_truths = [str(ground_truth).strip() for ground_truth in ground_truths]
            
            # Fix contexts data format for RAGAS compatibility
            # Convert string representations of lists back to actual lists
            processed_contexts = []
            for context in contexts:
                if isinstance(context, str):
                    try:
                        # Handle various string formats
                        if context.strip() in ['[]', '', 'null', 'None']:
                            processed_contexts.append([])
                        elif context.startswith('[') and context.endswith(']'):
                            # Try to safely evaluate the string as a list
                            import ast
                            processed_contexts.append(ast.literal_eval(context))
                        else:
                            # Single context item, wrap in list
                            processed_contexts.append([context])
                    except (ValueError, SyntaxError) as e:
                        print(f"Warning: Could not parse context '{context}', using as single item: {e}")
                        processed_contexts.append([context] if context else [])
                elif isinstance(context, list):
                    processed_contexts.append(context)
                else:
                    # Convert other types to string and wrap in list
                    processed_contexts.append([str(context)] if context else [])
            
            print(f"Processed {len(processed_contexts)} contexts for RAGAS evaluation")
            print(f"Sample context format: {type(processed_contexts[0]) if processed_contexts else 'No contexts'}")
            
            # Update the required columns names in the dataset
            data = {
                'user_input': queries,
                'response': answers,
                'retrieved_contexts': processed_contexts,  # Use processed contexts
                'reference': ground_truths
            }
            dataset = Dataset.from_dict(data)
            
            # Run RAGAS evaluation in this thread (now with proper event loop)
            print("🔄 Running RAGAS evaluation with thread event loop...")
            print(f"📊 Dataset shape: {len(dataset)} rows")
            print(f"📊 Dataset columns: {list(dataset.column_names)}")
            print(f"📊 Metrics to evaluate: {[metric.__class__.__name__ for metric in metrics]}")
            
            result = evaluate(dataset, metrics=metrics, token_usage_parser=get_token_usage_for_openai)
            
            # Extract token usage and cost information
            inputcost = self.config["cost_of_model"]["input"]
            outputcost = self.config["cost_of_model"]["output"]
            
            # Get token information
            total_tokens_obj = result.total_tokens()
            input_tokens = total_tokens_obj.input_tokens
            output_tokens = total_tokens_obj.output_tokens
            total_tokens = input_tokens + output_tokens
            
            # Calculate cost
            total_cost = result.total_cost(cost_per_input_token=inputcost, cost_per_output_token=outputcost)
            
            print(f"💰 Total Tokens for Evaluation: Input={input_tokens} Output={output_tokens}")
            print(f"💰 Total Cost in $: {total_cost}")
            
            result_df = result.to_pandas()
            print(f"📈 RAGAS result DataFrame shape: {result_df.shape}")
            print(f"📈 RAGAS result columns: {list(result_df.columns)}")
            print(f"📈 RAGAS sample row: {result_df.iloc[0].to_dict() if len(result_df) > 0 else 'No data'}")
            
            # Create enhanced result with token usage information
            enhanced_result = {
                'ragas_result': result,
                'token_usage': {
                    'prompt_tokens': input_tokens,
                    'completion_tokens': output_tokens,
                    'total_tokens': total_tokens,
                    'estimated_cost_usd': total_cost
                },
                'evaluation_summary': {
                    'total_queries': len(dataset),
                    'metrics_evaluated': [metric.__class__.__name__ for metric in metrics],
                    'model_used': self.config.get('llm_model', 'default')
                }
            }
            
            return result_df, enhanced_result
            
        finally:
            # Clean up the event loop
            try:
                loop = asyncio.get_event_loop()
                if loop and not loop.is_closed():
                    loop.close()
                    print("✅ Cleaned up thread event loop")
            except Exception as e:
                print(f"⚠️  Warning: Could not clean up event loop: {e}")

    async def evaluate(self, queries, answers, ground_truths, contexts, model=""):
        """
        Async wrapper that runs RAGAS evaluation in a thread pool to avoid uvloop conflicts.
        """
        print("🔄 Running RAGAS evaluation in thread pool to avoid uvloop conflicts...")
        
        loop = asyncio.get_event_loop()
        
        try:
            # Run RAGAS evaluation in a thread pool executor
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = await loop.run_in_executor(
                    executor, 
                    self._run_ragas_sync, 
                    queries, answers, ground_truths, contexts, model
                )
            
            print("✅ RAGAS evaluation completed successfully in thread pool")
            return result
            
        except Exception as e:
            print(f"❌ RAGAS evaluation failed in thread pool: {e}")
            raise e

    def process_results(self, results):
        return results.to_pandas()
