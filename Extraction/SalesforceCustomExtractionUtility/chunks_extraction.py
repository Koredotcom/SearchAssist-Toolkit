import asyncio
import argparse
import copy
import os
import json
import time
import re
import traceback
import ingest_data as data_ingestion
import aiofiles
import aiohttp
import html
import urllib.parse
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md
from openai import AsyncOpenAI
import dirtyjson
from bs4.element import NavigableString
from utils.logger import get_logger
import variables as config
logger = get_logger()
OPENAI_KEY = config.OPENAI_KEY
Azure_key= config.AZURE_OPENAI_KEY

llm_used=config.llm_used

open_ai_conf = {
    "API_BASE":config.openAI_apibase,
    "model": config.openAI_model,
    "API_KEY":OPENAI_KEY,
    "max_tokens":9000,
    "temperature":0.5,
    "top_p":1,
    "timeout":150,
    "max_retries":0
}
azure_open_ai_conf = {
    "API_BASE": config.API_BASE,
    "deployment_id": config.deployment,
    "api_version": config.Apiversion,
    "API_KEY": Azure_key,
    "model": config.Azure_model,
    "max_tokens": 7000,
    "temperature": 0.5,
    "top_p": 1,
    "timeout": 150,
    "max_retries": 0
}

prompt_json = [
    {
      "role": "system",
      "content": "{{instruction_msg}}\n--------------------------------------------------"
                  "----------------------------------------------------------------------\n\nContent:-{{content}}"
    }
]

azure_prompt=[
        {
            "role": "system",
            "content": "{{instruction_msg}}"
        },
        {
            "role": "user",
            "content": "{{content}}"
        }
]

instruction_msg = "Given an markdown for a possible table of content for a document, understand the text and identify table of contents with correct heading and subheadings.  Please note that there may be some extra info in the input text, which may not be needed for the index, use you knowledge to decide what to include in the index.\nFigure out add the parents of each subheading and return a lookup table map, which maps a heading to its hierarchical heading with all the parents appended as prefix.  \nCHILD HEADING SHOULD BE PRESENT IN THE VALUE ALWAYS.\nMap should be like:-\n{\n\"Child heading 1\": \"prefix1 prefix2 Child heading 1\",\n\"Child heading 2\": \" \"<prefix1 prefix2 Child heading 2\",\n...\n}"
openai_client = AsyncOpenAI(
            base_url= open_ai_conf.get("API_BASE", ""),
            api_key= open_ai_conf.get("API_KEY", ""),
            max_retries=open_ai_conf.get("MAX_RETRIES", 0),
        )
class AsyncAzureOpenAI:
    def __init__(self, base_url, deployment_id, api_version, api_key, max_retries):
        self.base_url = base_url
        self.deployment_id = deployment_id
        self.api_version = api_version
        self.api_key = api_key
        self.max_retries = max_retries

    async def fetch_azure_response(self, **request_payload):
        url = f"{self.base_url}/openai/deployments/{self.deployment_id}/chat/completions?api-version={self.api_version}"
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }

        async with aiohttp.ClientSession() as session:
            for _ in range(self.max_retries + 1):
                try:
                    async with session.post(url, headers=headers, json=request_payload, ssl=False) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            response.raise_for_status()
                except Exception as e:
                    print(f"An error occurred: {e}")
                    await asyncio.sleep(1)
        return None

azure_openai_client = AsyncAzureOpenAI(
    base_url=azure_open_ai_conf.get("API_BASE", ""),
    deployment_id=azure_open_ai_conf.get("deployment_id", ""),
    api_version=azure_open_ai_conf.get("api_version", ""),
    api_key=azure_open_ai_conf.get("API_KEY", ""),
    max_retries=azure_open_ai_conf.get("max_retries", 0)
)
common_index_tag = "a"


async def parse_html(file_path):
    # Opening the html file
    with open(file_path, "r") as html_file:
        try:
            with open(file_path, 'r', encoding='utf-8') as html_file:
                data = html_file.read()
        # Process the data as needed
        except UnicodeDecodeError as e:
            print(f"Error decoding file {file_path} with UTF-8 encoding: {e}")
        # Attempt to read the file with a different encoding
        try:
            with open(file_path, 'r', encoding='latin-1') as html_file:
                data = html_file.read()
                # Process the data as needed
        except UnicodeDecodeError as e:
            print(f"Error decoding file {file_path} with Latin-1 encoding: {e}")
    # Reading the file

    index = data
    return index

