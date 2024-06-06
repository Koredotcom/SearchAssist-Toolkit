import json
import logging
import os
import traceback
from urllib.parse import quote

import streamlit as st

from SnippetExtractionUtil import extract_file_snippets

# Constants
SOURCE_DIRECTORY = "./Utilities/SnippetExtraction"
CHUNK_SIZE = 300
CONTENT_PERCENT_THRESHOLD = 65
FUZZY_THRESHOLD = 90
HEADER_THRESHOLD = 70
FOOTER_THRESHOLD = 70
HEADER_MARGIN_NUM = 3
FOOTER_MARGIN_NUM = 5
# Custom HTML and CSS:-
EXTERNAL_SNIPPET_EXTRACTION_LOGGER = 'snippet_extraction'
debug_logger = logging.getLogger(EXTERNAL_SNIPPET_EXTRACTION_LOGGER)

# Define background color and text color
heading_background_color = "#cbcbcb"  # Example: Blue color
heading_text_color = "#ffffff"  # Example: White color
hide_st_style = """
           <style>
           #MainMenu {visibility: hidden;}
           footer {visibility: hidden;}
           header {visibility: hidden;}
           </style>
           """
# Custom CSS for the fixed header
custom_css = f"""
    <style>
        .fixed-header {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            background-color: {heading_background_color};
            padding: 1rem;
            text-align: left;
            color: {heading_text_color};
            height: 10%;
            z-index: 1001;  /* Ensure the header is above other elements */
        }}
        .content {{
            margin-top: 80px;  /* Adjust this margin based on the header height */
            padding: 1rem;
        }}
        .sidebar-content {{
        margin-top: 80px;
            z-index: 1000;  /* Ensure the sidebar is behind the header */
        }}
        .heading-class{{
            margin-top: -0.5%;
        }}
    </style>
"""
# Custom CSS for the Sidebar
css_body_container = f'''
<style>
    [data-testid="stSidebar"] {{
    top: 10%;
    background-color: rgb(240, 242, 246);
    z-index: 999991;
    min-width: 20%;
    max-width: 20%;
    transform: none;
    transition: transform 300ms ease 0s, min-width 300ms ease 0s, max-width 300ms ease 0s;
    }}
    [data-testid="baseButton-header"] {{
        display: none;
    }}

</style>
'''

# Hiding streamlit header/footer watermarks
st.markdown(hide_st_style, unsafe_allow_html=True)

# Display custom CSS
st.markdown(custom_css, unsafe_allow_html=True)
with open("./Utilities/SnippetExtraction/sa-logo.svg", "r") as f:
    svg_content = f.read()
# Encode SVG content for data URL
svg_content_encoded = quote(svg_content)

# Fixed header
st.markdown(
    f"""
    <div class="fixed-header">
        <img class = "heading-class" src="data:image/svg+xml,{svg_content_encoded}" alt="Logo" width="200" height="50">
    </div>
    """,
    unsafe_allow_html=True,
)

root_container = st.container()

root_container.header('Extract Snippets')
# settings_container.markdown('<div class="sidebar-content">', unsafe_allow_html=True)
uploaded_file = root_container.file_uploader('Upload your files',
                                             accept_multiple_files=False, type=['pdf'])
# sb.markdown('<div class="sidebar-content">',unsafe_allow_html=True)
settings_container = root_container.container()
st.markdown(css_body_container, unsafe_allow_html=True)
settings = st.sidebar.container()
# basic_settings, advanced_settings = settings_container.columns(2)
basic_settings = settings.container()
basic_settings.subheader("Basic Settings")
# basic_settings = settings_container.container()
# Create a button
url = basic_settings.text_input("Enter File URL:", placeholder="url", help="Document URL to be added to the snippets")
content_threshold = basic_settings.slider("Content Percentage", 0, 100, CONTENT_PERCENT_THRESHOLD,
                                          help="Minimum percentage of tags to be considered as content.")
