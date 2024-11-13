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
from streamlit_pdf_viewer import pdf_viewer

from utils import helpers, init_session_states, page_config

page_config.set()

# Initialize session_state variables if they don't exist
if "file" not in st.session_state:
    st.session_state["file"] = None  # or any default value
if "name" not in st.session_state:
    st.session_state["name"] = ""  # or any default value
if "password" not in st.session_state:
    st.session_state["password"] = ""  # or any default value
if "is_encrypted" not in st.session_state:
    st.session_state["is_encrypted"] = False  # or any default value

# ---------- HEADER ----------
st.title("📄 PDF WorkDesk!")
st.write(
    "User-friendly, lightweight, and open-source tool to preview and extract content and metadata from PDFs, add or remove passwords, modify, merge, convert and compress PDFs."
)

init_session_states.init()

# ---------- OPERATIONS ----------
try:
    pdf, reader, *other_values = helpers.load_pdf(key="main")

except FileNotDecryptedError:
    pdf = "password_required"

if pdf == "password_required":
    st.error("PDF is password protected. Please enter the password to proceed.")
elif pdf:
    lcol, rcol = st.columns(2)

    with lcol.expander(label="🔍 Extract text"):
        extract_text_lcol, extract_text_rcol = st.columns(2)

        page_numbers_str = helpers.select_pages(
            container=extract_text_lcol,
            key="extract_text_pages",
        )

        mode = extract_text_rcol.radio(
            "Extraction mode",
            options=["plain", "layout"],
            horizontal=True,
            help="Layout mode extracts text in a format resembling the layout of the source PDF",
        )

        if page_numbers_str:
            try:
                text = helpers.extract_text(reader, page_numbers_str, mode)
            except (IndexError, ValueError):
                st.error("Specified pages don't exist. Check the format.", icon="⚠️")
            else:
                st.text(text)

                with open("text.txt", "w", encoding="utf-8") as f:
                    f.write(text)

                with open("text.txt") as f:
                    st.download_button(
                        "💾 Download extracted text",
                        data=f,
                        use_container_width=True,
                    )

    with rcol.expander(label="️🖼️ Extract images"):
        if page_numbers_str := helpers.select_pages(
            container=st,
            key="extract_image_pages",
        ):
            try:
                images = helpers.extract_images(reader, page_numbers_str)
            except (IndexError, ValueError):
                st.error("Specified pages don't exist. Check the format.", icon="⚠️")
            else:
                if images:
                    for data, name in images.items():
                        st.image(data, caption=name)
                else:
                    st.info("No images found")

    with lcol.expander("📊 Extract table"):
        if page_numbers_str := helpers.select_pages(
            container=st,
            key="extract_table_pages",
        ):
            helpers.extract_tables(
                st.session_state["file"],  # Use session_state["file"]
                page_numbers_str,
            )

    with rcol.expander("🔄️ Convert to Word"):
        st.caption("Takes ~1 second/page. Will remove password if present")

        if st.button("Convert PDF to Word", use_container_width=True):
            st.download_button(
                "📥 Download Word document",
                data=helpers.convert_pdf_to_word(pdf),
                file_name=f"{st.session_state['name'][:-4]}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

    with lcol.expander("🔃 Rotate PDF"):
        # TODO: Add password back to converted PDF if original was protected
        st.caption("Will remove password if present")
        angle = st.slider(
            "Clockwise angle",
            min_value=0,
            max_value=270,
            step=90,
            format="%d°",
        )

        with PdfWriter() as writer:
            for page in reader.pages:
                writer.add_page(page)
                writer.pages[-1].rotate(angle)

            # TODO: Write to byte_stream
            writer.write("rotated.pdf")

            with open("rotated.pdf", "rb") as f:
                pdf_viewer(f.read(), height=250, width=300)
                st.download_button(
                    "📥 Download rotated PDF",
                    data=f,
                    mime="application/pdf",
                    file_name=f"{st.session_state['name'].rsplit('.')[0]}_rotated_{angle}.pdf",
                    use_container_width=True,
                )

    # ---------- ADDITIONAL ANALYSIS ----------
    def clean_text(text):
        # Convert text to lowercase
        text = text.lower()
        # Remove numbers and punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def extract_text_from_pdf(pdf_file):
        pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
        text = ""

        # Iterate through each page
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            # Extract text using layout analysis (this helps to capture table-like structures)
            text += page.get_text("text")  # Standard text extraction

        return text

    def extract_related_terms(text, term, window_size=5):
        """Extract terms related to the given term by considering words within a window of size."""
        term = term.lower()
        words = text.split()
        related_terms = set()

        # Find the positions of the term in the text
        positions = [i for i, word in enumerate(words) if term in word.lower()]

        # Collect words within a defined window around the term
        for pos in positions:
            start = max(0, pos - window_size)
            end = min(len(words), pos + window_size + 1)
            for i in range(start, end):
                if words[i].lower() != term:
                    related_terms.add(words[i].lower())

        return list(related_terms)

    # Main analysis interface
    st.subheader("Textual Analysis")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
        st.write(f"File: {uploaded_file.name}")
        extracted_text = extract_text_from_pdf(uploaded_file)
        cleaned_text = clean_text(extracted_text)

        custom_term = st.text_input("Enter a term to summarize references (e.g., 'eligibility')", "eligibility")

        dynamic_questions = generate_dynamic_questions(cleaned_text, custom_term)
        st.subheader("Sample Questions Based on Your Text")
        for question in dynamic_questions:
            if st.button(question):
                response = generate_response_to_question(extracted_text, question, custom_term)
                st.write(f"Response: {response}")

        context_data = extract_contextual_relationships(extracted_text, custom_term)
        st.subheader(f"Contextual Mentions of '{custom_term.capitalize()}'")
        if context_data:
            for entry in context_data:
                st.write(f"Sentence: {entry['sentence']}")
                if entry['related_terms']:
                    st.write(f"Related Terms: {', '.join(entry['related_terms'])}")
        else:
            st.write(f"No mentions of '{custom_term}' found in the document.")

        full_lines = print_full_lines_with_term(extracted_text, custom_term, page_info={})
        st.subheader(f"Full Lines Containing '{custom_term.capitalize()}'")
        st.write(full_lines)

        related_terms = extract_related_terms(extracted_text, custom_term)
        st.subheader(f"Related Terms to '{custom_term.capitalize()}'")
        if related_terms:
            st.write(f"Related terms found in the document: {', '.join(related_terms)}")
        else:
            st.write(f"No related terms found for '{custom_term}' in the document.")

except Exception as e:
    st.error(
        f"""The app has encountered an error:  
        `{e}`  
        Please create an issue [here](https://github.com/SiddhantSadangi/pdf-workdesk/issues/new) 
        with the below traceback""",
        icon="🥺",
    )
    st.code(traceback.format_exc())
