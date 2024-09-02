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
from ragas import evaluate
from .baseEvaluator import BaseEvaluator


class RagasEvaluator(BaseEvaluator):
    def evaluate(self, queries, answers, ground_truths, contexts, question_type):
        ground_truths = [str(ground_truth).strip() for ground_truth in ground_truths]
        data = {
            'question': queries,
            'answer': answers,
            'contexts': contexts,
            'ground_truth': ground_truths
        }
        dataset = Dataset.from_dict(data)
        result = evaluate(dataset, metrics=[
            answer_relevancy,
            faithfulness,
            context_recall,
            context_precision,
            answer_correctness,
            answer_similarity
        ])
        result_df = result.to_pandas()
        result_df['question_type'] = question_type
        return result_df

    def process_results(self, results):
        return results.to_pandas()
