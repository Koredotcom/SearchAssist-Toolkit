import os
import json
import pandas as pd
from tqdm.auto import tqdm
import sys

sys.path.append(str(os.getcwd()))
from transformers import AutoTokenizer
from loguru import logger
from evaluators.baseEvaluator import BaseEvaluator
from utils.fileHandling import log_response
from utils.dataProcessing import trim_predictions_to_max_token_length
from config.configManager import ConfigManager
from utils.fileHandling import load_json_file

# Give relative path of the file from src directory
prompts_file_path = "./prompts/prompts.json"
prompts = load_json_file(prompts_file_path)


class CragEvaluator(BaseEvaluator):
    def __init__(self, model_name, openai_client):
        self.model_name = model_name
        self.openai_client = openai_client
        self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
        self.config = ConfigManager().get_config()

    def evaluate(self, queries, answers, ground_truths, contexts):
        metrics_data = []

        for query, ground_truth, prediction in tqdm(
                zip(queries, ground_truths, answers), total=len(queries), desc="Evaluating Predictions"
        ):
            n_miss, n_correct, n_correct_exact = 0, 0, 0
            result_entry = {
                "query": query,
                "ground_truth": ground_truth,
                "prediction": prediction,
            }

            ground_truth = ground_truth.strip()
            prediction = trim_predictions_to_max_token_length(prediction, self.tokenizer)

            ground_truth_lowercase = ground_truth.lower()
            prediction_lowercase = prediction.lower()

            messages = [
                {"role": "system", "content": self.get_system_message()},
                {
                    "role": "user",
                    "content": f"Question: {query}\\n Ground truth: {ground_truth}\\n Prediction: {prediction}\\n",
                },
            ]

            if any(term in prediction_lowercase for term in
                   ["i don't know", "no answer found", "not enough information", "Failed to get response"]):
                n_miss += 1
                result_entry.update({"score": -1, "missing": True})
            elif prediction_lowercase == ground_truth_lowercase:
                n_correct_exact += 1
                n_correct += 1
                result_entry.update({"score": 1, "exact_accuracy": 1})
            else:
                response = self.attempt_api_call(messages)
                if response:
                    # uncomment whenever needed
                    # log_response(messages, response)
                    eval_res = self.parse_crag_response(response)
                    if eval_res == 1:
                        n_correct += 1
                        result_entry["score"] = 1  # Positive evaluation
                    else:
                        result_entry["score"] = 0  # Neutral evaluation

            # Updating the metric results into the result_entry
            n = 1  # TODO: need to understand it's usecase
            result_entry.update({
                "score": (2 * n_correct + n_miss) / n - 1,
                "exact_accuracy": n_correct_exact / n,
                "accuracy": n_correct / n,
                "hallucination": (n - n_correct - n_miss) / n,
                "missing": n_miss / n,
                "n_miss": n_miss,
                "n_correct": n_correct,
                "n_correct_exact": n_correct_exact,
                "total": n
            })

            metrics_data.append(result_entry)

        # Convert the metrics data to a DataFrame
        results_df = pd.DataFrame(metrics_data)
        return results_df

    def process_results(self, results):
        return results  # Return the DataFrame directly

    def get_system_message(self):
        # Load system message from config or file
        return prompts.get("cragEvaluationPrompt", "")

    def attempt_api_call(self, messages, max_retries=10):
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"API call failed on attempt {attempt + 1}, retrying... Error: {e}")
        return None

    def parse_crag_response(self, resp: str):
        try:
            resp = resp.lower()
            model_resp = json.loads(resp)

            if 'accuracy' in model_resp:
                accuracy_value = model_resp['accuracy']
                if isinstance(accuracy_value, bool):
                    return 1 if accuracy_value else -1
                elif isinstance(accuracy_value, str) and accuracy_value.lower() == 'true':
                    return 1
                elif isinstance(accuracy_value, str) and accuracy_value.lower() == 'false':
                    return -1
                else:
                    raise ValueError(f"Unexpected accuracy value: {accuracy_value}")
            else:
                raise ValueError("Accuracy key not found in response")
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            logger.debug(f"Response content: {resp}")
            return -1
