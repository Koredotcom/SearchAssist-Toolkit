import sys

import os
import fitz
import pandas as pd
from textwrap import wrap
import os
from langchain.docstore.document import Document
# from GenerativeAIExamples.RetrievalAugmentedGeneration.examples.multimodal_rag.llm.llm_client import LLMClient
# from llm_client import LLMClient
from PIL import Image
from io import BytesIO
import base64
# from GenerativeAIExamples.RetrievalAugmentedGeneration.common.utils import get_config
# from GenerativeAIExamples.RetrievalAugmentedGeneration.common.tracing import langchain_instrumentation_method_wrapper


def get_b64_image(image_path):
    image = Image.open(image_path).convert("RGB")
    buffered = BytesIO()
    image.save(buffered, format="JPEG", quality=20)  # quality=20 is a workaround (WAR)
    b64_string = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return b64_string

# @langchain_instrumentation_method_wrapper
# def is_graph(cb_handler, image_path):
#     # Placeholder function for graph detection logic
#     # Implement graph detection algorithm here
#     neva = LLMClient("ai-neva-22b", cb_handler=cb_handler)
#     b64_string = get_b64_image(image_path)
#     res = neva.multimodal_invoke(b64_string, creativity = 0, quality = 9, complexity = 0, verbosity = 9).content
#     if "graph" in res or "plot" in res or "chart" in res:
#         return True
#     else:
#         return False

# @langchain_instrumentation_method_wrapper
# def process_graph(cb_handler, image_path):
#     # Placeholder function for graph processing logic
#     # Implement graph processing algorithm here
#     # Call DePlot through the API
#     deplot = LLMClient("ai-google-deplot")
#     b64_string = get_b64_image(image_path)
#     res = deplot.multimodal_invoke(b64_string)
#     deplot_description = res.content
#     # Accessing the model name environment variable
#     # settings = get_config()
#     mixtral = LLMClient(model_name="mixtral_8x7b", is_response_generator=True, cb_handler=cb_handler)
#     response = mixtral.chat_with_prompt(system_prompt="Your responsibility is to explain charts. You are an expert in describing the responses of linearized tables into plain English text for LLMs to use.",
#                              prompt="Explain the following linearized table. " + deplot_description)
#     full_response = ""
#     for chunk in response:
#         full_response += chunk
#     return full_response

def extract_text_around_item(text_blocks, bbox, page_height, threshold_percentage=0.1):
    before_text, after_text = "", ""
    vertical_threshold_distance = page_height * threshold_percentage
    horizontal_threshold_distance = bbox.width * threshold_percentage  # Assuming similar threshold for horizontal distance

    for block in text_blocks:
        block_bbox = fitz.Rect(block[:4])
        vertical_distance = min(abs(block_bbox.y1 - bbox.y0), abs(block_bbox.y0 - bbox.y1))
        horizontal_overlap = max(0, min(block_bbox.x1, bbox.x1) - max(block_bbox.x0, bbox.x0))

        # Check if within vertical threshold distance and has horizontal overlap or closeness
        if vertical_distance <= vertical_threshold_distance and horizontal_overlap >= -horizontal_threshold_distance:
            if block_bbox.y1 < bbox.y0 and not before_text:
                before_text = block[4]
            elif block_bbox.y0 > bbox.y1 and not after_text:
                after_text = block[4]
                break

    return before_text, after_text

def process_text_blocks(text_blocks):
    char_count_threshold = 500  # Threshold for the number of characters in a group
    current_group = []
    grouped_blocks = []
    current_char_count = 0

    for block in text_blocks:
        if block[-1] == 0:  # Check if the block is of text type
            block_text = block[4]
            block_char_count = len(block_text)

            if current_char_count + block_char_count <= char_count_threshold:
                current_group.append(block)
                current_char_count += block_char_count
            else:
                if current_group:
                    grouped_content = "\n".join([b[4] for b in current_group])
                    grouped_blocks.append((current_group[0], grouped_content))
                current_group = [block]
                current_char_count = block_char_count

    # Append the last group
    if current_group:
        grouped_content = "\n".join([b[4] for b in current_group])
        grouped_blocks.append((current_group[0], grouped_content))

    return grouped_blocks


