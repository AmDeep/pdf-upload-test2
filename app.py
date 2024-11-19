import os
import sys
import traceback
from io import BytesIO
import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError
from streamlit import session_state
from collections import Counter  # <-- Add this import for the Counter class
from utils import helpers, init_session_states, page_config
from dotenv import load_dotenv
import openai

# Load environment variables from the .env file
load_dotenv()

# Get the OpenAI API key from the environment variable
openai.api_key = os.getenv(
    "OPENAI_API_KEY"
)  # Ensure your OpenAI API key is set (you can replace this with your actual key)

# Set up the page config
page_config.set()

# Initialize session states
init_session_states.init()

# ---------- HEADER ----------
st.title("📄 PDF WorkDesk with Text Extraction & Contextual Analysis")
st.write(
    "This tool enables text extraction, content analysis, metadata operations, and much more from PDFs. It allows you to analyze and manipulate your PDF documents."
)

# ---------- UPLOAD PDF ----------
st.subheader("Upload Your PDF File")
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# ---------- FIXED parse_page_numbers function -----------
@st.cache_data
def parse_page_numbers(page_numbers_str):
    parts = page_numbers_str.split(",")
    parsed_page_numbers = []
    for part in parts:
        part = part.strip()
        if "-" in part:
            start, end = map(int, part.split("-"))
            parsed_page_numbers.extend(range(start, end + 1))
        else:
            parsed_page_numbers.append(int(part))
    return [i - 1 for i in parsed_page_numbers]

# Function to extract text from PDF
def extract_text(reader: PdfReader.pages, page_numbers_str: str = "all", mode: str = "plain") -> str:
    text = ""
    if page_numbers_str == "all":
        for page in reader.pages:
            text = text + " " + page.extract_text(extraction_mode=mode)
    else:
        pages = parse_page_numbers(page_numbers_str)
        for page in pages:
            text = text + " " + reader.pages[page].extract_text()
    return text

# Function to convert PDF to Markdown
def pdf_to_markdown(pdf_document):
    markdown_text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        markdown_text += page.get_text("markdown")
    return markdown_text

# Function to query OpenAI for relevant data extraction
def query_openai(text, term):
    # Define the prompt template for OpenAI to extract information about each term
    prompt = f"""
    Pull the following in a table with the following columns:
    Term | Response | Page number
    
    Here are the 20 things we need with the response options in parentheses:
    Plan name (free text)
    Trustee (free text)
    EIN (integers)
    Year End  (date)
    Entity Type (C corp, S corp, non profit, partnership, LLC taxed as a s corp, LLC taxed as a c corp, LLC taxed as sole proprietor, Limited Liability Partnership, Sole Proprietorship, union, government agency, other)   
    Entity State (free text)
    Is it a safe harbor (No, Yes - safe harbor match, Yes - nonelective contribution, Yes - QACA safe harbor match, Yes - enhanced safe harbor match, Yes - QACA nonelective contribution)
    Vesting(100% Vested, 2 - 6 Year Graded, 1 - 5 Year Graded, 2 Year 50/50, 1 - 4 Year Graded, 3 Year Cliff, 2 Year Cliff, 1 Year Cliff)
    Profit sharing vesting (100% Vested, 2 - 6 Year Graded, 1 - 5 Year Graded, 2 Year 50/50, 1 - 4 Year Graded, 3 Year Cliff, 2 Year Cliff, 1 Year Cliff)
    Plan Type (free text)

    {text}
    """
    
    try:
        # Query OpenAI API to extract relevant data based on the term
        response = openai.Completion.create(
            model="gpt-4",  # Use a GPT model (adjust for GPT-4 or other models if necessary)
            prompt=prompt,
            max_tokens=1500,  # Set max tokens for the response
            temperature=0.5,  # Control randomness
            n=1,
            stop=None
        )
        # Return the extracted response from OpenAI
        return response.choices[0].text.strip()
    except Exception as e:
        # Handle errors in case of issues with the OpenAI API
        print(f"Error querying OpenAI: {e}")
        return None

# Function to extract relevant information from the PDF based on terms
def extract_relevant_information(pdf_reader, terms):
    info_data = {term: None for term in terms}  # Initialize dictionary to store term info

    # Iterate over each page of the PDF and extract the relevant data
    for page_num, page in enumerate(pdf_reader.pages):
        text = page.extract_text()  # Extract text from the current page
        if text:
            # Loop over each term and extract information using OpenAI
            for term in terms:
                if info_data[term] is None:  # Only process if the term hasn't been found yet
                    extracted_info = query_openai(text, term)  # Get information from OpenAI
                    if extracted_info:  # If OpenAI returned something
                        info_data[term] = [term, extracted_info, page_num + 1]  # Save term, data, and page number

    # Return the data in a structured format: [[term, extracted_info, page_number], ...]
    return [
        [term, info_data[term][1] if info_data[term] else "", info_data[term][2] if info_data[term] else ""]
        for term in terms
    ]

# ---------- MAIN SECTION ----------
try:
    if uploaded_file is not None:
        # Read the uploaded PDF
        try:
            pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            pdf_reader = PdfReader(uploaded_file)
            session_state["password"], session_state["is_encrypted"] = "", False
        except FileNotDecryptedError:
            pdf_document = "password_required"
            st.error("PDF is password protected. Please enter the password to proceed.")

        # ---------- PDF OPERATIONS ----------
        if pdf_document != "password_required" and pdf_document:

            # Extract text from PDF
            extracted_text = ""
            for page_num in range(pdf_document.page_count):
                page = pdf_document.load_page(page_num)
                extracted_text += page.get_text("text")  # Basic text extraction

            # Clean the extracted text
            def clean_text(text):
                text = text.lower()
                text = re.sub(r'[^\w\s]', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text

            cleaned_text = clean_text(extracted_text)

            # Define the terms to extract
            terms_to_extract = [
                "Plan name", "Trustee", "EIN", "Year End", "Entity Type", "Entity State",
                "Is it a safe harbor", "Vesting", "Profit sharing vesting", "Plan Type"
            ]

            # Extract information matching specific terms using OpenAI
            extracted_info = extract_relevant_information(pdf_reader, terms_to_extract)

            # Display the extracted information in a table
            with st.container():
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader("Extracted Information")
                    info_df = pd.DataFrame(extracted_info, columns=["Term", "Response", "Page Number"])
                    st.dataframe(info_df)
                with col2:
                    st.subheader("Document Preview")
                    preview_area = st.empty()
                    preview_area.markdown('<div style="height:400px; overflow-y:scroll; width:300px;">', unsafe_allow_html=True)
                    for page_num in range(pdf_document.page_count):
                        page = pdf_document.load_page(page_num)
                        pix = page.get_pixmap()
                        img_data = pix.tobytes("png")
                        preview_area.image(img_data, caption=f"Page {page_num + 1}", use_column_width=True)
                    preview_area.markdown("</div>", unsafe_allow_html=True)

        else:
            st.error("Unable to process the PDF. It may be password protected.")

except Exception as e:
    st.error(f"An error occurred: {e}")
    st.write(traceback.format_exc())