def replace_backslashes(input_string):
    pattern = r'\\\\{2,}'
    # Define the replacement string
    replacement = r'\\\\'
    return re.sub(pattern, replacement, input_string)
def clean_json(json_str):
    data = dict(dirtyjson.loads(json_str))
    json_string = data.get("raw_data", "")
   # json_string = json_string.replace("\n","").replace("\t","")
   # json_string = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'', json_string)
   # json_string = replace_backslashes(json_string)
   # data['raw_data'] = json.loads(json_string)
    data['raw_data'] = json_string
    return data

async def parse_json(file_path):
    # Opening the html file
    with open(file_path, 'r') as file:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = file.read()
                # Process the data as needed
        except UnicodeDecodeError as e:
            print(f"Error decoding file {file_path} with UTF-8 encoding: {e}")
        # Attempt to read the file with a different encoding
        try:
            with open(file_path, 'r', encoding='latin-1') as file:
                data = file.read()
                # Process the data as needed
        except UnicodeDecodeError as e:
            print(f"Error decoding file {file_path} with Latin-1 encoding: {e}")


        # data = file.read()
        cleaned_json = clean_json(data)
        raw_data = cleaned_json.get("raw_data", {})
        layout_items = raw_data.get("layoutItems",[])
        lastPublisheddate= raw_data.get("lastPublishedDate","")
        knowledge_article_urls=raw_data.get("url")
        html_string = ""
        for item in layout_items:
            if item.get("type","") in ["RICH_TEXT_AREA","TEXT"] :
                if item.get("value", ""):
                    html_string += item.get("value")
                    unescaped_string = html.unescape(html_string)
    return unescaped_string,lastPublisheddate,knowledge_article_urls


def check_tag(tag, heading_ids):
    if tag.name == "a" and heading_ids.get("#" + str(tag.get("id", tag.get("name", "")))):
        return True

    for child in tag.children:
        if hasattr(child, 'children'):  # Ensure the child is a tag and not a string or comment
            if(check_tag(child, heading_ids)):
                return True
    return False
def collect_intermediate_tags(soup, start_tag, heading_ids, tag_to_collect = None):
    current_tag = start_tag
    intermediate_tags = BeautifulSoup("", "html.parser")
    next_tag = current_tag.next_element
    while(tag_to_collect is None and next_tag):
        if isinstance(next_tag, NavigableString):
            tag_to_append = copy.deepcopy(next_tag)
            intermediate_tags.append(tag_to_append)
            intermediate_tags.append(" ")
        else:
            break
        next_tag = next_tag.next_element
    current_tag = current_tag.find_next()

    # Navigate through the document from start_tag to end_tag
    while current_tag:
        if check_tag(current_tag, heading_ids):
            break
        if current_tag.parent and current_tag.parent.get("added_as_content"):
            pass
        else:
            if tag_to_collect is None or current_tag.name == tag_to_collect:
                tag_to_append = copy.deepcopy(current_tag)
                intermediate_tags.append(tag_to_append)
            next_sibling = copy.deepcopy(current_tag.next_sibling)
            while(next_sibling):
                if tag_to_collect is None and isinstance(next_sibling, NavigableString):
                    tag_to_append = copy.deepcopy(next_sibling)
                    intermediate_tags.append(tag_to_append)
                next_sibling = next_sibling.next_sibling
        #Check for text tags
        current_tag['added_as_content'] = True
        current_tag = current_tag.find_next()
    return intermediate_tags

def clean_sub_index(sub_index):
    filtered_ul = BeautifulSoup('<ul></ul>', 'html.parser').ul

    if not (sub_index.next and sub_index.next.name == "ul" ):
        return filtered_ul
    else:
        sub_index = sub_index.next
    # Create a new <ul> tag for the filtered <li> tags

    # Iterate through each child <li> tag of the given <ul>
    for li in sub_index.find_all('li', recursive=False):
        # Get all children of the <li> tag
        children = list(li.children)

        # Check if the <li> tag's first child is an <a> tag
        if len(children) >= 1 and isinstance(children[0], Tag) and children[0].name == 'a':
            # Append the <li> tag to the filtered <ul>
            filtered_ul.append(li)

    return filtered_ul


