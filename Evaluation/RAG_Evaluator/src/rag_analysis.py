#!/usr/bin/env python3
"""
RAG System Analysis Tool

This script analyzes the complete evaluation output and generates detailed insights
about RAG system performance, including recommendations and improvements.

Usage:
    python rag_analysis.py --input "outputs/NVR_Evaluation_evaluation_output_*.xlsx"
    python rag_analysis.py --input "outputs/NVR_Evaluation_evaluation_output_*.xlsx" --model azure
"""

import os
import sys
import argparse
import pandas as pd
import json
from datetime import datetime
from openai import OpenAI
from loguru import logger
from tqdm import tqdm
import numpy as np

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.configManager import ConfigManager


class RAGAnalyzer:
    def __init__(self, model_type="openai"):
        self.model_type = model_type
        self.config = ConfigManager().get_config()
        self.openai_client = self._setup_client()
        self.model_name = self._get_model_name()
        
    def _setup_client(self):
        """Setup OpenAI client with API key from environment variable."""
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            print("❌ OpenAI API key not found in environment variable OPENAI_API_KEY")
            print("Please set your API key using: export OPENAI_API_KEY='your_api_key'")
            return None
        
        return OpenAI(api_key=api_key)
    
    def _get_model_name(self):
        """Get the model name from config.json."""
        try:
            if self.model_type == "azure":
                model_name = self.config.get('azure', {}).get('model_name', 'gpt-4')
                print(f"🤖 Using Azure model for analysis: {model_name}")
            else:
                model_name = self.config.get('openai', {}).get('model_name', 'gpt-4o-mini')
                print(f"🤖 Using OpenAI model for analysis: {model_name}")
            
            return model_name
        except Exception as e:
            print(f"⚠️  Error reading config, using default model: {str(e)}")
            return 'gpt-4o-mini' if self.model_type != "azure" else 'gpt-4'
    
    def load_evaluation_data(self, file_path):
        """
        Load evaluation data from Excel file, excluding retrieved_contexts.
        
        Args:
            file_path: Path to the evaluation output Excel file
            
        Returns:
            DataFrame with evaluation data (excluding retrieved_contexts)
        """
        try:
            print(f"📊 Loading evaluation data from: {file_path}")
            df = pd.read_excel(file_path)
            
            # Remove retrieved_contexts column if it exists
            if 'retrieved_contexts' in df.columns:
                df = df.drop(columns=['retrieved_contexts'])
                print("✅ Removed retrieved_contexts column")
            
            print(f"📈 Data shape: {df.shape}")
            print(f"📋 Available columns: {list(df.columns)}")
            
            return df
            
        except Exception as e:
            print(f"❌ Error loading data: {str(e)}")
            return None
    
    def _convert_to_json_serializable(self, obj):
        """
        Convert pandas/numpy objects to JSON serializable types.
        
        Args:
            obj: Object to convert
            
        Returns:
            JSON serializable object
        """
        if pd.isna(obj):
            return None
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, (np.bool_)):
            return bool(obj)
        elif isinstance(obj, (list, tuple)):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._convert_to_json_serializable(value) for key, value in obj.items()}
        else:
            return obj

    def prepare_analysis_data(self, df):
        """
        Prepare data for analysis by creating summary statistics.
        
        Args:
            df: DataFrame with evaluation results
            
        Returns:
            Dictionary with analysis data
        """
        analysis_data = {
            "total_samples": len(df),
            "columns": list(df.columns),
            "summary_stats": {}
        }
        
        # Calculate summary statistics for numeric columns
        numeric_columns = df.select_dtypes(include=['number']).columns
        for col in numeric_columns:
            if col in df.columns:
                # Convert pandas numeric types to native Python types for JSON serialization
                analysis_data["summary_stats"][col] = {
                    "mean": self._convert_to_json_serializable(df[col].mean()),
                    "median": self._convert_to_json_serializable(df[col].median()),
                    "min": self._convert_to_json_serializable(df[col].min()),
                    "max": self._convert_to_json_serializable(df[col].max()),
                    "std": self._convert_to_json_serializable(df[col].std()),
                    "count": self._convert_to_json_serializable(df[col].count())
                }
        
        # Sample data for detailed analysis
        sample_size = min(10, len(df))
        # Convert DataFrame to records and handle numeric types
        sample_records = df.head(sample_size).to_dict('records')
        
        # Convert all values to JSON serializable types
        converted_records = []
        for record in sample_records:
            converted_record = {}
            for key, value in record.items():
                converted_record[key] = self._convert_to_json_serializable(value)
            converted_records.append(converted_record)
        
        analysis_data["sample_data"] = converted_records
        
        return analysis_data
    
    def generate_analysis_prompt(self, analysis_data):
        """
        Generate the analysis prompt for the LLM.
        
        Args:
            analysis_data: Dictionary with analysis data
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""
You are an expert in evaluating Retrieval-Augmented Generation (RAG) pipelines.

Below is the output of a RAGAS evaluation on a dataset, including the following metrics:

- Answer Correctness
- Faithfulness
- Context Relevancy

The RAG system works by retrieving **relevant chunks (context)** for a given **user query**, and then passing that context to an LLM to **generate the answer**.

EVALUATION DATA SUMMARY:
- Total samples: {analysis_data['total_samples']}
- Available metrics: {', '.join(analysis_data['columns'])}

SUMMARY STATISTICS:
{json.dumps(analysis_data['summary_stats'], indent=2)}

SAMPLE DATA (first 10 entries):
{json.dumps(analysis_data['sample_data'], indent=2)}

---

Please analyze the RAGAS evaluation and generate a **comprehensive and human-understandable performance report**. The report should include the following:

---

1. **EXECUTIVE SUMMARY** (2–3 sentences)
   - Overall performance of the RAG system.
   - Key strengths and weaknesses.

2. **DETAILED METRIC ANALYSIS**
   - Breakdown and interpretation of each metric.
   - Highlight areas of strong and weak performance.
   - Describe the impact of these scores on the user experience.

3. **PROBLEMS IDENTIFIED**
   - Specific issues in the RAG pipeline such as:
     - Context chunks not relevant to the query
     - Important context missing (low recall)
     - LLM generating incorrect or hallucinated answers
     - Answers not directly answering the user's query
     - Low-quality or unclear answers

4. **RECOMMENDATIONS (Understandable to Non-Engineers)**
   - **Context Retrieval**: Are the right chunks being retrieved? Should embedding model, chunk size, or retrieval filtering be improved?
   - **Prompt Quality**: Is the prompt to the LLM clear and effective? Should it be improved to better guide the LLM?
   - **Answer Generation**: How can answer relevance, clarity, and correctness be improved?

5. **IMPROVEMENT STRATEGIES**
   - Concrete, actionable improvements across:
     - Chunking strategy
     - Retrieval model or ranking technique
     - Prompt engineering
     - LLM usage or fine-tuning
     - Post-processing or QA validation steps

6. **OVERALL ASSESSMENT**
   - Summary of system quality.
   - Confidence level in recommendations.
   - Priority list for fixes or next steps.

Be concise, specific, and use plain language so that both engineers and product stakeholders can easily understand the insights and recommendations.

"""
        return prompt
    
    def call_llm_for_analysis(self, prompt):
        """
        Call LLM for analysis with retry logic.
        
        Args:
            prompt: Analysis prompt
            
        Returns:
            LLM response or None if failed
        """
        if not self.openai_client:
            return None
        
        for attempt in range(3):
            try:
                # Prepare API call parameters
                api_params = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "You are an expert RAG system analyst. Provide detailed, actionable insights."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                }
                
                # Add Azure-specific parameters if using Azure
                if self.model_type == "azure":
                    azure_config = self.config.get('azure', {})
                    api_params.update({
                        "api_version": azure_config.get('openai_api_version', '2024-02-15-preview'),
                        "azure_endpoint": azure_config.get('base_url'),
                        "azure_deployment": azure_config.get('model_deployment', self.model_name)
                    })
                
                response = self.openai_client.chat.completions.create(**api_params)
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                logger.warning(f"Analysis API call attempt {attempt + 1} failed: {str(e)}")
                if attempt == 2:
                    logger.error(f"All analysis API call attempts failed")
                    return None
                continue
        
        return None
    
    def save_analysis_results(self, analysis_text, output_file=None):
        """
        Save analysis results to file.
        
        Args:
            analysis_text: Analysis text from LLM
            output_file: Output file path (optional)
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"rag_analysis_report_{timestamp}.txt"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("RAG SYSTEM ANALYSIS REPORT\n")
                f.write("=" * 50 + "\n")
                f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Model used: {self.model_name} ({self.model_type.upper()})\n")
                f.write("=" * 50 + "\n\n")
                f.write(analysis_text)
            
            print(f"💾 Analysis report saved to: {output_file}")
            
        except Exception as e:
            print(f"❌ Error saving analysis report: {str(e)}")
    
    def analyze_rag_system(self, file_path, output_file=None):
        """
        Complete RAG system analysis pipeline.
        
        Args:
            file_path: Path to evaluation output file
            output_file: Output file for analysis report (optional)
        """
        print("🔍 Starting RAG System Analysis")
        print("=" * 50)
        
        # Load data
        df = self.load_evaluation_data(file_path)
        if df is None:
            print("❌ Failed to load evaluation data")
            return None
        
        # Prepare analysis data
        print("📊 Preparing analysis data...")
        analysis_data = self.prepare_analysis_data(df)
        
        # Generate analysis prompt
        print("🤖 Generating analysis prompt...")
        prompt = self.generate_analysis_prompt(analysis_data)
        
        # Call LLM for analysis
        print("🧠 Calling LLM for comprehensive analysis...")
        analysis_result = self.call_llm_for_analysis(prompt)
        
        if analysis_result:
            print("✅ Analysis completed successfully!")
            
            # Display analysis
            print("\n" + "=" * 60)
            print("📋 RAG SYSTEM ANALYSIS REPORT")
            print("=" * 60)
            print(analysis_result)
            print("=" * 60)
            
            # Save results
            self.save_analysis_results(analysis_result, output_file)
            
            return analysis_result
        else:
            print("❌ Failed to generate analysis")
            return None


def find_latest_evaluation_output():
    """
    Find the latest evaluation output file in the outputs directory.
    
    Returns:
        Path to the latest output file
    """
    outputs_dir = "outputs"
    pattern = os.path.join(outputs_dir, "*evaluation_output*.xlsx")
    
    import glob
    files = glob.glob(pattern)
    if not files:
        print(f"❌ No evaluation output files found in {outputs_dir}")
        return None
    
    # Sort by modification time to get the latest
    latest_file = max(files, key=os.path.getmtime)
    print(f"📁 Found latest evaluation output: {latest_file}")
    return latest_file


def main():
    """Main function to handle command line arguments and run analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze RAG system performance from evaluation output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rag_analysis.py
  python rag_analysis.py --input "outputs/NVR_Evaluation_evaluation_output_*.xlsx"
  python rag_analysis.py --input "outputs/NVR_Evaluation_evaluation_output_*.xlsx" --model azure
  python rag_analysis.py --output analysis_report.txt
        """
    )
    
    parser.add_argument("--input", "-i", help="Path to evaluation output file (default: latest)")
    parser.add_argument("--model", "-m", choices=["openai", "azure"], default="openai", 
                       help="Model type to use for analysis (default: openai)")
    parser.add_argument("--output", "-o", help="Output file for analysis report")
    
    args = parser.parse_args()
    
    print("RAG System Analysis Tool")
    print("=" * 60)
    print("Analyzing RAG system performance and generating recommendations...")
    print()
    
    try:
        # Determine input file
        if args.input:
            input_file = args.input
        else:
            input_file = find_latest_evaluation_output()
            if not input_file:
                return
        
        # Create analyzer
        analyzer = RAGAnalyzer(model_type=args.model)
        
        # Run analysis
        result = analyzer.analyze_rag_system(input_file, args.output)
        
        if result:
            print(f"\n✅ RAG system analysis completed successfully!")
            print("📊 Check the analysis report for detailed insights and recommendations.")
        else:
            print(f"\n❌ RAG system analysis failed!")
        
    except Exception as e:
        # logger.error(f"Error during analysis: {str(e)}")
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    main() 