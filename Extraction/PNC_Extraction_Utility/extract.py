# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import asyncio
import argparse
import copy
import os
import json
import time
import re
import aiofiles
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from openai import AsyncOpenAI
import dirtyjson

OPENAI_KEY = os.environ['OPENAI_KEY']

open_ai_conf = {
    "API_BASE":"https://api.openai.com/v1/",
    "model": "gpt-3.5-turbo-16k",
    "API_KEY":OPENAI_KEY,
    "max_tokens":2000,
    "temperature":0.5,
    "top_p":1,
    "timeout":150,
    "max_retries":0
}
prompt_json = [
    {
      "role": "system",
      "content": "{{instruction_msg}}\n--------------------------------------------------"
                  "----------------------------------------------------------------------\n\nContent:-{{content}}"
    }
  ]
instruction_msg = "Given an markdown for a possible table of content for a document, understand the text and identify table of contents with correct heading and subheadings.  Please note that there may be some extra info in the input text, which may not be needed for the index, use you knowledge to decide what to include in the index.\nFigure out add the parents of each subheading and return a lookup table map, which maps a heading to its hierarchical heading with all the parents appended as prefix.  \nCHILD HEADING SHOULD BE PRESENT IN THE VALUE ALWAYS.\nMap should be like:-\n{\n\"Child heading 1\": \"prefix1 prefix2 Child heading 1\",\n\"Child heading 2\": \" \"<prefix1 prefix2 Child heading 2\",\n...\n}"
openai_client = AsyncOpenAI(
            base_url= open_ai_conf.get("API_BASE", ""),
            api_key= open_ai_conf.get("API_KEY", ""),
            max_retries=open_ai_conf.get("MAX_RETRIES", 0),
        )
common_index_tag = "a"


async def parse_html(file_path):
    # Opening the html file
    HTMLFile = open(file_path, "r")
    # Reading the file
    index = HTMLFile.read()
    return index

def replace_backslashes(input_string):
    pattern = r'\\\\{2,}'
    # Define the replacement string
    replacement = r'\\\\'
    return re.sub(pattern, replacement, input_string)
def clean_json(json_str):
    data = dict(dirtyjson.loads(json_str))
    json_string = data.get("raw_data", "")
    json_string = json_string.replace("\n","").replace("\t","")
    json_string = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'', json_string)
    json_string = replace_backslashes(json_string)
    data['raw_data'] = json.loads(json_string)
    return data

async def parse_json(file_path):
    # Opening the html file
    with open(file_path, 'r') as file:
        data = file.read()
        cleaned_json = clean_json(data)
        raw_data = cleaned_json.get("raw_data", {})
        layout_items = raw_data.get("layoutItems",[])
        html_string = ""
        for item in layout_items:
            if item.get("type","") in ["RICH_TEXT_AREA","TEXT"] :
                if item.get("value", ""):
                    html_string += item.get("value")
    return html_string
async def extract_toc (soup_obj):
    index_tags = ['ul']
    toc_html = list()
    for tag in index_tags:
        toc_html.append(soup_obj.find(tag))
    return toc_html

class OpenaiResponseHandler:
    def __init__(self, response):
        self.response = response

    def get_raw_format(self):
        return self.response

    def get_json_format(self):
        chat_id = self.response.id
        completion_usage_dict = self.response.usage.__dict__
        json_str = json.dumps(completion_usage_dict)
        choices = []
        completion_usage_dict = self.response.usage.__dict__
        json_str = json.dumps(completion_usage_dict)
        if self.response.choices:
            for choice in self.response.choices:
                choice_data = {
                    'message': {
                        'content': choice.message.content,
                        'role': choice.message.role,
                    }
                }
                choices.append(choice_data)
        output = {
            'chat_id': chat_id,
            'choices': choices,
            'usage': json_str
            # Include other fields attributes as needed
        }
        return output


