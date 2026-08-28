#!/usr/bin/env python3
"""
Context Relevance Checker

This script reads query and retrieved_contexts from Ragas output files
and evaluates the relevance of each context for its corresponding query.

Usage:
    python check_relevance.py
    python check_relevance.py --input "outputs/NVR_Evaluation_evaluation_output_*.xlsx"
    python check_relevance.py --sample 5  # Check only first 5 samples
    python check_relevance.py --output results.csv  # Save results to CSV
"""

import os
import sys
import argparse
import pandas as pd
import glob
from openai import OpenAI
from loguru import logger
from tqdm import tqdm
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from evaluators.relevanceEvaluator import RelevanceEvaluator
from config.configManager import ConfigManager


def find_latest_ragas_output():
    """
    Find the latest Ragas output file in the outputs directory.
    
    Returns:
        Path to the latest output file
    """
    outputs_dir = "outputs"
    pattern = os.path.join(outputs_dir, "*evaluation_output*.xlsx")
    
    files = glob.glob(pattern)
    if not files:
        print(f"❌ No Ragas output files found in {outputs_dir}")
        return None
    
    # Sort by modification time to get the latest
    latest_file = max(files, key=os.path.getmtime)
    print(f"📁 Found latest Ragas output: {latest_file}")
    return latest_file


def extract_data_from_ragas_output(file_path):
    """
    Extract user_input and retrieved_contexts from the Ragas output file.
    
    Args:
        file_path: Path to the Ragas output Excel file
        
    Returns:
        DataFrame with user_input and retrieved_contexts columns
    """
    try:
        print(f"Reading Ragas output file: {file_path}")
        df = pd.read_excel(file_path)
        
        print(f"File shape: {df.shape}")
        print(f"Available columns: {list(df.columns)}")
        
        # Check if required columns exist
        required_columns = ['user_input', 'retrieved_contexts']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ Missing columns: {missing_columns}")
            print(f"Available columns: {list(df.columns)}")
            return None
        
        # Extract the required columns
        extracted_data = df[['user_input', 'retrieved_contexts']].copy()
        
        # Remove any rows with missing data
        extracted_data = extracted_data.dropna()
        
        print(f"✅ Successfully extracted {len(extracted_data)} rows")
        print(f"Columns: {list(extracted_data.columns)}")
        
        return extracted_data
        
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
    except Exception as e:
        print(f"❌ Error reading file: {str(e)}")
        return None


def setup_openai_client(model_type="openai"):
    """Setup OpenAI client with API key from environment variable."""
    # Try to get API key from environment variable first
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ OpenAI API key not found in environment variable OPENAI_API_KEY")
        print("Please set your API key using: export OPENAI_API_KEY='your_api_key'")
        return None
    
    return OpenAI(api_key=api_key)


def get_model_from_config(model_type="openai"):
    """Get the model name from config.json."""
    try:
        config = ConfigManager().get_config()
        
        if model_type == "azure":
            model_name = config.get('azure', {}).get('model_name', 'gpt-4')
            print(f"🤖 Using Azure model from config: {model_name}")
        else:
            model_name = config.get('openai', {}).get('model_name', 'gpt-3.5-turbo')
            print(f"🤖 Using OpenAI model from config: {model_name}")
        
        return model_name
    except Exception as e:
        print(f"⚠️  Error reading config, using default model: {str(e)}")
        return 'gpt-3.5-turbo' if model_type != "azure" else 'gpt-4'


