import logging
import os
import re
import traceback
from collections import Counter
from io import BytesIO

import unicodedata
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pdfminer.converter import TextConverter, XMLConverter, HTMLConverter
from pdfminer.layout import LAParams
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage

LOG_FILE = "./snippet_extraction.log"
EXTERNAL_SNIPPET_EXTRACTION_LOGGER = 'snippet_extraction'
debug_logger = logging.getLogger(EXTERNAL_SNIPPET_EXTRACTION_LOGGER)


def clean_text(text):
    # Merge hyphenated words
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
    # Fix newlines in the middle of sentences
    text = re.sub(r"(?<!\n\s)\n(?!\s\n)", " ", text.strip())
    # Remove multiple newlines
    text = re.sub(r"\n\s*\n", "\n\n", text)
    # text = re.sub(r'[^A-Za-z0-9-,.\']+', ' ', text)
    return text.strip()


def clean_header_footer(text):
    text = re.sub(r'[^A-Za-z\']+', ' ', text)
    return text.strip()


def get_font_size(style):
    # Split the style attribute into individual styles
    styles = style.split(';')

    # Find the style containing font-size
    font_style = [s for s in styles if 'font-size' in s]

    if font_style:
        # Extract the font size value
        font_size = font_style[0].split(':')[-1].strip()
        return int(font_size[:-2])  # Extract the font size and convert to an integer
    else:
        return 0  # If no font-size is found


def fuzzy_match(string1, string2, threshold):
    score = fuzz.ratio(string1, string2)
    return score >= threshold


def font_transit(font_size, new_font_size):
    if font_size >= 18 and abs(font_size - new_font_size <= 3):
        return True
    elif abs(font_size - new_font_size) < 2:
        return True
    return False


def count_font_sizes_across_pages(pages, content_threshold):
    font_size_counts_total = Counter()
    for page in pages:
        soup_obj = BeautifulSoup(page, features="lxml")
        all_span = soup_obj.find_all('span')
        font_sizes = [get_font_size(span.get('style')) for span in all_span if 'style' in span.attrs]
        font_size_counts_total.update(font_sizes)
    font_size_counts_total = sorted(font_size_counts_total.items())

    if font_size_counts_total[0][0] == 0:
        del font_size_counts_total[0]
    sum_of_appearance = sum(pair[1] for pair in font_size_counts_total)

    debug_logger.info("All font sizes {}".format(font_size_counts_total))

    flag = 0
    temp_sum = 0
    Head_fonts = []
    for font, apperance in font_size_counts_total:
        if flag:
            Head_fonts.append(font)
        else:
            temp_sum += apperance
            percent = (temp_sum / sum_of_appearance) * 100
            if (percent > content_threshold):
                flag = 1
    debug_logger.info("Heading Font Sizes: {}".format(Head_fonts))
    return Head_fonts


def is_marginal(text, marginals, fuzzy_threshold):
    result = False
    text = clean_header_footer(text)
    if text:
        for marginal in marginals:
            result = result or fuzzy_match(marginal, text, fuzzy_threshold)
            if result:
                return result
    return result


def detect_headers_footers(pages, **kwargs):
    header_margin_num = kwargs.get("header_margin_num")
    footer_margin_num = kwargs.get("footer_margin_num")
    header_threshold = kwargs.get("header_threshold")
    footer_threshold = kwargs.get("footer_threshold")
    header_counts = Counter()
    footer_counts = Counter()
    possible_headers = list()
    possible_footers = list()
    headers = list()
    footers = list()
    num_page = -1

    for page in pages:
        num_page += 1
        page_soup_obj = BeautifulSoup(page, features="lxml")
        divs = page_soup_obj.find_all('div')
        possible_headers_tags = divs[0:header_margin_num]
        possible_footers_tags = divs[(-footer_margin_num):]

        for ph_tag in possible_headers_tags:
            cleaned_text = clean_header_footer(ph_tag.text.replace('\n', ' ').replace('\t', ' ').strip())
            possible_headers.append(cleaned_text)
        for pf_tag in possible_footers_tags:
            cleaned_text = clean_header_footer(pf_tag.text.replace('\n', ' ').replace('\t', ' ').strip())
            possible_footers.append(cleaned_text)
    header_counts.update(possible_headers)
    footer_counts.update(possible_footers)
    if num_page <= 5:
        footer_threshold = 60.0
        header_threshold = 60.0
    for text, frequency in header_counts.items():
        if num_page > 0 and text and (frequency / num_page) * 100 >= header_threshold:
            headers.append(text)
    for text, frequency in footer_counts.items():
        if num_page > 0 and text and (frequency / num_page) * 100 >= footer_threshold:
            footers.append(text)
    debug_logger.info("Headers : {} Footers : {}".format(headers, footers))
    return headers, footers


def pdf_to_html_conversion(path, format="html", codec="utf-8", password="", maxpages=0, caching=True,
                           pagenos=None):
    if pagenos is None:
        pagenos = set()
    pdf_resource_manager = PDFResourceManager()
    input_output_helper = BytesIO()
    laparams = LAParams()
    if format == "text":
        convertor = TextConverter(pdf_resource_manager, input_output_helper, codec=codec, laparams=laparams)
    elif format == "html":
        convertor = HTMLConverter(pdf_resource_manager, input_output_helper, codec=codec, laparams=laparams)
    elif format == "xml":
        convertor = XMLConverter(pdf_resource_manager, input_output_helper, codec=codec, laparams=laparams)
    else:
        raise ValueError("provide format, either text, html or xml!")

    file_pointer = open(path, "rb")
    interpreter = PDFPageInterpreter(pdf_resource_manager, convertor)
    for page in PDFPage.get_pages(file_pointer, pagenos, maxpages=maxpages, password=password, caching=caching,
                                  check_extractable=True, ):
        interpreter.process_page(page)

    pdf_html_text = input_output_helper.getvalue().decode()
    file_pointer.close()
    convertor.close()
    input_output_helper.close()
    return pdf_html_text


