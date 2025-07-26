import pandas as pd


class ResultsConverter:
    def __init__(self, ragas_results: pd.DataFrame, crag_results: pd.DataFrame, llm_results: pd.DataFrame = None):
        self.ragas_results = ragas_results
        self.crag_results = crag_results
        self.llm_results = llm_results if llm_results is not None else pd.DataFrame()

    def convert_ragas_results(self):
        """Converts column names in the Ragas Results DataFrame for consistency."""
        print(f"🔧 Converting RAGAS results columns...")
        print(f"   Before conversion: {list(self.ragas_results.columns)}")
        
        # Handle common RAGAS column name mappings
        column_mappings = {
            'question': 'query',
            'user_input': 'query',
            'response': 'answer',
            'retrieved_contexts': 'context',
            'reference': 'ground_truth'
        }
        
        # Apply mappings if columns exist
        columns_to_rename = {}
        for old_name, new_name in column_mappings.items():
            if old_name in self.ragas_results.columns:
                columns_to_rename[old_name] = new_name
                
        if columns_to_rename:
            self.ragas_results.rename(columns=columns_to_rename, inplace=True)
            print(f"   Renamed columns: {columns_to_rename}")
        else:
            print("   No column mappings applied")
            
        print(f"   After conversion: {list(self.ragas_results.columns)}")

    def convert_crag_results(self):
        """Converts column name 'prediction' to 'answer' in the CRAG Results DataFrame."""
        if 'prediction' in self.crag_results.columns:
            self.crag_results.rename(columns={'prediction': 'answer'}, inplace=True)
            print("Converted 'prediction' to 'answer' in CRAG results.")
        else:
            print("'prediction' column not found in CRAG results.")

    def convert_llm_results(self):
        """Converts column names in the LLM Results DataFrame for consistency."""
        # LLM results should already have standardized column names
        print("LLM results columns standardized.")

    def get_crag_results(self):
        return self.crag_results

    def get_ragas_results(self):
        return self.ragas_results

    def get_llm_results(self):
        return self.llm_results

    def get_combined_results(self):
        """Combines the converted Ragas, CRAG, and LLM results DataFrames."""
        print(f"🔗 Combining evaluation results...")
        
        dfs_to_combine = []
        
        # Add non-empty DataFrames to combination list
        if not self.ragas_results.empty:
            print(f"   ✅ Adding RAGAS results: {self.ragas_results.shape} with columns: {list(self.ragas_results.columns)}")
            dfs_to_combine.append(self.ragas_results.reset_index(drop=True))
        else:
            print(f"   ❌ RAGAS results empty, skipping")
            
        if not self.crag_results.empty:
            print(f"   ✅ Adding CRAG results: {self.crag_results.shape} with columns: {list(self.crag_results.columns)}")
            dfs_to_combine.append(self.crag_results.reset_index(drop=True))
        else:
            print(f"   ❌ CRAG results empty, skipping")
            
        if not self.llm_results.empty:
            print(f"   ✅ Adding LLM results: {self.llm_results.shape} with columns: {list(self.llm_results.columns)}")
            dfs_to_combine.append(self.llm_results.reset_index(drop=True))
        else:
            print(f"   ❌ LLM results empty, skipping")
        
        if not dfs_to_combine:
            print("⚠️ Warning: No results to combine.")
            return pd.DataFrame()
        
        # Check row count consistency
        row_counts = [len(df) for df in dfs_to_combine]
        if len(set(row_counts)) > 1:
            print(f"⚠️ Warning: Result DataFrames have different row counts: {row_counts}. Combining may lead to misalignment.")

        # Combine the DataFrames
        print(f"🔄 Concatenating {len(dfs_to_combine)} DataFrames...")
        combined_results = pd.concat(dfs_to_combine, axis=1)

        # Remove duplicate columns while keeping the first occurrence
        duplicated_columns = combined_results.columns[combined_results.columns.duplicated()].tolist()
        if duplicated_columns:
            print(f"🔧 Removing duplicate columns: {duplicated_columns}")
        combined_results = combined_results.loc[:, ~combined_results.columns.duplicated()]

        print(f"✅ Final combined results: {combined_results.shape} with columns: {list(combined_results.columns)}")
        return combined_results


# Example usage:
if __name__ == "__main__":
    # Sample DataFrames (replace these with actual DataFrames in practice)
    ragas_results = pd.DataFrame({'question': ['What is AI?', 'Define ML.'], 'other_col': [1, 2]})
    crag_results = pd.DataFrame({'prediction': ['AI is a field.', 'ML is a subset of AI.'], 'another_col': [3, 4]})

    converter = ResultsConverter(ragas_results, crag_results)

    # Convert columns
    converter.convert_ragas_results()
    converter.convert_crag_results()

    # Get combined results
    combined_results = converter.get_combined_results()

    print("\nCombined Results:")
    print(combined_results)