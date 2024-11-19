import os
import re
import pandas as pd
from io import BytesIO
from pypdf import PdfReader
from collections import Counter
import streamlit as st
import fitz  # PyMuPDF
import traceback
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

# Function to parse page numbers from a string
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
def extract_text(reader, page_numbers_str="all", mode="plain"):
    text = ""
    if page_numbers_str == "all":
        for page in reader.pages:
            text += " " + page.extract_text(extraction_mode=mode)
    else:
        pages = parse_page_numbers(page_numbers_str)
        for page in pages:
            text += " " + reader.pages[page].extract_text()
    return text

# Function to convert PDF to Markdown
def pdf_to_markdown(pdf_document):
    markdown_text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        markdown_text += page.get_text("markdown")
    return markdown_text

# Function to clean the response text
def clean_response(response, term):
    term_lower = term.lower()
    return re.sub(rf"{term_lower}:?", "", response, flags=re.IGNORECASE).strip()

# Function to dynamically extract relevant information from the PDF based on specified terms
def extract_relevant_information(pdf_reader, terms):
    info_data = {term: None for term in terms}
    for page_num, page in enumerate(pdf_reader.pages):
        text = page.extract_text()
        for term in terms:
            if info_data[term] is None:
                pattern = rf"({term}.*?)(?=\n|$)"
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    info_data[term] = [term, clean_response(match.group(1), term), page_num + 1]
    return [[term, info_data[term][1] if info_data[term] else "", info_data[term][2] if info_data[term] else ""] for term in terms]

# Function to handle table extraction
def extract_tables_from_pdf(pdf_reader, page_numbers):
    tables = helpers.extract_tables(uploaded_file, page_numbers)
    return tables

# ---------- MAIN SECTION ----------

try:
    if uploaded_file is not None:
        try:
            pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            pdf_reader = PdfReader(uploaded_file)
            session_state["password"], session_state["is_encrypted"] = "", False
        except FileNotDecryptedError:
            pdf_document = "password_required"
            st.error("PDF is password protected. Please enter the password to proceed.")

        if pdf_document != "password_required" and pdf_document:

            extracted_text = ""
            for page_num in range(pdf_document.page_count):
                page = pdf_document.load_page(page_num)
                extracted_text += page.get_text("text")

            markdown_text = pdf_to_markdown(pdf_document)

            def clean_text(text):
                text = text.lower()
                text = re.sub(r'[^\w\s]', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text

            cleaned_text = clean_text(extracted_text)

            custom_term = st.text_input("Enter a term to analyze (e.g., 'eligibility')", "eligibility")

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

            def vectorize(text):
                tokens = text.split()
                return Counter(tokens)

            vectorized_text = vectorize(cleaned_text)

            terms_to_extract = [
                "NAME", "TRUSTEE", "EIN", "YEAR END", "ENTITY TYPE", "ENTITY STATE",
                "Safe harbor", "Vesting", "Profit Sharing vesting", "Plan Type",
                "Compensation Definition", "Defferal change frequency", "Match frequency",
                "Entry date", "Match Entry date", "Profit share entry date", "Minimum age",
                "Match Minimum age", "Profit Share Minimum Age", "Eligibility delay"
            ]

            info_data = extract_relevant_information(pdf_reader, terms_to_extract)

            with st.container():
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader("Extracted Information")
                    info_df = pd.DataFrame(info_data, columns=["Term", "Response", "Page Number"])
                    st.dataframe(info_df)
                with col2:
                    st.subheader("Document Preview")
                    preview_area = st.empty()
                    preview_area.markdown(
                        '<div style="height:400px; overflow-y:scroll; width:300px;">', unsafe_allow_html=True)
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
