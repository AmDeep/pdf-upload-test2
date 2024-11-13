import streamlit as st
import fitz  # PyMuPDF for PDF text and image extraction
import re
from collections import Counter
import pandas as pd
import io
from io import BytesIO
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError
from PIL import Image
from docx import Document

# Initialize session_state variables if they don't exist
if "file" not in st.session_state:
    st.session_state["file"] = None
if "name" not in st.session_state:
    st.session_state["name"] = ""
if "password" not in st.session_state:
    st.session_state["password"] = ""
if "is_encrypted" not in st.session_state:
    st.session_state["is_encrypted"] = False

# 1. Data Cleaning
def clean_text(text):
    # Convert text to lowercase
    text = text.lower()
    # Remove numbers and punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 2. Tokenization
def tokenize(text):
    return text.split()

# 3. Extract Text from PDF
def extract_text_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    
    # Iterate through each page
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text += page.get_text("text")  # Standard text extraction
    
    return text

# 4. Extract Table from PDF
def extract_table_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    table_data = []

    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        blocks = page.get_text("dict")['blocks']
        
        # Extract table-like structures (assuming we have some table-like format)
        for block in blocks:
            if block['type'] == 0:  # Only text blocks
                for line in block['lines']:
                    line_text = " ".join([span['text'] for span in line['spans']])
                    table_data.append(line_text.split())

    return table_data

# 5. Rotate PDF Pages
def rotate_pdf(pdf_file, angle=90):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    rotated_pdf = fitz.open()
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        page.set_rotation(angle)
        rotated_pdf.insert_pdf(pdf_document, from_page=page_num, to_page=page_num)
    
    buffer = BytesIO()
    rotated_pdf.save(buffer)
    buffer.seek(0)
    return buffer

# 6. Extract Images from PDF
def extract_images_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        image_list = page.get_images(full=True)
        
        for img in image_list:
            xref = img[0]
            image = pdf_document.extract_image(xref)
            img_bytes = image["image"]
            img_pil = Image.open(io.BytesIO(img_bytes))
            images.append(img_pil)
    
    return images

# 7. Convert to Word
def convert_to_word(extracted_text):
    doc = Document()
    doc.add_paragraph(extracted_text)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# Function to print full lines with the term (including page info)
def print_full_lines_with_term(extracted_text, term, page_info):
    term = term.lower()
    full_lines_with_term = []
    
    lines = extracted_text.split('\n')
    for line in lines:
        if term in line.lower():
            page_num = page_info.get(line.strip(), "Unknown page")
            
            if isinstance(page_num, int):
                page_num = str(page_num + 1)  # Convert page number to string and add 1 for 1-based indexing
            
            full_line = line.replace(term, f"**_{term}_**")
            full_lines_with_term.append(f"Page {page_num}: {full_line}")
    
    return "\n".join(full_lines_with_term)

# Function to extract related terms from the document
def extract_related_terms(text, term):
    term = term.lower()
    related_terms = set()
    
    words = text.split()
    for word in words:
        if term in word.lower() and word.lower() != term:
            related_terms.add(word)
    
    return list(related_terms)

# Main Streamlit app interface
st.title("📄 PDF Text Extractor and Contextual Analysis")
st.write("Upload a PDF file to extract its text, clean it, and analyze content based on a custom term.")
st.write("Additional Operations: Extract Table, Rotate PDF, Extract Images, Convert to Word")

# File uploader widget
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    st.write(f"File: {uploaded_file.name}")
    st.session_state["file"] = uploaded_file
    st.session_state["name"] = uploaded_file.name
    
    # Option to choose operation
    option = st.selectbox("Choose an operation", [
        "🔍 Extract text", 
        "📊 Extract table", 
        "🔃 Rotate PDF", 
        "️🖼️ Extract images", 
        "🔄️ Convert to Word"
    ])
    
    # Extract Text
    if option == "🔍 Extract text":
        extracted_text = extract_text_from_pdf(uploaded_file)
        st.subheader("Extracted Text")
        st.text_area("Text", extracted_text, height=300)

        # Clean the extracted text
        cleaned_text = clean_text(extracted_text)

        # Input for custom term (e.g., "eligibility")
        custom_term = st.text_input("Enter a term to summarize references (e.g., 'eligibility')", "eligibility")
        
        # Full lines with the term
        full_lines = print_full_lines_with_term(extracted_text, custom_term, page_info={})
        st.subheader(f"Full Lines Containing '{custom_term.capitalize()}'")
        st.write(full_lines)

        # Related terms
        related_terms = extract_related_terms(extracted_text, custom_term)
        st.subheader(f"Related Terms to '{custom_term.capitalize()}'")
        if related_terms:
            st.write(f"Related terms found in the document: {', '.join(related_terms)}")
        else:
            st.write(f"No related terms found for '{custom_term}' in the document.")

    # Extract Table
    elif option == "📊 Extract table":
        table_data = extract_table_from_pdf(uploaded_file)
        if table_data:
            st.subheader("Extracted Table")
            df = pd.DataFrame(table_data)
            st.dataframe(df)
            
            # Convert table to CSV
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            st.download_button("Download Table as CSV", csv_buffer, file_name="extracted_table.csv")

    # Rotate PDF
    elif option == "🔃 Rotate PDF":
        angle = st.selectbox("Choose rotation angle", [90, 180, 270])
        rotated_pdf = rotate_pdf(uploaded_file, angle)
        st.download_button("Download Rotated PDF", rotated_pdf, file_name="rotated.pdf")

    # Extract Images
    elif option == "️🖼️ Extract images":
        images = extract_images_from_pdf(uploaded_file)
        if images:
            st.subheader("Extracted Images")
            for i, img in enumerate(images):
                st.image(img, caption=f"Image {i+1}")
        else:
            st.write("No images found in the document.")

    # Convert to Word
    elif option == "🔄️ Convert to Word":
        extracted_text = extract_text_from_pdf(uploaded_file)
        word_buffer = convert_to_word(extracted_text)
        st.download_button("Download as Word Document", word_buffer, file_name="converted_document.docx")
