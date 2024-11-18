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

# Function to extract and convert PDF to Markdown format
def convert_pdf_to_markdown(pdf_document):
    markdown_text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    line_text = " ".join([span["text"] for span in line["spans"]])
                    # Check for bold, underline, or italic formatting
                    is_bold = any(span["flags"] == 2 for span in line["spans"])
                    is_underline = any(span["flags"] == 4 for span in line["spans"])
                    is_italic = any(span["flags"] == 1 for span in line["spans"])
                    
                    # Add Markdown formatting if needed
                    if is_bold:
                        line_text = f"**{line_text}**"
                    if is_underline:
                        line_text = f"_{line_text}_"
                    if is_italic:
                        line_text = f"*{line_text}*"
                    
                    markdown_text += f"{line_text}\n"
    return markdown_text

# Function to match specific terms in the text
def match_terms_in_text(text):
    terms = [
        "NAME", "TRUSTEE", "EIN", "YEAR END", "ENTITY TYPE", "ENTITY STATE",
        "company", "plan name", "Ftwilliam Id", "Total aum", "Mscs account", "Safe Habor", "Vesting", "profit sharing vesting", 
        "plan type", "compensation definition", "deferral change frequency", "match frequency", "entry date", "match entry date", 
        "profit share entry date", "minimum age", "match minimum age", "profit share minimum age", "eligibility delay", 
        "match eligibility delay", "profit share eligibility delay", "eligibility delay rolling", "hours of service", 
        "plan effective date", "plan restatement date", "plan number"
    ]
    
    matches = []
    for term in terms:
        matches.extend(re.findall(f'({term}.*?)(?=\n|$)', text, re.IGNORECASE))
    
    return matches

# Function to extract information for required terms
def extract_information_from_markdown(markdown_text, page_number):
    matches = match_terms_in_text(markdown_text)
    info_data = []
    for match in matches:
        info_data.append([match, markdown_text, page_number])
    return info_data

# Function to extract tables and preview pages from PDF
def extract_tables_from_pdf(pdf_reader, page_numbers):
    page_numbers_str = ",".join(map(str, page_numbers)) if isinstance(page_numbers, list) else page_numbers
    tables = helpers.extract_tables(uploaded_file, page_numbers_str)
    return tables

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

# Function to extract images from PDF
def extract_images(reader: PdfReader.pages, page_numbers_str: str = "all") -> dict:
    images = {}
    if page_numbers_str == "all":
        for page in reader.pages:
            images |= {image.data: image.name for image in page.images}
    else:
        pages = parse_page_numbers(page_numbers_str)
        for page in pages:
            images.update({image.data: image.name for image in reader.pages[page].images})
    return images

# Function to convert table to CSV (You may need to implement this in helpers.py)
def convert_table_to_csv(table):
    import io
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(table)
    return output.getvalue()

# Matching function for table extraction
def match_terms_in_text(text):
    terms = [
        "company", "plan name", "Ftwilliam Id", "Total aum", "Mscs account", "Safe Habor", "Vesting", "profit sharing vesting", 
        "plan type", "compensation definition", "deferral change frequency", "match frequency", "entry date", "match entry date", 
        "profit share entry date", "minimum age", "match minimum age", "profit share minimum age", "eligibility delay", 
        "match eligibility delay", "profit share eligibility delay", "eligibility delay rolling", "hours of service", 
        "plan effective date", "plan restatement date", "plan number"
    ]
    
    matches = []
    for term in terms:
        matches.extend(re.findall(f'({term}.*?)(?=\n|$)', text, re.IGNORECASE))
    
    return matches

# Function to extract information matching specific terms
def extract_information_from_pdf(pdf_reader):
    info_data = []
    
    for page_num, page in enumerate(pdf_reader.pages):
        text = page.extract_text()
        matches = match_terms_in_text(text)
        
        for match in matches:
            info_data.append([match, text, page_num + 1])
    
    return info_data

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

            # Convert the PDF to Markdown format
            markdown_text = convert_pdf_to_markdown(pdf_document)

            # Input for custom term to search for
            custom_term = st.text_input("Enter a term to analyze (e.g., 'eligibility')", "eligibility")

            # Extract contextual mentions
            context_data = extract_contextual_relationships(markdown_text, custom_term)
            st.subheader(f"Contextual Mentions of '{custom_term.capitalize()}'")
            with st.expander("Expand to view Contextual Mentions"):
                if context_data:
                    for entry in context_data:
                        st.write(f"- {entry}")
                else:
                    st.write(f"No mentions of '{custom_term}' found in the document.")

            # 1. Extract relevant information matching the terms
            info_data = extract_information_from_markdown(markdown_text, page_number=1)  # Assuming page_number for simplicity
            st.subheader("Extracted Information for Specific Terms")
            if info_data:
                info_df = pd.DataFrame(info_data, columns=["Term", "Full Text", "Page Number"])
                st.dataframe(info_df)
            else:
                st.write("No relevant information found in the document.")

        else:
            st.error("Unable to process the PDF. It may be password protected.")

except Exception as e:
    st.error(f"An error occurred: {e}")
    st.write(traceback.format_exc())