def expand_toc(ul_tag, soup_obj, heading_ids = None, all_a_tags = None):
    if ul_tag.name!="ul":
        return []
    if not heading_ids:
        heading_ids = dict()
    if not all_a_tags:
        all_a_tags = soup_obj.find_all("a")
    a_tags = ul_tag.find_all('a')
    for a in a_tags:
        if 'href' in a.attrs:
            heading_ids[a['href']] = True

    for li in ul_tag.find_all('li', recursive=False):
        for child in li.children:
            sub_index = list()
            if child.name == 'a' and 'href' in child.attrs:
                # Filter the tags to match the desired conditions
                href = child['href'].lstrip("#")
                start_tag = next(
                    (tag for tag in all_a_tags if tag.get('id') == href or tag.get('name') == href), None)
                if start_tag:
                    all_a_tags.remove(start_tag)
                    sub_index = collect_intermediate_tags(soup_obj, start_tag, heading_ids, tag_to_collect="ul")
            elif child.name == 'ul':
                # Recursively call expand_toc for the nested <ul> tag
                sub_index = expand_toc(child, soup_obj, heading_ids,all_a_tags)
            if sub_index and sub_index!=child:
                sub_index = clean_sub_index(sub_index)
                if isinstance(sub_index, Tag) and sub_index.name == "ul" and len(list(sub_index.children))>=1:
                    child.insert_after(sub_index)
    return ul_tag

async def extract_toc(soup_obj, **kwargs):
    try:
        index_tags = ['ul']
        toc_html_queue = list()
        final_toc_html = list()
        for tag in index_tags:
            toc_html_queue.append(soup_obj.find(tag))
        for toc_html in toc_html_queue:
            final_toc_html.append(expand_toc(toc_html, soup_obj))
    except Exception as e:
        print("Error in extracting TOC for the file : {}".format(kwargs.get("filename","")))
        print(traceback.format_exc())
        final_toc_html = list()
    return final_toc_html

async def extract_toc_old (soup_obj):
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

