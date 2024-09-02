from enum import Enum


class RAGComponents(int, Enum):
    GENERATOR = 1
    RETRIEVER = 2
    REWRITER = 3
    ROUTING = 4
    KNOWLEDGE_BASE = 5


QUESTION_ATTRIBUTION = {
    RAGComponents.GENERATOR: [
        "simple",
        "complex",
        "distracting element",
        "situational",
        "double",
    ],
    RAGComponents.RETRIEVER: ["simple", "distracting element", "multi-context"],
    RAGComponents.REWRITER: [
        "distracting element",
        "double",
        "conversational",
        "multi-context",
    ],
    RAGComponents.ROUTING: ["out of scope"],
    RAGComponents.KNOWLEDGE_BASE: ["out of scope"],
}

COMPONENT_DESCRIPTIONS = {
    "GENERATOR": "The Generator is the LLM inside the RAG to generate the answers.",
    "RETRIEVER": "The Retriever fetches relevant documents from the knowledge base according to a user query.",
    "REWRITER": "The Rewriter modifies the user query to match a predefined format or to include the context from the chat history.",
    "ROUTING": "The Router filters the query of the user based on his intentions (intentions detection).",
    "KNOWLEDGE_BASE": "The knowledge base is the set of documents given to the RAG to generate the answers. Its scores is computed differently from the other components: it is the difference between the maximum and minimum correctness score across all the topics of the knowledge base.",
}


CORRECTNESS_EVALUATION_SYSTEM_PROMPT = """Your role is to test AI agents. Your task consists in assessing whether an agent's output correctly answers a question. 
You are provided with the ground truth answer to the question. Your task is then to evaluate if the agent's answer is close to the ground truth answer. 

You are auditing the following agent:
{agent_description}

Think step by step and consider the agent's output in its entirety. Remember: you need to have a strong and sound reason to support your evaluation.
If the agent's answer is correct, return 1. If the agent's answer is incorrect, return 0 
You must output either 1 or 0

The question that was asked to the agent, its output, and the expected ground truth answer will be delimited with XML tags.
"""

CORRECTNESS_INPUT_TEMPLATE = """<question>
{question}
</question>

<agent_answer>
{agent_answer}
</agent_answer>

<ground_truth>
{ground_truth}
</ground_truth>
"""

CORRECTNESS_TRUE_EXAMPLE_INPUT = CORRECTNESS_INPUT_TEMPLATE.format(
    question="What is the capital of France?", agent_answer="The capital of France is Paris.", ground_truth="Paris."
)

CORRECTNESS_TRUE_EXAMPLE_OUTPUT = """1"""

CORRECTNESS_FALSE_EXAMPLE_INPUT = CORRECTNESS_INPUT_TEMPLATE.format(
    question="What is the capital of Denmark?",
    agent_answer="The capital of Denmark is Paris.",
    ground_truth="Copenhagen.",
)

CORRECTNESS_FALSE_EXAMPLE_OUTPUT = """0"""

QUESTION_CLASSIFICATION_SYSTEM_PROMPT = """Your role is to classify questions into specific types based on their characteristics. 
You are provided with a question, and you need to determine its type according to the following categories:

1. simple
2. complex
3. distracting element
4. situational
5. double

Think carefully about the question and consider its complexity, intent, and structure. Choose the most appropriate type from the list provided.

You must output one of the following types:
1. simple
2. complex
3. distracting element
4. situational
5. double

The question will be delimited with XML tags.
"""

QUESTION_CLASSIFICATION_INPUT_TEMPLATE = """<question>
{question}
</question>
"""

QUESTION_CLASSIFICATION_EXAMPLE_SIMPLE_INPUT = """<question>
What is the capital of France?
</question>"""

QUESTION_CLASSIFICATION_EXAMPLE_SIMPLE_OUTPUT = """simple"""

QUESTION_CLASSIFICATION_EXAMPLE_COMPLEX_INPUT = """<question>
Explain the impact of climate change on polar bear populations and their habitat.
</question>"""
QUESTION_CLASSIFICATION_EXAMPLE_COMPLEX_OUTPUT = """complex"""

QUESTION_CLASSIFICATION_EXAMPLE_DISTRACTING_ELEMENT_INPUT = """<question>
If you could have any superpower, what would it be?
</question>"""
QUESTION_CLASSIFICATION_EXAMPLE_DISTRACTING_ELEMENT_OUTPUT = """distracting element"""

QUESTION_CLASSIFICATION_EXAMPLE_SITUATIONAL_INPUT = """<question>
How would you handle a situation where you have to meet a tight deadline with limited resources?
</question>"""
QUESTION_CLASSIFICATION_EXAMPLE_SITUATIONAL_OUTPUT = """situational"""

QUESTION_CLASSIFICATION_EXAMPLE_DOUBLE_INPUT = """<question>
What are the benefits of exercise, and how does it impact mental health?
</question>"""
QUESTION_CLASSIFICATION_EXAMPLE_DOUBLE_OUTPUT = """double"""

AGENT_DESCRIPTION = "You are a logical, and context-aware evaluator"