def df_to_table_string(df, max_col_width=50):
    def wrap_text(text, width):
        return wrap(str(text), width)
    
    # Wrap text in each cell based on the specified column width
    wrapped_df = df.map(lambda x: wrap_text(x, max_col_width))
    
    # Calculate the maximum number of lines in any cell for each row
    max_lines_per_row = wrapped_df.map(len).max(axis=1)
    
    # Create a list to hold the formatted rows
    formatted_rows = []
    
    # Format the header
    header_parts = [wrap_text(col, max_col_width) for col in df.columns]
    max_header_lines = max(len(part) for part in header_parts)
    
    for line_num in range(max_header_lines):
        line_parts = []
        for part in header_parts:
            if line_num < len(part):
                line_parts.append(f"{part[line_num]:<{max_col_width}}")
            else:
                line_parts.append(" " * max_col_width)
        formatted_rows.append(" | ".join(line_parts))
    formatted_rows.append("\n\n")
    for i, row in wrapped_df.iterrows():
        row_lines = [""] * max_lines_per_row[i]
        for col, cell in row.items():
            for line_num, line in enumerate(cell):
                row_lines[line_num] += f"{line:<{max_col_width}} | "
            for line_num in range(len(cell), max_lines_per_row[i]):
                row_lines[line_num] += " " * max_col_width + " | "
        formatted_rows.extend(row_lines)
    
    # Join all the formatted rows into a single string
    table_string = "\n".join(formatted_rows)
    
    return table_string


def parse_all_tables(filename, page, pagenum, text_blocks, ongoing_tables):
    table_docs = []
    table_bboxes = []
    ctr = 1
    try:
        tables = page.find_tables(horizontal_strategy = "lines_strict", vertical_strategy = "lines_strict")
    except Exception as e:
        print(f"Error during table extraction: {e}")
        
        return table_docs, table_bboxes, ongoing_tables
    if tables:
        for tab in tables:
            if tab.header.external:
                # Check if this table is a continuation of a table from a previous page
                previous_table = ongoing_tables.get(pagenum - 1, None)
                if previous_table:
                    # Merge the current table with the previous part
                    combined_df = pd.concat([previous_table['dataframe'], tab.to_pandas()])
                    ongoing_tables[pagenum] = {"dataframe": combined_df, "bbox": bbox}
                continue
            if not tab.header.external:
                pandas_df = tab.to_pandas()
                tablerefdir = os.path.join(os.getcwd(), "vectorstore/table_references")
                if not os.path.exists(tablerefdir):
                    os.makedirs(tablerefdir)
                df_xlsx_path = os.path.join(tablerefdir, f"table{ctr}-page{pagenum}.xlsx")
                pandas_df.to_excel(df_xlsx_path)
                bbox = fitz.Rect(tab.bbox)
                table_bboxes.append(bbox)

                # Find text around the table
                before_text, after_text = extract_text_around_item(text_blocks, bbox, page.rect.height)

                table_img = page.get_pixmap(clip=bbox)
                table_img_path = os.path.join(tablerefdir, f"table{ctr}-page{pagenum}.jpg")
                
                # table_img.save(table_img_path)
                # img = Image.open(table_img_path)
                # img.show()
                # Convert the Pixmap to a PIL Image
                pil_image = Image.frombytes("RGB", [table_img.width, table_img.height], table_img.samples)

                # Save the image with higher DPI for better quality
                dpi_factor = 100  # Adjust this factor as needed to improve quality
                pil_image.save(table_img_path, dpi=(300 * dpi_factor, 300 * dpi_factor))
                # Open and display the image
                # img = Image.open(table_img_path)
                # img.show()
                # description = process_graph(table_img_path)
                # ctr += 1

                # caption = before_text.replace("\n", " ") + description + after_text.replace("\n", " ")
                # if before_text == "" and after_text == "":
                #     caption = " ".join(tab.header.names)


                table_metadata = {
                    "source": f"{filename[:-4]}-page{pagenum}-table{ctr}",
                    "dataframe": df_xlsx_path,
                    "image": table_img_path,
                    # "caption": caption,
                    "type": "table",
                    "page_num": pagenum
                }
                # all_cols = ", ".join(list(pandas_df.columns.values))
                df_str = df_to_table_string(pandas_df)
                # print(f"Pandas df \n\n {pandas_df}","\n\n",df_str)
                doc = Document(f"\nTable content:\n\n {df_str} ", metadata=table_metadata)
                table_docs.append(doc)
                
                # print(table_docs)
    return table_docs, table_bboxes, ongoing_tables

def parse_all_images(filename, page, pagenum, text_blocks):
    image_docs = []
    image_info_list = page.get_image_info(xrefs=True)
    page_rect = page.rect  # Get the dimensions of the page

    for image_info in image_info_list:
        xref = image_info['xref']
        if xref == 0:
            continue  # Skip inline images or undetectable images

        img_bbox = fitz.Rect(image_info['bbox'])
        # Check if the image size is at least 5% of the page size in any dimension
        if img_bbox.width < page_rect.width / 20 or img_bbox.height < page_rect.height / 20:
            continue  # Skip very small images

        # Extract and save the image
        extracted_image = page.parent.extract_image(xref)
        image_data = extracted_image["image"]
        imgrefpath = os.path.join(os.getcwd(), "vectorstore/image_references")
        if not os.path.exists(imgrefpath):
            os.makedirs(imgrefpath)
        image_path = os.path.join(imgrefpath, f"image{xref}-page{pagenum}.png")
        with open(image_path, "wb") as img_file:
            img_file.write(image_data)

        # Find text around the image
        before_text, after_text = extract_text_around_item(text_blocks, img_bbox, page.rect.height)
        # skip images without a caption, they are likely just some logo or graphics
        if before_text == "" and after_text == "":
            continue

        # Process the image if it's a graph
        # image_description = " "
        # if is_graph(image_path):
        #     image_description = process_graph(image_path)

        # # Combine the texts to form a caption
        # caption = before_text.replace("\n", " ") + image_description + after_text.replace("\n", " ")

        image_metadata = {
            "source": f"{filename[:-4]}-page{pagenum}-image{xref}",
            "image": image_path,
            # "caption": caption,
            "type": "image",
            "page_num": pagenum
        }
        image_docs.append(Document(page_content="Image Description(Skipped)",metadata=image_metadata))
    return image_docs

