import sys
sys.path.append('E:\\Projects\\SA - R&D\\chunking')
import warnings

warnings.filterwarnings("ignore",category=UserWarning)

from nltk.tokenize import word_tokenize
from utils.pdfExt import main
from pypdf import PdfReader
from fuzzywuzzy import fuzz
from openai import OpenAI
from pathlib import Path
from PIL import Image
import anthropic
import textwrap
import requests
import openai
import nltk
import json
import time 
import re
import io
import os
# nltk.download('punkt')

class CHunkingByGPT:
    
    def __init__(self,api_key:str,gpt_model_name:str):
        os.environ['GPT_KEY'] = api_key
        os.environ['GPT_MODEL_NAME'] = gpt_model_name
        
        
    @staticmethod
    def log(message:str,success_flag=True):
        
        if success_flag: print(f"\n\n###################   {message}   ###################")
        else: print(f"!!!!!!!!!!!!!!!!!!   {message}   !!!!!!!!!!!!!!!!!!!!")
        

    def extract_data(self,pdf_path_or_url : str, output_folder=r'./data/img') -> str:
        
        os.makedirs(output_folder, exist_ok=True)
        
        # If PDF is a URL, download it
        if pdf_path_or_url.startswith("http"):
            
            response = requests.get(pdf_path_or_url)
            self.log("Downloading the pdf.")
            
            if response.status_code == 200:
                pdf_data = response.content
            else:
                self.log(f"Failed to download PDF from {pdf_path_or_url}",True)
                return 404
        else:
        
            with open(pdf_path_or_url, 'rb') as f:
                pdf_data = f.read()

        reader = PdfReader(io.BytesIO(pdf_data))
        text = ''.join([page.extract_text() for page in reader.pages])
        wrapped_text = textwrap.fill(text, width=120)
        
        for page_num, page in enumerate(reader.pages, start=1):
            
            for i, image in enumerate(page.images, start=1):
                
                image_data = io.BytesIO(image.data)
                
                try:
                    
                    img = Image.open(image_data)
                    image_name = f"page{page_num}_img{i}"
                    
                    image_path = os.path.join(output_folder, f"{image_name}.{img.format.lower()}")
                    img.save(image_path)
                    self.log(f"Image extracted: {image_name}")
                    
                except Exception as e:
                    
                    self.log(f"Failed to extract image: {e}",True)
                            
        # print("\n\n")
        self.log("Extracted Text succesfully")
        
        return wrapped_text

    @staticmethod
    def format_text(self,raw_text:str):
        
        formatted_text = ' '.join(raw_text.split())
        formatted_text = ''.join(char if char.isalnum() or char.isspace() else ' ' for char in formatted_text)
        
        sections = formatted_text.split('   ')
        formatted_text = ''
        
        for section in sections:
            
            if section.strip():
                
                formatted_text += '   ' + section.strip() + '\n\n'

        return formatted_text.strip()


    # Call LLM
    def generate_raw_chunks(self,user_prompt:str):

        client = OpenAI(
            api_key=os.getenv('GPT_KEY')
        )
        
        system_prompt = """Given the provided text data, your task is to chunk the text into meaningful segments or 'chunks' based on the topics or sections mentioned within the text. Each chunk should encapsulate a distinct topic or subtopic discussed within the text corpus. Your goal is to parse the text into coherent units that represent the main themes or ideas conveyed in the text.

        You can identify the boundaries of each chunk by looking for section headers or topic labels within the text. These headers typically indicate the start of a new topic or section. Your output should consist of the identified chunks, along with their corresponding labels or headers.

        Please ensure that each chunk is clearly delineated and captures a cohesive set of information related to its respective topic or theme. Additionally, consider the overall structure and coherence of the chunks to facilitate understanding and interpretation by readers.

        Feel free to leverage the contextual information provided in the text to guide your chunking process. Remember, the objective is to organize the text into digestible segments that effectively convey the main ideas discussed within the text corpus.

        <important>Note: You should not modify the text in the corpus; your only job is to split (chunk) the corpus accordingly. your are strictly not allowed to reduce the content of chunk it should be same as the raw corpse provides. if the input corpse is 1000 tokents the output should also be 1000 tokens,if the input corpse is 2000 tokens the output tokents should be 2000.if a chunk croses 800 words please divide it if a chunk is 1600 words divide it by 800 woord chunk and 800 word chunk. 
        
        The chunks should follow a format like this:

        <chunk 1>
        Topic:topic for chunk 1
        Content:content of Chunk 1
        </chunk 1>
        ...
        
        Remember : you should not reduce content nor summarise it your only job is to divide corpse to chunks. the chunks should be a perfect sub-class of corpse(super-class).
        </important>

        """
        try:
            chat_completion = client.chat.completions.create(
                model=os.getenv('GPT_MODEL_NAME'),
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Here is the corpse\n <important> You are strictly not allowed to modify this corpse your only job is to split this corpse into chunks(that makes sense)</important>\n<corpse>\n {user_prompt} \n</corpse>"}
                ]
            )

            return chat_completion.choices[0].message.content
        
        except openai.APIConnectionError as e:
            warnings.warn("Network Error Retry Later",category=TimeoutError)
            sys.exit(-1)


    '''Multilingual Prompt'''
    # def generate_raw_chunks(user_prompt:str):
        
    #     client = OpenAI(
    #         api_key=os.getenv('GPT_KEY')
    #     )
        
    #     system_prompt = """We have a Retrieval-Augmented Generation (RAG) System that will chunk the content, rank it, and retrieve the correct chunks when queried. Your task is to thoroughly understand this document and chunk it wisely so that any question can be accurately answered. Ensure that no hallucinations occur and that all chunks are factual. Please retain every single word from the document.

    #     <important>Note: The document may have polish content so understand the content carefully ,You should not modify the text in the corpus; your only job is to split (chunk) the corpus accordingly. your are strictly not allowed to reduce the content of chunk it should be same as the raw corpse provides. if the input corpse is 1000 tokents the output should also be 1000 tokens,if the input corpse is 2000 tokens the output tokents should be 2000.if a chunk croses 800 words please divide it if a chunk is 1600 words divide it by 800 woord chunk and 800 word chunk. 
        
    #     The chunks should follow a format like this:

    #     <chunk 1>
    #     Topic:topic for chunk 1
    #     Content:content of Chunk 1
    #     </chunk 1>
    #     ...
        
    #     Remember : you should not reduce content nor summarise it your only job is to divide corpse to chunks. the chunks should be a perfect sub-class of corpse(super-class).
    #     </important>

    #     """
    #     try:
    #         chat_completion = client.chat.completions.create(
    #             model=os.getenv('GPT_MODEL_NAME'),
    #             max_tokens=4096,
    #             messages=[
    #                 {"role": "system", "content": system_prompt},
    #                 {"role": "user", "content": f"Here is the corpse\n <important> You are strictly not allowed to modify this corpse your only job is to split this corpse into chunks(that makes sense)</important>\n<corpse>\n {user_prompt} \n</corpse>"}
    #             ]
    #         )

    #         return chat_completion.choices[0].message.content
        
    #     except openai.APIConnectionError as e:
    #         warnings.warn("Network Error Retry Later",category=TimeoutError)
    #         sys.exit(-1)

    @staticmethod
    def split_corpse(text):
        max_tokens = 3900
        min_tokens = 3600
        paragraph_separator = '\n\n'
        
        tokens = word_tokenize(text)
        total_tokens = len(tokens)

        if total_tokens <= max_tokens:
            return [text]  # If the total number of tokens is within the range, return the original string as a single segment
        
        segments = []
        current_segment = []
        token_count = 0

        for token in tokens:
            token_count += 1  # Increment token count for each token
            current_segment.append(token)

            if token_count >= min_tokens and (token_count >= max_tokens or token == paragraph_separator):
                # If the token count reaches the minimum required, and either exceeds the maximum or a paragraph separator is found,
                # add the current segment to the segments list
                segments.append(' '.join(current_segment))
                current_segment = []
                token_count = 0
        
        # Add the last segment if there are any remaining tokens
        if current_segment:
            segments.append(' '.join(current_segment))

        return segments

    def pre_process(self,corpus, raw_chunks, save_flag, display_flag,is_folder,is_fresh,file_name):

        def convert_to_json(raw_data):

            topic_pattern = re.compile(r'Topic: (.+)')
            subtopic_pattern = re.compile(r'Subtopic: (.+)')
            content_pattern = re.compile(r'Content:\s*(.*?)\s*(?=\n<chunk \d+>|$)', re.DOTALL)
            formatted_chunks = []
            chunks = raw_data.split('<chunk')

            for chunk in chunks[1:]:
                formatted_chunk = {}
                topic_match = topic_pattern.search(chunk)
                if topic_match:
                    formatted_chunk['topic'] = topic_match.group(1).strip()

                subtopic_match = subtopic_pattern.search(chunk)
                if subtopic_match:
                    formatted_chunk['subtopic'] = subtopic_match.group(1).strip()

                content_match = content_pattern.search(chunk)
                if content_match:
                    content = content_match.group(1).strip()
                    content = re.sub(r'\n</chunk \d+>$', '', content)
                    formatted_chunk['content'] = content
                formatted_chunks.append(formatted_chunk)
                # with open(r'results\raw_chunks.json', 'w') as json_file:
                #     json.dump(formatted_chunks, json_file, indent=2)
            return formatted_chunks
        
        pre_form_json = convert_to_json(raw_chunks)

        contents = [content["content"] for content in pre_form_json]
        topics = [topic["topic"] for topic in pre_form_json]
        subtopics = [subtopic.get("subtopic", None) for subtopic in pre_form_json]
        
        output = []
        start_index = 0
        total_tokens = 0
        for idx, content in enumerate(contents):
            topic = topics[idx]
            subtopic = subtopics[idx]
            tokens = word_tokenize(content)
            
            if len(tokens) > 800:
                # Split content into smaller chunks
                num_chunks = len(tokens) // 800 + 1
                chunk_size = len(tokens) // num_chunks
                token_chunks = [tokens[i:i+chunk_size] for i in range(0, len(tokens), chunk_size)]
                chunked_content = [' '.join(chunk) for chunk in token_chunks]
            else:
                chunked_content = [content]
            total_tokens += len(tokens)
            
            for chunk_content in chunked_content:
                end_index = min(len(corpus), start_index + len(chunk_content))
                if subtopic != None:
                    output.append({
                    "title": topic,
                    "subtopic":subtopic,
                    "content": chunk_content,
                    "start_index": start_index,
                    "end_index": end_index,
                    "num_tokens":len(tokens),
                    "doc_name" : file_name
                }) 
                    
                else:
                    output.append({
                    "title": topic,
                    "content": chunk_content,
                    "start_index": start_index,
                    "end_index": end_index,
                    "num_tokens":len(tokens),
                    "doc_name" : file_name
                })
                
                start_index = end_index + 1
                
        if display_flag:
            print(json.dumps(output, indent=2))
            
        if save_flag:
            file_path = r'../src\results\chunks.json'
            if is_folder:
                if is_fresh:
                    existing_data = []
                else:
                    with open(file_path, 'r') as file:
                        existing_data = json.load(file)
                
                existing_data.extend(output)

                with open(file_path, 'w') as json_file:
                    json.dump(existing_data, json_file, indent=2)
            
            else:
                with open(file_path, 'w') as json_file:
                    json.dump(output, json_file, indent=2)
                
        else:
            warnings.warn("Note : Chunks are not saved \n Reason : save_flag - False ",category=Warning)
                
            
        return False
                
        
            
    def chunk_single_pdf(self,timer : bool,pdf_path : str,display_flag = False,save_flag  = True):
        
        if timer:
            start_time = time.time()
        
        self.log("Called PDF extracter")
        try:
            corpus,file_name = main(pdf_filepath=pdf_path)
        except FileNotFoundError as e:
            print("cant open file")
            sys.exit(-1)
            
        self.log("Extracted PDF data")
        corpus = self.format_text(self,raw_text=corpus)
        print(corpus)
        result = self.split_corpse(corpus)
        raw_chunk = ''
        
        self.log("Genrating raw chunks")
        for segment in result:
            raw_chunk_ = self.generate_raw_chunks(user_prompt=segment)
            raw_chunk += "\n\n" + raw_chunk_
        # log("Raw Chunks")
        # print(raw_chunk)
        
        self.log("Post Processing chunks")
        self.pre_process(corpus=corpus,raw_chunks=raw_chunk,save_flag=save_flag,display_flag=display_flag,is_folder=False,is_fresh=True,file_name=file_name)
        
        if timer:
            end_time = time.time()
            total_time = end_time - start_time
            self.log(f" Total time taken to run: {total_time}")


    def chunk_multiple_pdf(self,timer : bool,folder_path : str,display_flag = False,save_flag  = True):
        
        if timer:
            start_time = time.time()
            
        is_fresh = True
        # log("Called PDF extracter")
        for filename in os.listdir(folder_path):
            # Check if the file is a PDF
            if filename.endswith('.pdf'):
                pdf_path = os.path.join(folder_path, filename)
                try:
                    corpus,file_name = main(pdf_filepath=pdf_path)
                except FileNotFoundError as e:
                    print("cant open file")
                    sys.exit(-1)
            
                # log(f"Extracted PDF data for {filename}")
                corpus = self.format_text(self,raw_text=corpus)
                # print(corpus)
                result = self.split_corpse(corpus)
                raw_chunk = ''
                
                # log("Genrating raw chunks for {filename}")
                for segment in result:
                    raw_chunk_ = self.generate_raw_chunks(user_prompt=segment)
                    raw_chunk += "\n\n" + raw_chunk_
                # log("Raw Chunks")
                # print(raw_chunk)
                
                # log(f"Post Processing raw chunks for {filename}")
                is_fresh = self.pre_process(corpus=corpus,raw_chunks=raw_chunk,save_flag=save_flag,display_flag=display_flag,is_folder=True,is_fresh=is_fresh,file_name=file_name)
                self.log(f"Chunked {filename} succesfully")
                
        if timer:
            end_time = time.time()
            total_time = end_time - start_time
            self.log(f" Total time taken to run: {total_time}")

# if __name__ == "__main__":
    
#     os.environ['GPT_KEY'] = 'Your Key Here'
#     os.environ['GPT_MODEL_NAME'] = "gpt-4o-mini"
#     chunk_single_pdf(timer=True,pdf_path = r"Enter Your PDF path here",display_flag=False,save_flag=True)

