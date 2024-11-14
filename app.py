import os
import sys
import traceback
from io import BytesIO
import streamlit as st
import fitz  # PyMuPDF
import re
from collections import Counter
from pypdf import PaperSize, PdfReader, PdfWriter, Transformation
from pypdf.errors import FileNotDecryptedError
from streamlit import session_state
from streamlit_pdf_viewer import pdf_viewer
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
            st.subheader("Extracted Text")
            st.text_area("Text", cleaned_text, height=200)

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

            # 4. Vectorization (Simple Bag of Words)
            def vectorize(text):
                tokens = text.split()
                return Counter(tokens)

            vectorized_text = vectorize(cleaned_text)
            st.subheader("Word Frequency (Bag of Words)")
            st.write(vectorized_text)

            # ---------- PDF Editing Operations ----------
            lcol, rcol = st.columns(2)

            with lcol.expander("🔒 PDF Encryption & Decryption"):
                # Password-protect or remove password from PDF
                new_password = st.text_input("Enter new password (Leave blank to remove password)", type="password")
                if new_password:
                    with PdfWriter() as writer:
                        for page in pdf_reader.pages:
                            writer.add_page(page)
                        writer.encrypt(new_password)
                        filename = "protected_pdf.pdf"
                        with open(filename, "wb") as f:
                            writer.write(f)
                        st.download_button("📥 Download Protected PDF", data=open(filename, "rb"), file_name=filename)

            with rcol.expander("🔄 PDF Operations"):
                # Rotate PDF
                angle = st.slider("Rotate PDF (degrees)", min_value=0, max_value=270, step=90, format="%d°")
                with PdfWriter() as writer:
                    for page in pdf_reader.pages:
                        writer.add_page(page)
                        writer.pages[-1].rotate(angle)
                    writer.write("rotated.pdf")
                    st.download_button("📥 Download Rotated PDF", data=open("rotated.pdf", "rb"), file_name="rotated.pdf")

            # 5. Convert PDF to Word
            with lcol.expander("🔄 Convert to Word"):
                if st.button("Convert PDF to Word"):
                    word_file = helpers.convert_pdf_to_word(uploaded_file)
                    st.download_button("📥 Download Word Document", data=word_file, file_name="converted.docx")

            # 6. Merge PDFs
            with lcol.expander("➕ Merge PDFs"):
                st.caption("Merge another PDF with the current one.")
                second_pdf = st.file_uploader("Upload another PDF to merge", type="pdf")
                if second_pdf:
                    with PdfWriter() as merger:
                        for file in [uploaded_file, second_pdf]:
                            reader_to_merge = PdfReader(file)
                            for page in reader_to_merge.pages:
                                merger.add_page(page)
                        merger.write("merged.pdf")
                        st.download_button("📥 Download Merged PDF", data=open("merged.pdf", "rb"), file_name="merged.pdf")

            # 7. Reduce PDF Size
            with rcol.expander("🤏 Reduce PDF Size"):
                if st.button("Reduce PDF Size"):
                    reduced_pdf = helpers.compress_pdf(uploaded_file)
                    st.download_button("📥 Download Reduced PDF", data=reduced_pdf, file_name="reduced.pdf")
        else:
            st.error("PDF could not be processed.")

    else:
        st.info("Please upload a PDF file to get started.")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.code(traceback.format_exc())
