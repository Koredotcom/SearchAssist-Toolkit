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
from api.SASearch import SearchAssistAPI, get_bot_response
from typing import List, Tuple, Optional


def call_searchassist_api(queries: List[str], ground_truths: List[str]) -> List[dict]:
    api = SearchAssistAPI()
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


def load_data_and_call_api(excel_file: str, sheet_name: Optional[str], config: dict) -> Tuple[List[str], List[str], List[str], List[str]]:
    df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
    queries = df['query'].fillna('').tolist()
    ground_truths = df['ground_truth'].fillna('').tolist()

    api_results = call_searchassist_api(queries, ground_truths)

    results_df = pd.DataFrame(api_results)
    relative_output_dir = "./outputs/sa_api_outputs"
    os.makedirs(relative_output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_filename = os.path.splitext(os.path.basename(excel_file))[0]
    output_filename = f"{base_filename}_sa_api_results_{timestamp}.xlsx"
    output_file_path = os.path.join(relative_output_dir, output_filename)
    results_df.to_excel(output_file_path, index=False)

    print(f"API results saved to {output_file_path}")

    return (
        results_df['query'].tolist(),
        results_df['answer'].tolist(),
        results_df['ground_truth'].tolist(),
        results_df['context'].tolist()
    )


def load_data(excel_file: str, sheet_name: Optional[str]) -> Tuple[List[str], List[str], List[str], List[str]]:
    df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl') if sheet_name else pd.read_excel(excel_file, engine='openpyxl')
    queries = df['query'].fillna('').tolist()
    ground_truths = df['ground_truth'].fillna('').tolist()
    contexts = df['contexts'].fillna('[]').apply(eval).tolist()
    answers = df['answer'].fillna('').tolist()

    return queries, answers, ground_truths, contexts


def evaluate_with_ragas_and_crag(excel_file: str, sheet_name: Optional[str], config: dict, run_ragas: bool = True, run_crag: bool = True, use_search_api: bool = False) -> Optional[pd.DataFrame]:
    try:
        if use_search_api:
            queries, answers, ground_truths, contexts = load_data_and_call_api(excel_file, sheet_name, config)
        else:
            queries, answers, ground_truths, contexts = load_data(excel_file, sheet_name)

        ragas_results = pd.DataFrame([])
        crag_results = pd.DataFrame([])

        if run_ragas:
            ragas_evaluator = RagasEvaluator()
            ragas_results = ragas_evaluator.evaluate(queries, answers, ground_truths, contexts)

        if run_crag:
            openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            crag_evaluator = CragEvaluator(config['EVALUATION_MODEL_NAME'], openai_client)
            crag_results = crag_evaluator.evaluate(queries, answers, ground_truths, contexts)

        result_converter = ResultsConverter(ragas_results, crag_results)

        if run_ragas:
            result_converter.convert_ragas_results()

        if run_crag:
            result_converter.convert_crag_results()

        if not ragas_results.empty and not crag_results.empty:
            return result_converter.get_combined_results()
        elif not ragas_results.empty:
            return result_converter.get_ragas_results()
        elif not crag_results.empty:
            return result_converter.get_crag_results()
    except Exception as e:
        print("Encountered error while running evaluation: ", traceback.format_exc())
        raise


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Evaluate Ragas and Crag based on Excel input.')
    parser.add_argument('--input_file', type=str, required=True, help='Path to the input Excel file.')
    parser.add_argument('--sheet_name', type=str, help='Specific sheet name to evaluate (defaults to all sheets).')
    parser.add_argument('--evaluate_ragas', action='store_true', help='Run only Ragas evaluation.')
    parser.add_argument('--evaluate_crag', action='store_true', help='Run only Crag evaluation.')
    parser.add_argument('--use_search_api', action='store_true', help='Use SearchAssist API to fetch responses.')
    return parser.parse_args()


def setup_output_directory() -> str:
    relative_output_dir = "./outputs"
    os.makedirs(relative_output_dir, exist_ok=True)
    return relative_output_dir


def main():
    try:
        args = parse_arguments()
        config_manager = ConfigManager()
        config = config_manager.get_config()

        sheet_names = [args.sheet_name] if args.sheet_name else pd.ExcelFile(args.input_file).sheet_names
        output_dir = setup_output_directory()

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_filename = os.path.splitext(os.path.basename(args.input_file))[0]
        output_filename = f"{base_filename}_evaluation_output_{timestamp}.xlsx"
        output_file_path = os.path.join(output_dir, output_filename)

        run_ragas = args.evaluate_ragas or not args.evaluate_crag
        run_crag = args.evaluate_crag or not args.evaluate_ragas

        with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
            for sheet_name in sheet_names:
                print(f"Processing sheet: {sheet_name}")
                results = evaluate_with_ragas_and_crag(args.input_file, sheet_name, config,
                                                       run_crag=run_crag,
                                                       run_ragas=run_ragas,
                                                       use_search_api=args.use_search_api)
                results.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"Results for sheet '{sheet_name}' saved to '{output_filename}'.")

        print(f"All results have been saved to '{output_filename}'.")
    except Exception as e:
        print("RAG Evaluation has failed with an error:", e)


if __name__ == "__main__":
    main()
