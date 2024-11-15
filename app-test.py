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

# Function to extract tables from PDF
def extract_tables_from_pdf(pdf_reader, term):
    tables = helpers.extract_tables(uploaded_file, "all")
    
    matching_tables = []
    for table in tables:
        for row in table:
            if any(term.lower() in cell.lower() for cell in row):  # Check if term is in any cell of the row
                matching_tables.append(table)
                break

    return matching_tables

# Function to extract and display matching data based on term
def extract_matching_info(text, term):
    # Define the list of terms for internal form extraction
    terms_list = [
        "company", "plan name", "Ftwilliam ID", "Total aum", "Mscs account", "Safe Harbor", 
        "Vesting", "profit sharing vesting", "plan type", "compensation definition", 
        "deferral change frequency", "match frequency", "entry date", "match entry date", 
        "profit share entry date", "minimum age", "match minimum age", "profit share minimum age", 
        "eligibility delay", "match eligibility delay", "profit share eligibility delay", 
        "eligibility delay rolling", "hours of service", "plan effective date", 
        "plan restatement date", "plan number"
    ]

    matching_info = []
    sentences = text.split(".")
    for sentence in sentences:
        for term in terms_list:
            if term in sentence.lower():
                matching_info.append((term, sentence.strip()))
                
    return matching_info

# Function to match term with extracted data
def match_term_to_table(text, tables, term):
    matching_data = []
    for table in tables:
        for row in table:
            for cell in row:
                if term.lower() in cell.lower():
                    matching_data.append((term, cell, "Page X"))  # Page number will be added later
    return matching_data

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

            # 4. Extracting Tables based on Term
            st.subheader(f"Extract Tables Matching '{custom_term.capitalize()}'")
            matching_tables = extract_tables_from_pdf(pdf_reader, custom_term)
            
            if matching_tables:
                # Match term with table data and display
                matched_data = []
                for table in matching_tables:
                    matched_data.extend(match_term_to_table(extracted_text, [table], custom_term))
                
                if matched_data:
                    # Create a DataFrame for display
                    df = pd.DataFrame(matched_data, columns=["Term", "Description", "Page Number"])
                    st.write(df)
                else:
                    st.write(f"No matching data found for '{custom_term}'.")
            else:
                st.write(f"No tables containing '{custom_term}' found.")

        else:
            st.error("Unable to process the PDF. It may be password protected.")

except Exception as e:
    st.error(f"An error occurred: {e}")
    st.write(traceback.format_exc())