def get_pdf_documents(filepath):
    all_pdf_documents = []
    ongoing_tables = {}
    try:
        f = fitz.open(filepath)
    except Exception as e:
        print(f"Error opening or processing the PDF file: {e}")
        return []

    for i in range(len(f)):
        page = f[i]
        page_docs = []

        # Process text blocks
        initial_text_blocks = page.get_text("blocks", sort=True)

        # Define thresholds for header and footer (10% of the page height)
        page_height = page.rect.height
        header_threshold = page_height * 0.1
        footer_threshold = page_height * 0.9

        # Filter out text blocks that are likely headers or footers
        text_blocks = [block for block in initial_text_blocks if block[-1] == 0 and not (block[1] < header_threshold or block[3] > footer_threshold)]

        # Group text blocks by character count
        grouped_text_blocks = process_text_blocks(text_blocks)

        # Extract tables and their bounding boxes
        table_docs, table_bboxes, ongoing_tables = parse_all_tables(filepath, page, i, text_blocks, ongoing_tables)
        page_docs.extend(table_docs)

        # Extract and process images
        image_docs = parse_all_images(filepath, page, i, text_blocks)
        page_docs.extend(image_docs)

        # Process grouped text blocks
        text_block_ctr = 0
        for heading_block, content in grouped_text_blocks:
            text_block_ctr +=1 
            heading_bbox = fitz.Rect(heading_block[:4])
            # Check if the heading or its content overlaps with table or image bounding boxes
            if not any(heading_bbox.intersects(table_bbox) for table_bbox in table_bboxes):
                bbox = {"x1": heading_block[0], "y1": heading_block[1], "x2": heading_block[2], "x3": heading_block[3]}
                text_doc = Document(page_content=f"{heading_block[4]}\n{content}", metadata={**bbox, "type": "text", "page_num": i, "source": f"{filepath[:-4]}-page{i}-block{text_block_ctr}"})
                page_docs.append(text_doc)

        all_pdf_documents.append(page_docs)

    f.close()
    return all_pdf_documents

from difflib import SequenceMatcher

def remove_duplicate_paragraphs(text):
    # Split the text into paragraphs
    paragraphs = text.split("\n\n")
    
    # Remove duplicates while preserving the order
    unique_paragraphs = []
    seen_paragraphs = set()
    for i in range(len(paragraphs) - 1):
        # Compare current paragraph with the next one
        similarity = SequenceMatcher(None, paragraphs[i], paragraphs[i+1]).ratio()
        
        # If similarity is less than 0.9 (adjust as needed), consider them as different
        if similarity < 0.9:
            if paragraphs[i] not in seen_paragraphs:
                unique_paragraphs.append(paragraphs[i])
                seen_paragraphs.add(paragraphs[i])
    
    # Add the last paragraph
    if paragraphs[-1] not in seen_paragraphs:
        unique_paragraphs.append(paragraphs[-1])
    
    # Join the unique paragraphs back into a single string
    result_text = "\n\n".join(unique_paragraphs)
    
    return result_text

def main(pdf_filepath,nv_api_key='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'):


    # Set the value of NVIDIA_API_KEY environment variable
    os.environ['NVIDIA_API_KEY'] = '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'
    # Call the function to extract documents from the PDF
    pdf_documents_dl = get_pdf_documents(pdf_filepath)
    # Initialize an empty string to store the concatenated documents
    result_string = ""

    # Iterate through the extracted documents
    for page_documents in pdf_documents_dl:
        for document in page_documents:
            # Concatenate the page content to the result string
            result_string += document.page_content + "\n\n"

    result = remove_duplicate_paragraphs(result_string)
    
    return result,os.path.basename(pdf_filepath)

# if __name__ == "__main__":
    # with open('output.txt', 'w') as file:
    #     file.write(main(r"E:\Projects\SA - R&D\chunking\data\Adoption Policy.pdf")[0])
    # print(main(r"E:\Projects\SA - R&D\chunking\data\Adoption Policy.pdf")[0])