import pandas as pd


class ResultsConverter:
    def __init__(self, ragas_results: pd.DataFrame, crag_results: pd.DataFrame, llm_results: pd.DataFrame = None):
        self.ragas_results = ragas_results
        self.crag_results = crag_results
        self.llm_results = llm_results if llm_results is not None else pd.DataFrame()

    def convert_ragas_results(self):
        """Converts column names in the Ragas Results DataFrame for consistency."""
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

    def convert_crag_results(self):
        """Converts column name 'prediction' to 'answer' in the CRAG Results DataFrame."""
        if 'prediction' in self.crag_results.columns:
            self.crag_results.rename(columns={'prediction': 'answer'}, inplace=True)

    def convert_llm_results(self):
        """Converts column names in the LLM Results DataFrame for consistency."""
        # LLM results should already have standardized column names
        pass

    def get_crag_results(self):
        return self.crag_results

    def get_ragas_results(self):
        return self.ragas_results

    def get_llm_results(self):
        return self.llm_results

    def get_combined_results(self):
        """Combines the converted Ragas, CRAG, and LLM results DataFrames."""
        dfs_to_combine = []
        
        # Add non-empty DataFrames to combination list
        if not self.ragas_results.empty:
            dfs_to_combine.append(self.ragas_results.reset_index(drop=True))
            
        if not self.crag_results.empty:
            dfs_to_combine.append(self.crag_results.reset_index(drop=True))
            
        if not self.llm_results.empty:
            dfs_to_combine.append(self.llm_results.reset_index(drop=True))
        
        if not dfs_to_combine:
            return pd.DataFrame()

        # Combine the DataFrames
        combined_results = pd.concat(dfs_to_combine, axis=1)

        # Remove duplicate columns while keeping the first occurrence
        combined_results = combined_results.loc[:, ~combined_results.columns.duplicated()]

        return combined_results