def word_length(text):
    return len(text.split(" "))


def extract_file_snippets(local_file_path, url, file_name, **kwargs):
    doc_snippets = extract_snippets_pdfminer(url, local_file_path, file_name, **kwargs)
    chunk_size = kwargs.get("chunk_size")
    split_snippets = kwargs.get("split_snippets")
    text_splitter = RecursiveCharacterTextSplitter(
        # Set a really small chunk size, just to show.
        chunk_size=chunk_size,
        chunk_overlap=0 * int(.1 * chunk_size),
        separators=["000"],
        length_function=word_length,
        is_separator_regex=False,
    )
    data = list()
    for snippet in doc_snippets:
        full_chunk_text = snippet["Content"]
        if split_snippets:
            splits = text_splitter.split_text(full_chunk_text)
        else:
            splits = [full_chunk_text]
        for split in splits:
            split = split.replace("000", "\n")
            newObject = {
                "title": snippet["title"],
                "content": split,
                "url": snippet.get("url", ""),
                "doc_name": file_name
            }
            data.append(newObject)
    try:
        os.remove(local_file_path)
        debug_logger.info("File {} Deleted successfully!!".format(file_name))
    except OSError as err:
        debug_logger.error(traceback.format_exc())
    return data


def extract_snippets_pdfminer(file_access_url, local_file_path, sys_source_name, **kwargs):
    snippets = list()
    try:
        html_text = pdf_to_html_conversion(local_file_path)
        soup_obj = BeautifulSoup(html_text, 'html.parser')

        pages = soup_obj.find_all("div", string=re.compile("Page"))
        for page in pages:
            page.insert_before("/new_page/")
        soup_obj_str = str(soup_obj)
        pages = soup_obj_str.split("/new_page/")
        data_body, data_heading = '', ''
        font_size = -1
        page_number = 0
        overall_font_size_counts = count_font_sizes_across_pages(pages, kwargs.get("content_threshold"))
        run_stack = []
        headers, footers = detect_headers_footers(pages, **kwargs)
        for page in pages:
            soup_obj = BeautifulSoup(page, features="lxml")
            divs = soup_obj.find_all('div')
            snippet_page_number = page_number
            curr_div_num = 0
            total_divs = len(divs)
            for div in divs:
                curr_div_num += 1
                data = div.find_all('span')
                for record in data:
                    record_text = record.text.strip()
                    if curr_div_num < (1 + kwargs.get("header_margin_num")) and is_marginal(
                            record_text, headers, kwargs.get("fuzzy_threshold")):
                        continue
                    elif curr_div_num > total_divs - kwargs.get("footer_margin_num") and is_marginal(
                            record_text, footers, kwargs.get("fuzzy_threshold")):
                        continue
                    if record_text:
                        new_font_size = get_font_size(record.get('style'))
                        if ('Bold' in record.get('style') and not "italic" in record.get(
                                'style').lower() and font_transit(font_size, new_font_size)) or (
                                new_font_size in overall_font_size_counts):
                            '''Not considering italic headings since most of them can be found in between paragraphs, 
                            we can remove this condn on demand'''
                            if len(record_text.split(" ")) > 25:
                                data_body += record_text + ' '
                                continue
                            font_size = get_font_size(record.get('style'))
                            if data_body and run_stack and len(data_body.strip()) > 50:
                                if not bool(re.search(r'[a-zA-Z]+', record_text)):
                                    data_body += record_text + ' '
                                    continue
                                data_heading = clean_text(record_text)
                                data_body = clean_text(data_body)
                                if data_body:
                                    hierarchy_title = [pair[1] for pair in run_stack]
                                    current_title = run_stack[-1][1]
                                    snippets.append(
                                        {'title': hierarchy_title, 'Content': data_body, 'sub_type': 'paragraph',
                                         'url': file_access_url + '#page=' + str(snippet_page_number),
                                         'source': sys_source_name})
                                    run_stack = [(font, head) for font, head in run_stack if font > font_size]
                                    run_stack.append((font_size, data_heading))
                                    snippet_page_number = page_number
                                    data_body = ''
                                    data_heading = ''


                            elif bool(re.search(r'[a-zA-Z]+', record_text)):
                                '''A heading should have atleast one alphabet to be qualified'''
                                data_heading += record_text + ' '
                                combined_head = ""
                                if run_stack and run_stack[-1][0] < font_size and data_body:
                                    combined_head = run_stack[-1][1] + combined_head
                                    run_stack.pop()
                                if run_stack and run_stack[-1][0] <= font_size:
                                    combined_head = run_stack[-1][1] + " " + clean_text(record_text)
                                    run_stack.pop()
                                    run_stack.append((font_size, combined_head))
                                else:
                                    run_stack.append((font_size, clean_text(record_text)))
                            elif data_heading:
                                data_body += record_text + ' '
                        elif run_stack:
                            data_body += record_text + ' '
                if data_body != '' and data_body.endswith(". "):
                    data_body += "000"
            page_number += 1

        # handling the last snippet
        if data_body and run_stack:
            hierarchy_title = [pair[1] for pair in run_stack]
            snippets.append(
                {'title': hierarchy_title, 'Content': data_body, 'sub_type': 'paragraph',
                 'url': file_access_url + '#page=' + str(snippet_page_number),
                 'source': sys_source_name})
        return snippets
    except Exception as e:
        debug_logger.error(traceback.format_exc())
        return snippets