def evaluate_relevance_batch(data_df, sample_size=None, output_file='relevance_results.csv', model_type="openai"):
    """
    Evaluate relevance for all query-context pairs in the dataset.
    
    Args:
        data_df: DataFrame with user_input and retrieved_contexts columns
        sample_size: Number of samples to evaluate (None for all)
        output_file: File to save results (optional)
        model_type: "openai" or "azure" to specify which model to use
    
    Returns:
        DataFrame with evaluation results
    """
    # Setup OpenAI client
    openai_client = setup_openai_client(model_type)
    if not openai_client:
        return None
    
    # Get model from config
    model_name = get_model_from_config(model_type)
    evaluator = RelevanceEvaluator(model_name, openai_client, model_type)
    
    # Limit to sample size if specified
    if sample_size:
        data_df = data_df.head(sample_size)
        print(f"Evaluating first {sample_size} samples...")
    
    results = []
    
    print(f"Evaluating relevance for {len(data_df)} query-context pairs using {model_type.upper()}...")
    
    for idx, (_, row) in enumerate(tqdm(data_df.iterrows(), total=len(data_df), desc="Evaluating")):
        query = row['user_input']
        context = row['retrieved_contexts']
        
        try:
            # Evaluate relevance
            result = evaluator.evaluate_single_pair(query, context)
            
            # Add row index for reference
            result['row_index'] = idx + 1
            
            results.append(result)
            
        except Exception as e:
            print(f"Error evaluating row {idx + 1}: {str(e)}")
            results.append({
                'row_index': idx + 1,
                'query': query,
                'context_chunk': context,
                'relevance_score': -1,
                'explanation': f"Error: {str(e)}"
            })
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # Add summary statistics
    valid_results = results_df[results_df['relevance_score'] >= 0]
    if not valid_results.empty:
        summary = {
            'total_evaluations': len(results_df),
            'valid_evaluations': len(valid_results),
            'average_relevance_score': valid_results['relevance_score'].mean(),
            'median_relevance_score': valid_results['relevance_score'].median(),
            'min_relevance_score': valid_results['relevance_score'].min(),
            'max_relevance_score': valid_results['relevance_score'].max(),
            'std_relevance_score': valid_results['relevance_score'].std(),
            'score_distribution': valid_results['relevance_score'].value_counts().sort_index().to_dict()
        }
        
        print(f"\n📊 EVALUATION SUMMARY")
        print("=" * 50)
        for key, value in summary.items():
            if key == 'score_distribution':
                print(f"{key}:")
                for score, count in value.items():
                    print(f"  Score {score}: {count} evaluations")
            else:
                print(f"{key}: {value}")
    
    # Save results if output file specified
    if not output_file:
        output_file = f'relevance_results_from_ragas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    results_df.to_csv(output_file, index=False)
    print(f"\n💾 Results saved to: {output_file}")
    
    return results_df


def display_sample_results(results_df, num_samples=3):
    """Display sample results."""
    print(f"\n📋 SAMPLE RESULTS")
    print("=" * 50)
    
    for i, (_, row) in enumerate(results_df.head(num_samples).iterrows()):
        print(f"\n--- Sample {i+1} ---")
        print(f"Row: {row['row_index']}")
        print(f"Query: {row['query']}")
        print(f"Context: {row['context_chunk'][:150]}...")
        print(f"Relevance Score: {row['relevance_score']}/5")
        print(f"Explanation: {row['explanation']}")
        
        # Provide interpretation
        score = row['relevance_score']
        if score == 5:
            print("✅ Highly relevant")
        elif score == 4:
            print("✅ Mostly relevant")
        elif score == 3:
            print("⚠️  Related but limited")
        elif score == 2:
            print("⚠️  Moderately related")
        elif score == 1:
            print("❌ Slightly related")
        elif score == 0:
            print("❌ Completely irrelevant")
        else:
            print("❓ Unable to evaluate")


def main():
    """Main function to handle command line arguments and run evaluation."""
    parser = argparse.ArgumentParser(
        description="Check relevance of retrieved contexts from Ragas output files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python check_relevance.py
  python check_relevance.py --input "outputs/NVR_Evaluation_evaluation_output_*.xlsx"
  python check_relevance.py --sample 10
  python check_relevance.py --output relevance_results.csv
        """
    )
    
    parser.add_argument("--input", "-i", help="Path to Ragas output file (default: latest)")
    parser.add_argument("--sample", "-s", type=int, help="Number of samples to evaluate (default: all)")
    parser.add_argument("--output", "-o", help="Output CSV file to save results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    
    args = parser.parse_args()
    
    print("Context Relevance Checker (Ragas Output)")
    print("=" * 60)
    print("Reading from Ragas output file and evaluating relevance...")
    print()
    
    try:
        # Determine input file
        if args.input:
            input_file = args.input
        else:
            input_file = find_latest_ragas_output()
            if not input_file:
                return
        
        # Extract data from Ragas output file
        data_df = extract_data_from_ragas_output(input_file)
        
        if data_df is None:
            print("❌ Failed to extract data from Ragas output file")
            return
        
        # Evaluate relevance
        results_df = evaluate_relevance_batch(
            data_df, 
            sample_size=args.sample,
            output_file=args.output
        )
        
        if results_df is None:
            print("❌ Failed to evaluate relevance")
            return
        
        # Display sample results
        display_sample_results(results_df, num_samples=3)
        
        print(f"\n✅ Evaluation completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during evaluation: {str(e)}")
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    main() 