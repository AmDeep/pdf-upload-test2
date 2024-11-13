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

    if pdf == "password_required":
        st.error("PDF is password protected. Please enter the password to proceed.")
    elif pdf:
        lcol, rcol = st.columns(2)

        # Text extraction from PDF
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

        # Image extraction
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

        # Table extraction
        with lcol.expander("📊 Extract table"):
            if page_numbers_str := helpers.select_pages(
                container=st,
                key="extract_table_pages",
            ):
                helpers.extract_tables(
                    st.session_state["file"],  # Use session_state["file"]
                    page_numbers_str,
                )

        # PDF to Word Conversion
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

        # Rotate PDF
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

                # Write to byte_stream
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

        # --------------- Custom Text Extraction & Term Analysis ----------------

        # Function to clean extracted text
        def clean_text(text):
            text = text.lower()
            text = re.sub(r'[^\w\s]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text

        # Function to tokenize text
        def tokenize(text):
            return text.split()

        # Function for vectorization (Simple Bag of Words)
        def vectorize(tokens):
            return Counter(tokens)

        # Function to extract contextual relationships
        def extract_contextual_relationships(text, term, page_info=None):
            term = term.lower()
            sentences = text.split('.')
            context_data = []

            for sentence in sentences:
                sentence = sentence.strip()
                if term in sentence:
                    words = sentence.split()
                    relevant_words = [word for word in words if word not in ["the", "and", "is", "to", "in", "for", "on", "with", "as", "it", "at", "by", "that", "from", "this", "was", "were", "are", "be", "been", "being"]]
                    related_terms = [word for word in relevant_words if word != term]

                    context_data.append({
                        "sentence": sentence,
                        "related_terms": related_terms
                    })

            if not context_data and page_info:
                for page_num, page_text in page_info.items():
                    if term in page_text:
                        context_data.append({
                            "sentence": term,
                            "related_terms": [],
                            "page_num": page_num
                        })

            return context_data

        # Function to summarize mentions of a term
        def summarize_mentions(text, term):
            term = term.lower()
            sentences = text.split('.')
            summary_data = []

            for sentence in sentences:
                sentence = sentence.strip()
                if term in sentence:
                    summary_data.append(sentence)

            if summary_data:
                return "\n".join(summary_data)
            else:
                return f"No mentions of '{term}' found in the document."

        # Function to generate dynamic questions
        def generate_dynamic_questions(text, term):
            term = term.lower()

            context_data = extract_contextual_relationships(text, term)

            questions = []
            if context_data:
                questions.append(f"What is mentioned about '{term}' in the document?")
                questions.append(f"Can you provide examples of '{term}' being discussed in the document?")

                if any("requirement" in sentence.lower() for sentence in [entry['sentence'] for entry in context_data]):
                    questions.append(f"What requirements or rules are associated with '{term}'?")

                if any("defined" in sentence.lower() for sentence in [entry['sentence'] for entry in context_data]):
                    questions.append(f"How is '{term}' defined in the document?")

                if len(context_data) > 1:
                    questions.append(f"How does the discussion of '{term}' differ in various sections of the document?")

            return questions

        # Function to extract text from PDF
        def extract_text_from_pdf(pdf_file):
            pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
            text = ""

            for page_num in range(pdf_document.page_count):
                page = pdf_document.load_page(page_num)
                text += page.get_text("text")

            return text

        # Full line extraction
        def print_full_lines_with_term(extracted_text, term, page_info):
            term = term.lower()
            full_lines_with_term = []

            lines = extracted_text.split('\n')
            for line in lines:
                if term in line.lower():
                    page_num = page_info.get(line.strip(), "Unknown page")

                    if isinstance(page_num, int):
                        page_num = str(page_num + 1)

                    full_line = line.replace(term, f"**_{term}_**")
                    full_lines_with_term.append(f"Page {page_num}: {full_line}")

            return "\n".join(full_lines_with_term)

        # Function to extract related terms
        def extract_related_terms(text, term):
            term = term.lower()
            related_terms = set()

            words = text.split()
            for word in words:
                if term in word.lower() and word.lower() != term:
                    related_terms.add(word)

            return list(related_terms)

        # -------- User input to extract and analyze custom term --------
        custom_term = st.text_input("Enter a custom term to analyze", "")

        if custom_term:
            # Extract text from PDF
            extracted_text = extract_text_from_pdf(pdf)

            # Print full lines containing the term
            full_lines = print_full_lines_with_term(extracted_text, custom_term, page_info={})
            st.subheader(f"Full Lines Containing '{custom_term.capitalize()}'")
            st.write(full_lines)

            # Extract related terms
            related_terms = extract_related_terms(extracted_text, custom_term)
            st.subheader(f"Related Terms to '{custom_term.capitalize()}'")

            if related_terms:
                st.write(f"Related terms found in the document: {', '.join(related_terms)}")

            # Dynamic questions
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