class AzureOpenaiResponseHandler:
    def __init__(self, response):
        self.response = response

    def get_raw_format(self):
        return self.response
    def get_json_format(self):
        chat_id = self.response["id"]
        completion_usage_dict = self.response["usage"]
        json_str = json.dumps(completion_usage_dict)
        choices = []
        completion_usage_dict = self.response["usage"]
        json_str = json.dumps(completion_usage_dict)
        if self.response["choices"]:
            for choice in self.response["choices"]:
                choice_data = {
                    'message': {
                        'content': choice["message"]["content"],
                        'role': choice["message"]["role"],
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

async def get_openai_response(content, instruction_msg):
    try:
        if not content:
           raise Exception("Empty TOC encountered")
        curr_prompt = copy.deepcopy(prompt_json)
        content_template = curr_prompt[0].get("content", "")
        content_template = content_template.replace("{{instruction_msg}}", instruction_msg).replace("{{content}}", content)
        curr_prompt[0]["content"] = content_template
        model = open_ai_conf.get("model")
        timeout = open_ai_conf.get("timeout")
        max_tokens = open_ai_conf.get("max_tokens")
        temperature = open_ai_conf.get("temperature")
        top_p = open_ai_conf.get("top_p")
        request_payload = dict(
            model=model,
            messages=curr_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            timeout=timeout
        )
        start_time = time.time()
        completion = await openai_client.chat.completions.create(**request_payload)
        openai_response_handler = OpenaiResponseHandler(completion)
        completion_json_format = openai_response_handler.get_json_format()
        print("Time taken in one OpenAI call: {}".format(time.time() - start_time))
        print('**OpenAI Response** {}'.format(completion_json_format))
    except Exception as e:
        print("Error in fetching LLM response, falling back to empty llm response")
        print(traceback.format_exc())
        completion_json_format = {}
    return completion_json_format

async def get_azure_openai_response(content, instruction_msg):
    try:
        if not content:
           raise Exception("Empty TOC encountered")
        curr_prompt = copy.deepcopy(azure_prompt)
        # print(curr_prompt)
        content_template = curr_prompt[0].get("content", "")
        content_template1=curr_prompt[1].get("content","")
        # print("content_template",content_template)
        content_template = content_template.replace("{{instruction_msg}}", instruction_msg)
        content_template1=content_template1.replace("{{content}}", content)
        curr_prompt[0]["content"] = content_template
        curr_prompt[1]["content"] = content_template1
        # print(curr_prompt)
        model = azure_open_ai_conf.get("model")
        max_tokens = azure_open_ai_conf.get("max_tokens")
        temperature = azure_open_ai_conf.get("temperature")
        top_p = azure_open_ai_conf.get("top_p")
        request_payload = dict(
            messages=curr_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p
        )
        start_time = time.time()
        completion = await azure_openai_client.fetch_azure_response(**request_payload)
        azure_response_handler = AzureOpenaiResponseHandler(completion)
        completion_json_format = azure_response_handler.get_json_format()
        print("Time taken in one Azure OpenAI call: {}".format(time.time() - start_time))
        print('**Azure OpenAI Response** {}'.format(completion_json_format))
    except Exception as e:
        print("Error in fetching LLM response, falling back to empty llm response")
        print(traceback.format_exc())
        completion_json_format = {}

    return completion_json_format


async def get_llm_response(content, instruction_msg):
    try:
        if not content:
           raise Exception("Empty TOC encountered")
        if llm_used=="openai":
            llm_response= await get_openai_response(content, instruction_msg)

        elif llm_used=="azure":
            llm_response= await get_azure_openai_response(content, instruction_msg)
    except Exception as e:
        print("Error in fetching LLM response, falling back to empty llm response")
    return llm_response



async def fetch_lookup_from_llm_response(llm_response,toc_html, **kwargs):
    try :
        lookup_with_id = dict()
        heading_ids = dict()
        lookup_string = llm_response.get("choices",[])[0].get("message",{}).get("content","")
        lookup_json = json.loads(lookup_string)
        #list of tocs, usually single
        for key, value in lookup_json.items():
            if lookup_with_id.get(key) is None:
                for toc in toc_html:
                    anchor_tag = toc.find(common_index_tag, string=key)
                    if anchor_tag:
                        heading_id =anchor_tag['href']
                        lookup_with_id[key] = dict(value = lookup_json[key], heading_id = heading_id)
                        heading_ids[heading_id] = True
    except Exception as e:
        lookup_with_id = dict()
        heading_ids = dict()
        print("Error in Creating Lookup from LLM response for {}, sending empty lookup".format(kwargs.get("filename")))
        print(traceback.format_exc())
    return lookup_with_id, heading_ids



def extract_chunks_using_heading_id(soup, lookup_table,  heading_ids, **kwargs):
    try:
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
                        content_html = collect_intermediate_tags(soup, anchor_tag, heading_ids)
                        content_html_string = str(content_html)
                        chunks.append(dict(heading = new_value, content = content_html_string))

    except Exception as e:
        print("Error in Extracting Chunks based on the given lookup table {} for {}".format(lookup_table, kwargs.get("filename","")))
        print(traceback.format_exc())
        chunks = list()
    if len(chunks)==0:
        print("No chunks extracted, sending whole html as a chunk")
        content_html_string = str(soup)
        chunks.append(dict(heading="", content=content_html_string))
    # print(chunks)
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

async def convert_to_SA_format(chunks,lastupdatedDate,unique_ArticleIDs_url, **kwargs):
    data_list = list()
    for chunk in chunks:
        title = chunk.get("heading")
        markdown= chunk.get("content_markdown")

        if markdown is None:
            markdown="null"
        data = {
            "title" : chunk.get("heading") or kwargs.get("filename", ""),
            "content": chunk.get("content"),
            "html": urllib.parse.quote(chunk.get("content")),
            "content_markdown" : markdown,
            # "url": kwargs.get("url",""),
            "url": unique_ArticleIDs_url,
            "meta_data":kwargs.get("meta_data",{}),
            "doc_name" : kwargs.get("filename",""),
            "lastModifiedDate": lastupdatedDate
        }
        data_list.append(data)
    return data_list
def convert_chunks_to_markdown(chunks):
    for chunk in chunks:
        if chunk.get("content",""):
            chunk['content_markdown'] = md(chunk.get('content'))
    return chunks
async def extract_chunks(input_html,lastupdatedDate,unique_ArticleIDs_url,**kwargs):
    try:
        soup =  BeautifulSoup(input_html, 'html.parser')
        soup_for_toc = copy.deepcopy(soup)
        toc_html = await extract_toc(soup_for_toc, **kwargs)
        index_html_as_string = [str(toc) for toc in toc_html]
        index_as_markdown = md("\n".join(index_html_as_string))
        #Make LLM call using the above html to get a lookup table of headings-> hierarchical heading - make this configurable to support any model with/without proxy
        llm_response = await get_llm_response(index_as_markdown, instruction_msg)
        index_lookup_table, heading_ids = await fetch_lookup_from_llm_response(llm_response, toc_html, **kwargs)
        #Enrich the page html using the lookup table from the LLM response and breakdown the document into chunks
        extracted_chunks = extract_chunks_using_heading_id(soup,index_lookup_table, heading_ids, **kwargs)
        markdown_chunks = convert_chunks_to_markdown(extracted_chunks)
        # Split the html into chunk if failed to extract using the above approach
        # chunks = split_into_chunks(html_as_markdown, heading_start, heading_end)
        sa_structured_data = await convert_to_SA_format(markdown_chunks,lastupdatedDate,unique_ArticleIDs_url,**kwargs)
    except Exception as e:
        print("Error in extracting Chunks for the given file : {}. Sending empty data".format(kwargs.get("filename")))
        print(traceback.format_exc())
        sa_structured_data = list()
    return sa_structured_data

async def save_json(output_file_path, store_chunks):
    async with aiofiles.open(output_file_path, 'w') as json_file:
        await json_file.write(json.dumps(store_chunks, indent=2))
        print("data ingestion started")
        ingest=data_ingestion.ingest_new_data(store_chunks)
        print(ingest)

async def helper(input_directory_path, output_directory_path):
    structure_Data_Count=0
    updatedDates={}
    articleID_urls={}
    # html_directory_path="./html"
    os.makedirs(output_directory_path, exist_ok=True)
    input_html_directory_path = os.path.join(input_directory_path, "html")
    os.makedirs(input_html_directory_path, exist_ok=True)
    # Create a list of tasks for processing and saving files
    tasks = []
    store_chunks=[]
    # Loop through all files in the directory
    for filename in os.listdir(input_directory_path):
        file_path = os.path.join(input_directory_path, filename)
        if os.path.isfile(file_path) and file_path.endswith('.json'):
            # input_html_directory_path="./input"
            html_input_file_path = os.path.join(input_html_directory_path, f"{os.path.splitext(filename)[0]}_html.html")
            if os.path.exists(html_input_file_path):
                print(f"The file '{html_input_file_path}' already exists.")

            else:
                # Open the file in write mode

                parsed_html,updatedDate,knowledge_article_urls = await parse_json(file_path)
                # print(parsed_html)
                with open(html_input_file_path, 'w') as file:
                    # Write the HTML string to the file
                        try:
                            with open(html_input_file_path, 'w', encoding='utf-8') as output_file:
                                output_file.write(parsed_html)
                                updatedDates.update({html_input_file_path:updatedDate})
                                articleID_urls.update({html_input_file_path:knowledge_article_urls})
                                print(f"Parsed HTML saved to {html_input_file_path}")
                        except UnicodeEncodeError as e:
                            print(f"Error encoding parsed HTML to UTF-8: {e}")
                    # file.write(parsed_html)
                print(f"HTML content has been written to '{html_input_file_path}'.")
    for filename in os.listdir(input_html_directory_path):
        html_input_file_path = os.path.join(input_html_directory_path, filename)
        input_html = await parse_html(html_input_file_path)
        if input_html:
            kwargs = dict()
            kwargs['filename'] = filename.removesuffix('.html')
            print(f'Staring Extraction for {filename}')
            if html_input_file_path in updatedDates:
                lastupdatedDate= updatedDates[html_input_file_path]
            if html_input_file_path in articleID_urls:
                unique_ArticleIDs_url= articleID_urls[html_input_file_path]
            json_output = await extract_chunks(input_html,lastupdatedDate,unique_ArticleIDs_url,**kwargs)
            html_path = os.path.join(input_html_directory_path, f"{os.path.splitext(filename)[0]}_chunks.json")
            with open(html_path, 'w') as file:
                json.dump(json_output, file, indent=4)
            structure_Data_Count+=len(json_output)
            # print(json_output)
            store_chunks.extend(json_output)
            # print(store_chunks)

    if store_chunks:
        # output_directory_path = ".data/output"
        filename = "output_file.json"
        output_file_path = os.path.join(output_directory_path, filename)
        return await save_json(output_file_path, store_chunks)