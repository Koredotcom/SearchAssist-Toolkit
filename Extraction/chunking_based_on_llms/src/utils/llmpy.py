import sys

sys.path.append(r"E:\\Projects\\SA - R&D\\chunking")

import requests
import json
from langchain_nvidia_ai_endpoints import ChatNVIDIA
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from langchain_community.llms import HuggingFacePipeline
from GenerativeAIExamples.RetrievalAugmentedGeneration.common.utils import get_llm, get_config


class NvidiaLLM:
    def __init__(self, model_name, is_response_generator: bool = False, **kwargs):

        # LLM is used for response generation as well as for generating description
        # of images, only use llm from configuration for response generator
        if is_response_generator:
            self.llm = get_llm(**kwargs)
        else:
            self.llm = ChatNVIDIA(model=model_name,
                            temperature = kwargs.get('temperature', 0.6),
                            top_p = kwargs.get('top_p', 0.3),
                            max_tokens = kwargs.get('max_tokens', 1024))


class LocalLLM:
    def __init__(self, model_path):
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, 
            torch_dtype=torch.float16,
            trust_remote_code=True,
            device_map="auto"
            )

        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_length=1024,
            temperature=0.6,
            top_p=0.3,
            repetition_penalty=1.0
        )

        self.llm = HuggingFacePipeline(pipeline=pipe)


def create_llm(model_name, model_type="NVIDIA", is_response_generator=False):
    # Use LLM to generate answer
    if model_type == "NVIDIA":
        model = NvidiaLLM(model_name, is_response_generator)
    elif model_type == "LOCAL":
        model = LocalLLM(model_name)
    else:
        print("Error! Need model_name and model_type!")
        exit()

    return model.llm


if __name__ == "__main__":
    llm = create_llm("gpt2", "LOCAL")

    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain import LLMChain

    system_prompt = ""
    prompt = "who are you"
    langchain_prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", "{input}")])
    chain = langchain_prompt | llm | StrOutputParser()

    response = chain.stream({"input": prompt})

    for chunk in response:
        print(chunk)

