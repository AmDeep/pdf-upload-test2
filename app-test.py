import os
import sys
import traceback
from io import BytesIO
import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd
import pdfplumber
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError
from streamlit import session_state
from collections import Counter
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

# Function to extract text from PDF
def extract_text(reader: PdfReader.pages, mode: str = "plain") -> str:
    text = ""
    for page in reader.pages:
        text += page.extract_text(extraction_mode=mode)
    return text

# Function to extract tables from PDF based on predefined terms
def extract_tables_from_pdf(pdf_reader, terms_list):
    tables = helpers.extract_tables(uploaded_file, "all")
    
    matching_tables = []
    for table in tables:
        for row in table:
            if any(term.lower() in cell.lower() for term in terms_list for cell in row):  # Check if any term is in the row
                matching_tables.append(table)
                break

    return matching_tables

# Function to extract and display matching data based on predefined terms
def extract_matching_info(text, terms_list):
    matching_info = []
    sentences = text.split(".")
    for sentence in sentences:
        for term in terms_list:
            if term in sentence.lower():
                matching_info.append((term, sentence.strip()))
                
    return matching_info

# Function to match term with extracted data from tables
def match_term_to_table(tables, terms_list, page_numbers):
    matched_data = []
    for page_num, table in zip(page_numbers, tables):
        for row in table:
            for cell in row:
                for term in terms_list:
                    if term.lower() in cell.lower():
                        matched_data.append((term, cell, page_num))  # Include page number for reference
    return matched_data

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

            # Predefined terms to look for in the document
            terms_list = [
                "company", "plan name", "Ftwilliam ID", "Total aum", "Mscs account", "Safe Harbor", 
                "Vesting", "profit sharing vesting", "plan type", "compensation definition", 
                "deferral change frequency", "match frequency", "entry date", "match entry date", 
                "profit share entry date", "minimum age", "match minimum age", "profit share minimum age", 
                "eligibility delay", "match eligibility delay", "profit share eligibility delay", 
                "eligibility delay rolling", "hours of service", "plan effective date", 
                "plan restatement date", "plan number"
            ]

            # 1. Extracting tables based on predefined terms (no user input term)
            st.subheader("Extract Table Matching Predefined Terms")
            page_numbers = list(range(len(pdf_reader.pages)))  # Extract from all pages
            matching_tables = extract_tables_from_pdf(pdf_reader, terms_list)

            if matching_tables:
                matched_data = match_term_to_table(matching_tables, terms_list, page_numbers)
                if matched_data:
                    matched_df = pd.DataFrame(matched_data, columns=["Term", "Description", "Page Number"])
                    st.write(matched_df)
                else:
                    st.write("No relevant data found for the predefined terms in the tables.")
            else:
                st.write("No tables containing predefined terms found.")

            # 2. Contextual Mentions (minimized and scrollable by default)
            custom_term = st.text_input("Enter a term to analyze (e.g., 'eligibility')", "eligibility")
            st.subheader(f"Contextual Mentions of '{custom_term.capitalize()}'")
            
            context_data = extract_matching_info(cleaned_text, [custom_term.lower()])
            
            # Show context in a scrollable, minimized area
            with st.expander(f"See Contextual Mentions for '{custom_term.capitalize()}'"):
                if context_data:
                    for entry in context_data:
                        st.write(f"- **{entry[0]}**: {entry[1]}")
                else:
                    st.write(f"No contextual mentions found for '{custom_term}'.")

            # 3. Full Lines Containing the Term
            def print_full_lines_with_term(text, term):
                full_lines = []
                lines = text.split("\n")
                for line in lines:
                    if term in line.lower():
                        full_lines.append(line)
                return "\n".join(full_lines)

            full_lines = print_full_lines_with_term(extracted_text, custom_term.lower())
            st.subheader(f"Full Lines Containing '{custom_term.capitalize()}'")
            st.text_area("Full Lines", full_lines, height=150)

        else:
            st.error("Unable to process the PDF. It may be password protected.")

except Exception as e:
    st.error(f"An error occurred: {e}")
    st.write(traceback.format_exc())
