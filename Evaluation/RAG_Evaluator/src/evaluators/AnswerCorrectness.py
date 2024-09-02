import os
from openai import OpenAI
import pandas as pd
from tqdm import tqdm
from prompts.Prompt_And_Mappings import (RAGComponents,
                                         QUESTION_ATTRIBUTION,
                                         CORRECTNESS_EVALUATION_SYSTEM_PROMPT,
                                         CORRECTNESS_INPUT_TEMPLATE,
                                         CORRECTNESS_TRUE_EXAMPLE_INPUT,
                                         CORRECTNESS_TRUE_EXAMPLE_OUTPUT,
                                         CORRECTNESS_FALSE_EXAMPLE_INPUT,
                                         CORRECTNESS_FALSE_EXAMPLE_OUTPUT,
                                         QUESTION_CLASSIFICATION_SYSTEM_PROMPT,
                                         QUESTION_CLASSIFICATION_INPUT_TEMPLATE,
                                         QUESTION_CLASSIFICATION_EXAMPLE_SIMPLE_INPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_SIMPLE_OUTPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_COMPLEX_INPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_COMPLEX_OUTPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_DISTRACTING_ELEMENT_INPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_DISTRACTING_ELEMENT_OUTPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_SITUATIONAL_INPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_SITUATIONAL_OUTPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_DOUBLE_INPUT,
                                         QUESTION_CLASSIFICATION_EXAMPLE_DOUBLE_OUTPUT, AGENT_DESCRIPTION)

class Report():
    def __init__(self, model):
        self.model = model
        self.agent_description = AGENT_DESCRIPTION
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def calculate_correctness(self, question, reference_answer, answer):
        chat_completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                 "content": CORRECTNESS_EVALUATION_SYSTEM_PROMPT.format(agent_description=self.agent_description)},
                {"role": "user", "content": CORRECTNESS_TRUE_EXAMPLE_INPUT},
                {"role": "assistant", "content": CORRECTNESS_TRUE_EXAMPLE_OUTPUT},
                {"role": "user", "content": CORRECTNESS_FALSE_EXAMPLE_INPUT},
                {"role": "assistant", "content": CORRECTNESS_FALSE_EXAMPLE_OUTPUT},
                {"role": "user", "content": CORRECTNESS_INPUT_TEMPLATE.format(
                    question=question,
                    agent_answer=answer,
                    ground_truth=reference_answer,
                )},
            ],
            temperature=0,
        )
        response_content = chat_completion.choices[0].message.content
        if response_content in {'1', '0'}:
            return int(response_content)
        else:
            return 0

    def classify_question_type(self, question):
        chat_completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": QUESTION_CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": QUESTION_CLASSIFICATION_EXAMPLE_SIMPLE_INPUT},
                {"role": "assistant", "content": QUESTION_CLASSIFICATION_EXAMPLE_SIMPLE_OUTPUT},
                {"role": "user", "content": QUESTION_CLASSIFICATION_EXAMPLE_COMPLEX_INPUT},
                {"role": "assistant", "content": QUESTION_CLASSIFICATION_EXAMPLE_COMPLEX_OUTPUT},
                {"role": "user", "content": QUESTION_CLASSIFICATION_EXAMPLE_DISTRACTING_ELEMENT_INPUT},
                {"role": "assistant", "content": QUESTION_CLASSIFICATION_EXAMPLE_DISTRACTING_ELEMENT_OUTPUT},
                {"role": "user", "content": QUESTION_CLASSIFICATION_EXAMPLE_SITUATIONAL_INPUT},
                {"role": "assistant", "content": QUESTION_CLASSIFICATION_EXAMPLE_SITUATIONAL_OUTPUT},
                {"role": "user", "content": QUESTION_CLASSIFICATION_EXAMPLE_DOUBLE_INPUT},
                {"role": "assistant", "content": QUESTION_CLASSIFICATION_EXAMPLE_DOUBLE_OUTPUT},
                {"role": "user", "content": QUESTION_CLASSIFICATION_INPUT_TEMPLATE.format(question=question)},
            ],
            temperature=0,
        )
        response_content = chat_completion.choices[0].message.content.strip().lower()
        valid_types = ["simple", "complex", "distracting element", "situational", "double"]
        return response_content if response_content in valid_types else "simple"

    def evaluate_queries(self, queries, answers, ground_truths, question_types):
        assert len(queries) == len(answers) == len(
            ground_truths) == len(question_types), "Length of queries, answers, and ground truths must be the same."

        correctness_results = []

        # Use tqdm to show progress
        for i in tqdm(range(len(queries)), desc="Evaluating queries"):
            question = queries[i]
            answer = answers[i]
            ground_truth = ground_truths[i]
            correctness = self.calculate_correctness(question, ground_truth, answer)
            correctness_results.append(correctness)
            question_type = question_types[i]

        correctness_df = pd.DataFrame({
            'question': queries,
            'correctness': correctness_results,
            'question_type': question_type
        })

        # Compute average correctness for each question type
        avg_correctness_by_type = correctness_df.groupby('question_type')['correctness'].mean()

        # Compute component scores
        component_scores_df = self.component_scores(avg_correctness_by_type)

        # Calculate overall score
        total_score = sum(correctness_results)
        average_score = total_score / len(queries) if queries else 0

        return average_score, component_scores_df

    def component_scores(self, avg_correctness_by_type) -> pd.DataFrame:
        """
        Compute the scores for each RAG component based on average correctness for each question type.
        """
        # Assume that `QUESTION_ATTRIBUTION` maps components to question types
        available_question_types = {
            component: list(set(attribution).intersection(avg_correctness_by_type.index))
            for component, attribution in QUESTION_ATTRIBUTION.items()
        }

        scores = {
            component: (
                [sum(1 / len(attribution) * avg_correctness_by_type[q_type] for q_type in attribution)]
                if len(attribution) > 0
                else [1]
            )
            for component, attribution in available_question_types.items()
        }
        score_df = pd.DataFrame.from_dict(scores, orient="index")
        score_df.columns = ["score"]
        score_df.index.rename("RAG Components", inplace=True)
        score_df.index = score_df.index.map(lambda x: RAGComponents(x).name)
        return score_df
