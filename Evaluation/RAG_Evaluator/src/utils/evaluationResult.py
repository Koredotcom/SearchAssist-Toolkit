import pandas as pd


class ResultsConverter:
    def __init__(self, ragas_results: pd.DataFrame, crag_results: pd.DataFrame):
        self.ragas_results = ragas_results
        self.crag_results = crag_results

    def convert_ragas_results(self):
        """Converts column name 'question' to 'query' in the Ragas Results DataFrame."""
        if 'question' in self.ragas_results.columns:
            self.ragas_results.rename(columns={'question': 'query'}, inplace=True)
            print("Converted 'question' to 'query' in Ragas results.")
        else:
            print("'question' column not found in Ragas results.")

    def convert_crag_results(self):
        """Converts column name 'prediction' to 'answer' in the CRAG Results DataFrame."""
        if 'prediction' in self.crag_results.columns:
            self.crag_results.rename(columns={'prediction': 'answer'}, inplace=True)
            print("Converted 'prediction' to 'answer' in CRAG results.")
        else:
            print("'prediction' column not found in CRAG results.")

    def get_crag_results(self):
        return self.crag_results

    def get_ragas_results(self):
        return self.ragas_results

    def get_combined_results(self):
        """Combines the converted Ragas results and CRAG results DataFrames."""
        # Assuming both DataFrames have the same number of rows
        if len(self.ragas_results) != len(self.crag_results):
            print("Warning: Ragas and CRAG results have different row counts. Combining may lead to misalignment.")

        # Combine the DataFrames
        combined_results = pd.concat([self.ragas_results.reset_index(drop=True), self.crag_results.reset_index(drop=True)], axis=1)

        # Remove duplicate columns while keeping the first occurrence
        combined_results = combined_results.loc[:, ~combined_results.columns.duplicated()]

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