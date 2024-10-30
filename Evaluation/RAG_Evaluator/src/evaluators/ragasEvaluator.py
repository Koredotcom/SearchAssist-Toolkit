# src/evaluators/ragasEvaluator.py

from datasets import Dataset
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_recall,
    context_precision,
    answer_correctness,
    answer_similarity
)
from langchain_openai.chat_models import AzureChatOpenAI
from langchain_openai.embeddings import AzureOpenAIEmbeddings
from ragas import evaluate
from .baseEvaluator import BaseEvaluator
from config.configManager import ConfigManager

metrics = [
    answer_relevancy,
    faithfulness,
    context_recall,
    context_precision,
    answer_correctness,
    answer_similarity,
]


class RagasEvaluator(BaseEvaluator):
    def evaluate(self, queries, answers, ground_truths, contexts, model):
        config_manager = ConfigManager()
        config = config_manager.get_config()
        if model == "azure":
            azure_model = AzureChatOpenAI(
                openai_api_version= config["azure"]["openai_api_version"],
                azure_endpoint= config["azure"]["base_url"],
                azure_deployment= config["azure"]["model_deployment"],
                model= config["azure"]["model_name"],
                validate_base_url=False,
            )

            azure_embeddings = AzureOpenAIEmbeddings(
                openai_api_version= config["azure"]["openai_api_version"],
                azure_endpoint= config["azure"]["base_url"],
                azure_deployment= config["azure"]["embedding_deployment"],
                model= config["azure"]["embedding_name"],
            )
        ground_truths = [str(ground_truth).strip() for ground_truth in ground_truths]
        data = {
            'question': queries,
            'answer': answers,
            'contexts': contexts,
            'ground_truth': ground_truths
        }
        dataset = Dataset.from_dict(data)
        result = evaluate(dataset, metrics=metrics, llm=azure_model, embeddings=azure_embeddings) if model=="azure" else evaluate(dataset, metrics=metrics)
        result_df = result.to_pandas()
        return result_df, result

    def process_results(self, results):
        return results.to_pandas()
