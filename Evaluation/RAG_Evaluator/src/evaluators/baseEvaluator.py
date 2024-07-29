# src/evaluators/baseEvaluator.py

from abc import ABC, abstractmethod

class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(self, queries, answers, ground_truths, contexts):
        pass

    @abstractmethod
    def process_results(self, results):
        pass