async def get_llm_response(content, instruction_msg):
    curr_prompt = copy.deepcopy(prompt_json)
    content_template = curr_prompt[0].get("content","")
    content_template =content_template.replace("{{instruction_msg}}",instruction_msg).replace("{{content}}",content)
    curr_prompt[0]["content"] = content_template
    model = open_ai_conf.get("model")
    timeout = open_ai_conf.get("timeout")
    max_tokens = open_ai_conf.get("max_tokens")
    temperature = open_ai_conf.get("temperature")
    top_p = open_ai_conf.get("top_p")
    request_payload = dict(model=model,
                           messages=curr_prompt,
                           temperature=temperature,
                           max_tokens=max_tokens,
                           top_p=top_p,
                           frequency_penalty=open_ai_conf.get('frequency_penalty', 0),
                           presence_penalty=open_ai_conf.get('presence_penalty', 0),
                           timeout=timeout)
    print('**Open AI Request {}'.format(request_payload))
    start_time = time.time()
    completion = await openai_client.chat.completions.create(**request_payload)
    openai_response_handler = OpenaiResponseHandler(completion)

    completion_json_format = openai_response_handler.get_json_format()
    print("Time taken in one OpenAI call {}".format(time.time()-start_time))
    print('**Open Ai Response** {}'.format(completion_json_format))
    return completion_json_format

async def fetch_lookup_from_llm_response(llm_response,toc_html):
    lookup_string = llm_response.get("choices",[])[0].get("message",{}).get("content","")
    lookup_json = json.loads(lookup_string)
    lookup_with_id = dict()
    heading_ids = dict()
    #list of tocs, usually single
    for key, value in lookup_json.items():
        if lookup_with_id.get(key) is None:
            for toc in toc_html:
                anchor_tag = toc.find(common_index_tag, string=key)
                if anchor_tag:
                    heading_id =anchor_tag['href']
                    lookup_with_id[key] = dict(value = lookup_json[key], heading_id = heading_id)
                    heading_ids[heading_id] = True
    # stripped_lowercased_lookup = {key.strip().lower(): value for key, value in lookup_json.items()}
    return lookup_with_id, heading_ids


def check_tag(tag, heading_ids):
    if tag.name == "a" and heading_ids.get("#" + str(tag.get("id", ""))):
        return True

    for child in tag.children:
        if hasattr(child, 'children'):  # Ensure the child is a tag and not a string or comment
            if(check_tag(child, heading_ids)):
                print(f"Found a match inside : {tag}")
                return check_tag(child, heading_ids)
    return False
def collect_intermediate_tags(soup, start_tag, heading_ids):
    current_tag = start_tag
    intermediate_tags = ""
    if start_tag.name == 'h3' and start_tag.find('a', id="Researching_a_Transaction") is not None:
        print("found a parent")
    current_tag = current_tag.find_next()
    # Navigate through the document from start_tag to end_tag
    while current_tag:
        if check_tag(current_tag, heading_ids):
            break
        if current_tag.parent and current_tag.parent.get("added_as_content"):
            print("Content already added")
        else:
            intermediate_tags += str(current_tag)
        current_tag['added_as_content'] = True
        current_tag = current_tag.find_next()
    return intermediate_tags
def extract_chunks_using_heading_id(soup, lookup_table,  heading_ids):
    chunks = list()
    for key, item in lookup_table.items():
        if type(item)==dict:
            heading_id = item['heading_id'].lstrip('#')  # Remove the leading '#' for id lookup
            new_value = item['value']
            # Find the anchor tag with the specified id
            anchor_tag = soup.find('a', id=heading_id)
            if anchor_tag:
                parent = anchor_tag.parent
                if parent:
                    # Replace the entire text of the parent element with new value
                    content_html = collect_intermediate_tags(soup, anchor_tag,heading_ids)
                    # content_html = str(content) for content in content_html
                    # parent.string = new_value
                    chunks.append(dict(heading = new_value, content = content_html))
    return chunks

def split_into_chunks(text, heading_start, heading_end):
    raw_chunks = text.split(heading_start)
    chunks = list()
    for raw_chunk in raw_chunks:
        splitted_chunk = raw_chunk.split(heading_end)
        heading = ""
        if len(splitted_chunk)==1:
            content = splitted_chunk[0]
        else:
            heading = splitted_chunk[0]
            content = splitted_chunk[1]
        chunks.append(dict(heading = heading, content = content))
    return chunks

