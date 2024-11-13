import os
import sys
import traceback
from io import BytesIO

import streamlit as st
import fitz  # PyMuPDF
import re
from collections import Counter
from pypdf.errors import FileNotDecryptedError
from streamlit_pdf_viewer import pdf_viewer

from utils import helpers, init_session_states, page_config

# Set up page config
page_config.set()

# Initialize session_state variables if they don't exist
if "file" not in st.session_state:
    st.session_state["file"] = None
if "name" not in st.session_state:
    st.session_state["name"] = ""
if "password" not in st.session_state:
    st.session_state["password"] = ""
if "is_encrypted" not in st.session_state:
    st.session_state["is_encrypted"] = False

# ---------- HEADER ----------
st.title("📄 PDF WorkDesk!")
st.write(
    "User-friendly, lightweight, and open-source tool to preview and extract content and metadata from PDFs, "
    "add or remove passwords, modify, merge, convert and compress PDFs."
)

init_session_states.init()

# ---------- OPERATIONS ----------
try:
    # Loading the PDF file (handling password protection)
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

# Custom Term Analysis Operations
def extract_text_from_pdf(pdf_file):
    """Extracts text from a PDF file."""
    pdf_document = fitz.open(stream=pdf_file, filetype="pdf")  # Directly use the bytes stream
    text = ""

    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text += page.get_text("text")

    return text


# Custom Term Analysis: Extract related terms
def extract_related_terms(text, term):
    term = term.lower()
    related_terms = set()
    
    words = text.split()
    for word in words:
        if term in word.lower() and word.lower() != term:
            related_terms.add(word)
    
    return list(related_terms)


# Custom Term Analysis: Full lines containing the custom term
def print_full_lines_with_term(extracted_text, term, page_info):
    term = term.lower()
    full_lines_with_term = []
    
    lines = extracted_text.split('\n')
    for line in lines:
        if term in line.lower():
            page_num = page_info.get(line.strip(), "Unknown page")
            
            if isinstance(page_num, int):
                page_num = str(page_num + 1)  # Convert to 1-based indexing
            
            full_line = line.replace(term, f"**_{term}_**")
            full_lines_with_term.append(f"Page {page_num}: {full_line}")  # Ensure page_num is properly formatted as a string
    
    return "\n".join(full_lines_with_term)


# Main Streamlit app interface
st.title("PDF Text Extractor and Contextual Analysis")
st.write("Upload a PDF file to extract its text, clean it, and analyze content based on a custom term.")

# File uploader widget
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    st.write(f"File: {uploaded_file.name}")
    
    # Extract text from the uploaded PDF
    extracted_text = extract_text_from_pdf(uploaded_file)

    # Clean the extracted text
    cleaned_text = helpers.clean_text(extracted_text)

    # Input for custom term (e.g., "eligibility")
    custom_term = st.text_input("Enter a term to summarize references (e.g., 'eligibility')", "eligibility")

    if custom_term:
        # Extract full lines with the custom term
        full_lines = print_full_lines_with_term(extracted_text, custom_term, page_info={})
        st.subheader(f"Full Lines Containing '{custom_term.capitalize()}'")
        st.write(full_lines)

        # Extract related terms
        related_terms = extract_related_terms(extracted_text, custom_term)
        st.subheader(f"Related Terms to '{custom_term.capitalize()}'")

        if related_terms:
            st.write(f"Related terms found in the document: {', '.join(related_terms)}")

        # Generate dynamic questions
        questions = generate_dynamic_questions(extracted_text, custom_term)
        st.subheader(f"Generated Questions for '{custom_term.capitalize()}'")

        if questions:
            st.write("\n".join(questions))

except Exception as e:
    st.error(
        f"""The app has encountered an error:  
        `{e}`  
        Please create an issue [here](https://github.com/SiddhantSadangi/pdf-workdesk/issues/new) 
        with the below traceback""",
        icon="🥺",
    )
    st.code(traceback.format_exc())

# Success message for the user
st.success(
    "[Star the repo](https://github.com/SiddhantSadangi/pdf-workdesk) to show your :heart: ",
    icon="⭐",
)
