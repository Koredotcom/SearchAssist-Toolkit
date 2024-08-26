import sys
sys.path.append('Extraction\chunking_based_on_llms\resources')
from nltk.tokenize import word_tokenize
from pypdf import PdfReader
from fuzzywuzzy import fuzz
from PIL import Image
import nltk
import anthropic
import textwrap
import requests
import json
import re
import io
import os
from utils.pdfExt import main
nltk.download('punkt')


def log(message:str,success_flag=True):
    
    if success_flag: print(f"\n\n###################   {message}   ###################")
    else: print(f"!!!!!!!!!!!!!!!!!!   {message}   !!!!!!!!!!!!!!!!!!!!")
    

def extract_data(pdf_path_or_url : str, output_folder=r'./data/img') -> str:
    
    os.makedirs(output_folder, exist_ok=True)
    
    # If PDF is a URL, download it
    if pdf_path_or_url.startswith("http"):
        
        response = requests.get(pdf_path_or_url)
        log("Downloading the pdf.")
        
        if response.status_code == 200:
            pdf_data = response.content
        else:
            log(f"Failed to download PDF from {pdf_path_or_url}",True)
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
                log(f"Image extracted: {image_name}")
                
            except Exception as e:
                
                log(f"Failed to extract image: {e}",True)
                           
    # print("\n\n")
    log("Extracted Text succesfully")
    
    return wrapped_text


def format_text(raw_text:str):
    
    formatted_text = ' '.join(raw_text.split())
    formatted_text = ''.join(char if char.isalnum() or char.isspace() else ' ' for char in formatted_text)
    
    sections = formatted_text.split('   ')
    formatted_text = ''
    
    for section in sections:
        
        if section.strip():
            
            formatted_text += '   ' + section.strip() + '\n\n'

    return formatted_text.strip()


# Call LLM
def generate_raw_chunks(user_prompt:str)->str:
    
    client = anthropic.Client(api_key="Your api key here")

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
    
    log("Genrating raw chunks")
    
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=4096,
        system=system_prompt,
        messages=
        [
            {"role": "user", "content": f"Here is the corpse\n <important> You are strictly not allowed to modify this corpse your only job is to split this corpse into chunks(that makes sense)</important>\n<corpse>\n {user_prompt} \n</corpse>"}
        ]
    )

    return response.content[0].text


def pre_process(corpus : str, raw_chunks : str, test_flag : bool, save_flag : bool, display_flag : bool)->None:
    
    log("Post processing raw chunks")
    
    def convertToJSON(raw_chunks):
        
        chunks = re.findall(r'<chunk (\d+)>\nTopic: (.*?)\nContent: (.*?)\n</chunk \d+>', raw_chunks, re.DOTALL)
        chunks_dict = []
        for chunk_num, topic, content in chunks:
            
            chunks_dict.append({'Topic': topic, 'Content': content})
            # print(chunks_dict)
        return chunks_dict
    
    pre_form_json = convertToJSON(raw_chunks)
    # print(pre_form_json)
    
    contents = [content["Content"] for content in pre_form_json]
    topics = [topic["Topic"] for topic in pre_form_json]
    
    output = []
    start_index = 0
    
    for idx, content in enumerate(contents):
        
        topic = topics[idx]
       
        tokens = word_tokenize(content)
        
        # Check if content exceeds 800 tokens
        if len(tokens) > 800:
            # Split content into smaller chunks
            num_chunks = len(tokens) // 800 + 1
            chunk_size = len(tokens) // num_chunks
            
            token_chunks = [tokens[i:i+chunk_size] for i in range(0, len(tokens), chunk_size)]
            
            chunked_content = [' '.join(chunk) for chunk in token_chunks]
        else:
            chunked_content = [content]
        
        for chunk_content in chunked_content:
            # ignore this for now finding better ways to find indexes
            match = fuzz.partial_ratio(corpus, chunk_content)
            
            end_index = min(len(corpus), start_index + len(chunk_content))
            
            output.append({
                "topic": topic,
                "content": chunk_content,
                "start_index": start_index,
                "end_index": end_index
            })
            
            
            start_index = end_index + 1
    
    if save_flag:
        with open('chunks.json', 'w') as json_file:
            json.dump(output, json_file, indent=2)
        log("please Take a look at chunks.json for chunks")
    
    if display_flag:
        print(json.dumps(output, indent=4))
        
        
if __name__ == "__main__":
    
    import time 
    
    start_time = time.time()
    log("Called PDF extracter")
    corpus = main(r"sample\resources\data\Companycar.pdf")
    log("Extracted PDF data")
    print(corpus)
    # corpus = format_text(corpus)
    raw_chunk = generate_raw_chunks(user_prompt=corpus)
    log("Raw Chunks")
    print(raw_chunk)
    pre_process(corpus=corpus,raw_chunks=raw_chunk,test_flag=False,save_flag=True,display_flag=False)
    end_time = time.time()
    
    # Calculate the total time taken
    total_time = end_time - start_time
    
    log(f" Total time taken to run: {total_time}")