split_snippets = basic_settings.radio("Split Snippets", [True, False], index=1,
                                      help="Choose whether to split snippet content on size post extraction")
chunk_size = basic_settings.slider("Size of chunk", 100, 2000, value=CHUNK_SIZE, step=100,
                                   help="Maximum number of words in a snippet post for splitting")
# chunk_size = basic_settings.selectbox("Size of chunk",list(), index=300)
advanced_settings = settings.container()
advanced_settings.subheader("Advanced Settings")
# advanced_settings = settings_container.container()

header_threshold = advanced_settings.slider("Header Frequency Threshold", 0, 100, value=HEADER_THRESHOLD, step=10,
                                            help="Minimum percentage of page numbers for a tentative header to be present in to be considered a header")
footer_threshold = advanced_settings.slider("Footer Frequency Threshold", 0, 100, value=FOOTER_THRESHOLD, step=10,
                                            help="Minimum percentage of page numbers for a tentative footer to be present in to be considered a footer")
header_margin_num = advanced_settings.slider("Tentative headers", 1, 10, value=HEADER_MARGIN_NUM,
                                             help="Top N tags in a page to be considered for as a tentative header")
footer_margin_num = advanced_settings.slider("Tentative footers", 1, 10, value=FOOTER_MARGIN_NUM,
                                             help="Bottom N tags in a page to be considered as tentative footer")
fuzzy_threshold = advanced_settings.slider("Fuzzy Match Threshold", 0, 100, value=FUZZY_THRESHOLD, step=10,
                                           help="String fuzzy match threshold used in header/footer detection")
advanced_settings.visible = False
settings_container.markdown("</div>", unsafe_allow_html=True)


def on_extract_button_click():
    extract_snippets(uploaded_file)


button_container = root_container.container()

extract_button_container, download_button_container = button_container.columns(2)
# Create a button
extract_button = extract_button_container.button("Extract Snippets", on_click=on_extract_button_click)


# Attach the function to the button click event

def extract_snippets(uploaded_file):
    try:
        if uploaded_file:
            root_container.write("Extracting Snippets !")
            debug_logger.info("Uploaded file name : {}".format(uploaded_file.name))
            file_path = os.path.join(SOURCE_DIRECTORY, str(uploaded_file.name))
            with open(file_path, "wb") as file:
                file.write(uploaded_file.getvalue())
            debug_logger.info("PDF file {} created".format(uploaded_file.name))
            kwargs = {
                "content_threshold": content_threshold,
                "header_threshold": header_threshold,
                "footer_threshold": footer_threshold,
                "header_margin_num": header_margin_num,
                "footer_margin_num": footer_margin_num,
                "fuzzy_threshold": fuzzy_threshold,
                "split_snippets": split_snippets,
                "chunk_size": chunk_size
            }
            debug_logger.info("Extracting Snippets for {}".format(uploaded_file.name))
            snippets = extract_file_snippets(file_path, url, uploaded_file.name, **kwargs)
            debug_logger.info("Snippet Extraction completed for {}".format(uploaded_file.name))

            # Update the list of processed files
            def download_json():
                # Convert the JSON object to a string
                json_str = json.dumps(snippets, indent=2)

                # Download the JSON string as a file named "data.json"
                download_button_container.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name="snippets.json",
                    key="download_button"
                )

            # Display the download button
            download_json()
            root_container.json(snippets)
        else:
            debug_logger.warning("No file uploaded")
            root_container.warning("Please upload a file first !!")
    except Exception as e:
        root_container.error("Error in Snippet Extraction")
        debug_logger.error("Error in Custom Snippet Extraction")
        debug_logger.error(traceback.format_exc())
# streamlit run ExtractionService.py --server.enableXsrfProtection=false --server.enableCORS=false --server.enableWebsocketCompression=false

# streamlit run ExtractionService.py --server.enableXsrfProtection=false --server.enableCORS=false --server.enableWebsocketCompression=false > streamlit_output.log 2>&1 &
