import os
import sys
import traceback
import re
import fitz  # PyMuPDF
from collections import Counter
from io import BytesIO

import streamlit as st
from pypdf import PaperSize, PdfReader, PdfWriter, Transformation
from pypdf.errors import FileNotDecryptedError
from streamlit_pdf_viewer import pdf_viewer
from utils import helpers, init_session_states, page_config

# Set the page config for Streamlit
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
st.title("📄 PDF WorkDesk & Text Analysis Tool")
st.write(
    "An integrated tool for PDF manipulation (preview, extract, modify, rotate, etc.) and textual analysis (term extraction, contextual relationships, etc.)."
)

init_session_states.init()

# ---------- OPERATIONS ----------

# PDF Operations
try:
    pdf, reader, *other_values = helpers.load_pdf(key="main")
except FileNotDecryptedError:
    pdf = "password_required"

if pdf == "password_required":
    st.error("PDF is password protected. Please enter the password to proceed.")
elif pdf:
    lcol, rcol = st.columns(2)

    # PDF Text Extraction Section
    with lcol.expander(label="🔍 Extract text"):
        extract_text_lcol, extract_text_rcol = st.columns(2)
        page_numbers_str = helpers.select_pages(container=extract_text_lcol, key="extract_text_pages")
        mode = extract_text_rcol.radio(
            "Extraction mode", options=["plain", "layout"], horizontal=True,
            help="Layout mode extracts text in a format resembling the layout of the source PDF"
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
                        "💾 Download extracted text", data=f, use_container_width=True
                    )

    # PDF Image Extraction Section
    with rcol.expander(label="️🖼️ Extract images"):
        if page_numbers_str := helpers.select_pages(container=st, key="extract_image_pages"):
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

    # PDF Table Extraction Section
    with lcol.expander("📊 Extract table"):
        if page_numbers_str := helpers.select_pages(container=st, key="extract_table_pages"):
            helpers.extract_tables(st.session_state["file"], page_numbers_str)

    # Convert PDF to Word Section
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

    # Rotate PDF Section
    with lcol.expander("🔃 Rotate PDF"):
        st.caption("Will remove password if present")
        angle = st.slider("Clockwise angle", min_value=0, max_value=270, step=90, format="%d°")
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

# ---------- Textual Analysis ----------
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def tokenize(text):
    return text.split()

def vectorize(tokens):
    return Counter(tokens)

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
            context_data.append({"sentence": sentence, "related_terms": related_terms})
    return context_data

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

def generate_response_to_question(text, question, term):
    term = term.lower()
    context_data = extract_contextual_relationships(text, term)
    if "about" in question or "what" in question.lower():
        if context_data:
            response = f"The document discusses '{term}' in various contexts: "
            for entry in context_data:
                response += f"\n- In the sentence: '{entry['sentence']}', related terms are {', '.join(entry['related_terms'])}."
            return response
        else:
            return f"'{term}' is only briefly mentioned or not fully explored in the document."
    elif "examples" in question.lower():
        examples = [entry['sentence'] for entry in context_data if "example" in entry['sentence'].lower()]
        if examples:
            return f"Here is an example of '{term}' in the document: {examples[0]}"
        else:
            return f"No clear examples of '{term}' were found in the document."

    elif "requirements" in question.lower() or "rules" in question.lower():
        requirements = [entry['sentence'] for entry in context_data if "requirement" in entry['sentence'].lower()]
        if requirements:
            return f"'{term}' is associated with specific eligibility requirements, such as {requirements[0]}"
        else:
            return f"No specific eligibility requirements related to '{term}' were found in the document."

    elif "defined" in question.lower():
        definitions = [entry['sentence'] for entry in context_data if "defined" in entry['sentence'].lower()]
        if definitions:
            return f"'{term}' is defined in the document as: {definitions[0]}"
        else:
            return f"'{term}' is not explicitly defined in the document."

    elif "different" in question.lower() and len(context_data) > 1:
        return f"Across different sections, '{term}' is discussed from various perspectives."
    else:
        return f"The document offers a detailed exploration of '{term}', providing insight into its significance."

# Extract text from PDF (including tables)
def extract_text_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text += page.get_text("text")
    return text

# Full lines containing the term
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
