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
import os



# Please add open ai key in os-env before running this script



def evaluate_data(queries,answers,ground_truth_values,contexts,context_url):
    data = {
    'question':queries,
    'answer':answers,
    'contexts': contexts,
    'ground_truth':ground_truth_values
    }
    #printing the eval data
    print(data)
    dataset = Dataset.from_dict(data)
    score = evaluate(dataset,metrics=[
        answer_relevancy,
        faithfulness,
        context_recall,
        context_precision,
        answer_correctness,
        answer_similarity]
    )
    df=score.to_pandas()
    df['context_url']=context_url
    print(df['answer_similarity'].tolist())
    print(df.head())
    return df
