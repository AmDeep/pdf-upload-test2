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
    # Split the input string by comma or hyphen
    parts = page_numbers_str.split(",")

    # Initialize an empty list to store parsed page numbers
    parsed_page_numbers = []

    # Iterate over each part
    for part in parts:
        # Remove any leading/trailing spaces
        part = part.strip()

        # If the part contains a hyphen, it represents a range
        if "-" in part:
            start, end = map(int, part.split("-"))
            parsed_page_numbers.extend(range(start, end + 1))
        else:
            # Otherwise, it's a single page number
            parsed_page_numbers.append(int(part))

    return [i - 1 for i in parsed_page_numbers]


# Function to extract tables and preview pages from PDF
def extract_tables_from_pdf(pdf_reader, page_numbers):
    # Convert list of page numbers to a comma-separated string
    page_numbers_str = ",".join(map(str, page_numbers)) if isinstance(page_numbers, list) else page_numbers
    
    # Call the helpers.extract_tables function with the correct string format for page numbers
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
            images.update(
                {image.data: image.name for image in reader.pages[page].images}
            )

    return images


# Function to handle table extraction
def extract_tables_from_pdf(pdf_reader, page_numbers):
    tables = helpers.extract_tables(uploaded_file, page_numbers)
    return tables


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


# Function to extract tables and relevant information
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

            # Display the extracted and cleaned text
            ##st.subheader("Extracted Text")
            ##st.text_area("Text", cleaned_text, height=200)

            # Input for custom term to search for
            custom_term = st.text_input("Enter a term to analyze (e.g., 'eligibility')", "eligibility")

            # 1. Contextual Relationship Extraction
            def extract_contextual_relationships(text, term):
                term = term.lower()
                sentences = text.split('.')
                context_data = []
                for sentence in sentences:
                    if term in sentence.lower():
                        context_data.append(sentence.strip())
                return context_data

            context_data = extract_contextual_relationships(cleaned_text, custom_term)
            st.subheader(f"Contextual Mentions of '{custom_term.capitalize()}'")
            with st.expander("Expand to view Contextual Mentions"):
                if context_data:
                    for entry in context_data:
                        st.write(f"- {entry}")
                else:
                    st.write(f"No mentions of '{custom_term}' found in the document.")

            # 2. Summarize Mentions
            def summarize_mentions(text, term):
                term = term.lower()
                sentences = text.split('.')
                summary = []
                for sentence in sentences:
                    if term in sentence.lower():
                        summary.append(sentence.strip())
                return "\n".join(summary) if summary else f"No mentions of '{term}' found."

            summary = summarize_mentions(cleaned_text, custom_term)
            st.subheader(f"Summary of Mentions for '{custom_term.capitalize()}'")
            st.text_area("Summary", summary, height=150)

            # 3. Full Lines Containing the Term
            def print_full_lines_with_term(text, term):
                term = term.lower()
                full_lines = []
                lines = text.split("\n")
                for line in lines:
                    if term in line.lower():
                        full_lines.append(line)
                return "\n".join(full_lines)

            full_lines = print_full_lines_with_term(extracted_text, custom_term)
            st.subheader(f"Full Lines Containing '{custom_term.capitalize()}'")
            st.text_area("Full Lines", full_lines, height=150)

            # 4. Vectorization (Simple Bag of Words)
            def vectorize(text):
                tokens = text.split()
                return Counter(tokens)

            vectorized_text = vectorize(cleaned_text)
            ##st.subheader("Word Frequency (Bag of Words)")
            ##st.write(vectorized_text)


            # 1. Table Extraction (Button to extract tables)
            with st.expander("📊 Extract Tables from PDF"):
                # Handle page number input
                page_input = st.text_input("Enter page number(s) (e.g., '1', '1-3', 'all')", key="page_input")
                if st.button("Extract Tables"):
                    if page_input.lower() == "all":
                        page_numbers = list(range(len(pdf_reader.pages)))
                    else:
                        try:
                            page_numbers = parse_page_numbers(page_input)  # Pass page_input (as string) to the parser
                        except ValueError:
                            st.error("Invalid page numbers format. Please enter a valid page range or 'all'.")
                            page_numbers = []
                    if page_numbers:
                        st.write(f"Extracting tables from pages: {page_numbers}")
                        extract_tables_from_pdf(pdf_reader, page_numbers)
                    else:
                        st.warning("No valid pages selected for table extraction.")

            # Extract information matching specific terms
            info_data = extract_information_from_pdf(pdf_reader)
            st.subheader("Extracted Information")
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