async def convert_to_SA_format(chunks, **kwargs):
    data_list = list()
    for chunk in chunks:
        data = {
            "title" : chunk.get("heading", kwargs.get("filename","")),
            "content": chunk.get("content"),
            "url": kwargs.get("url",""),
            "meta_data":kwargs.get("meta_data",{}),
            "doc_name" : kwargs.get("filename","")
        }
        data_list.append(data)
    return data_list
def convert_chunks_to_markdown(chunks):
    for chunk in chunks:
        if chunk.get("content",""):
            chunk['content'] = md(chunk.get('content'))
    return chunks
async def extract_chunks(input_html, **kwargs):
    soup =  BeautifulSoup(input_html, 'html.parser')

    #  Clean the html before sending to LLM
    # for tag in soup(["script", "style", "header", "footer"]):
    #     tag.decompose()

    #Identify and Extract ToC for the index
    toc_html = await extract_toc(soup)
    index_html_as_string = [str(toc) for toc in toc_html]
    index_as_markdown = md("\n".join(index_html_as_string))
    #Make LLM call using the above html to get a lookup table of headings-> hierarchical heading - make this configurable to support any model with/without proxy
    llm_response = await get_llm_response(index_as_markdown, instruction_msg)
    index_lookup_table, heading_ids = await fetch_lookup_from_llm_response(llm_response, toc_html)
    print(index_lookup_table)
    #Enrich the page html using the lookup table from the LLM response and breakdown the document into chunks
    extracted_chunks = extract_chunks_using_heading_id(soup,index_lookup_table,heading_ids)
    markdown_chunks = convert_chunks_to_markdown(extracted_chunks)
    # Split the html into chunk if failed to extract using the above approach
    # chunks = split_into_chunks(html_as_markdown, heading_start, heading_end)
    sa_structured_data = await convert_to_SA_format(markdown_chunks, **kwargs)
    return sa_structured_data

async def save_json(output_file_path, json_output):
    async with aiofiles.open(output_file_path, 'w') as json_file:
        await json_file.write(json.dumps(json_output, indent=4))

async def helper(input_directory_path, output_directory_path):
    os.makedirs(output_directory_path, exist_ok=True)
    input_html_directory_path = os.path.join(input_directory_path, "html")
    # Create a list of tasks for processing and saving files
    tasks = []
    # Loop through all files in the directory
    for filename in os.listdir(input_directory_path):
        file_path = os.path.join(input_directory_path, filename)
        if os.path.isfile(file_path) and file_path.endswith('.json'):
            html_input_file_path = os.path.join(input_html_directory_path, f"{os.path.splitext(filename)[0]}_html.html")
            if os.path.exists(html_input_file_path):
                print(f"The file '{html_input_file_path}' already exists.")

            else:
                # Open the file in write mode
                parsed_html = await parse_json(file_path)
                with open(html_input_file_path, 'w') as file:
                    # Write the HTML string to the file
                    file.write(parsed_html)
                print(f"HTML content has been written to '{html_input_file_path}'.")

    for filename in os.listdir(input_html_directory_path):
        html_input_file_path = os.path.join(input_html_directory_path, filename)
        input_html = await parse_html(html_input_file_path)
        if input_html:
            kwargs = dict()
            kwargs['filename'] = filename.rstrip(".html")
            json_output = await extract_chunks(input_html,**kwargs)
            output_file_path = os.path.join(output_directory_path, f"{os.path.splitext(filename)[0]}_chunks.json")
            # Save the JSON output asynchronously
            await save_json(output_file_path, json_output)
            print(f'Finished processing for {filename}')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
if __name__ == "__main__":
    # Use argparse to handle command-line arguments
    parser = argparse.ArgumentParser(description="Process HTML files and output JSON files.")
    parser.add_argument("input_directory_path", nargs = '?', type=str, default= "./data/input/", help="Path to the input directory containing HTML files.")
    parser.add_argument("output_directory_path", nargs = '?', type=str, default= "./data/output/",help="Path to the output directory for JSON files.")

    args = parser.parse_args()

    # Run the main function with the parsed arguments
    asyncio.run(helper(args.input_directory_path, args.output_directory_path))