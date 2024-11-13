import streamlit as st
import fitz  # PyMuPDF
import re
from collections import Counter
import io

# 1. Data Cleaning
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 2. Tokenization
def tokenize(text):
    return text.split()

# 3. Vectorization (Simple Bag of Words)
def vectorize(tokens):
    return Counter(tokens)

# 4. Extract Contextual Relationships
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
    
    if not context_data and page_info:
        for page_num, page_text in page_info.items():
            if term in page_text:
                context_data.append({"sentence": term, "related_terms": [], "page_num": page_num})
    
    return context_data

# 5. Summarize Mentions of the User-Input Text
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

# Function to generate dynamic question prompts based on the extracted term
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

# Function to extract text from PDF (including tables)
def extract_text_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text += page.get_text("text")
    return text

# Function to extract tables from PDF (using layout-based approach)
def extract_tables_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    tables = []
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        blocks = page.get_text("dict")["blocks"]
        
        # Simple table extraction heuristic based on block position and text alignment
        table = []
        for block in blocks:
            if block['type'] == 0:  # Type 0 is text block
                lines = block["lines"]
                for line in lines:
                    text = " ".join([span['text'] for span in line['spans']])
                    table.append(text.split())  # Split line by spaces
        if table:
            tables.append(table)
    
    return tables

# Function to generate a CSV string from table data
def generate_csv(table_data):
    csv_output = io.StringIO()
    for row in table_data:
        csv_output.write(",".join(row) + "\n")
    return csv_output.getvalue()

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
st.title("PDF Text Extractor and Contextual Analysis")
st.write("Upload a PDF file to extract its text, clean it, and analyze content based on a custom term.")

# File uploader widget
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    st.write(f"File: {uploaded_file.name}")
    
    # Extract text from the uploaded PDF
    extracted_text = extract_text_from_pdf(uploaded_file)

    # Clean the extracted text
    cleaned_text = clean_text(extracted_text)

    # Input for custom term (e.g., "eligibility")
    custom_term = st.text_input("Enter a term to summarize references (e.g., 'eligibility')", "eligibility")

    # Generate dynamic question prompts
    dynamic_questions = generate_dynamic_questions(cleaned_text, custom_term)

    # Display dynamic questions
    st.subheader("Sample Questions Based on Your Text")
    for question in dynamic_questions:
        if st.button(question):
            response = generate_response_to_question(extracted_text, question, custom_term)
            st.write(f"Response: {response}")

    # Extract and display all contextual mentions of the custom term in the document
    context_data = extract_contextual_relationships(extracted_text, custom_term)
    st.subheader(f"Contextual Mentions of '{custom_term.capitalize()}'")
    
    if context_data:
        for entry in context_data:
            st.write(f"Sentence: {entry['sentence']}")
            if entry['related_terms']:
                st.write(f"Related Terms: {', '.join(entry['related_terms'])}")
    else:
        st.write(f"No mentions of '{custom_term}' found in the document.")

    # Full lines containing the custom term
    st.subheader(f"Full Lines Containing '{custom_term.capitalize()}'")
    full_lines = print_full_lines_with_term(extracted_text, custom_term, page_info={})  # Assuming `page_info` is provided
    st.write(full_lines)

    # List of related terms
    related_terms = extract_related_terms(extracted_text, custom_term)
    st.subheader(f"Related Terms to '{custom_term.capitalize()}'")
    if related_terms:
        st.write(f"Related terms found in the document: {', '.join(related_terms)}")
    else:
        st.write(f"No related terms found for '{custom_term}' in the document.")

    # Extract tables from the PDF
    tables = extract_tables_from_pdf(uploaded_file)
    
    if tables:
        st.subheader("Table Preview (First 3 Tables)")
        for i, table in enumerate(tables[:3]):
            st.write(f"Table {i + 1}:")
            st.write(table)
            
            # Generate CSV for the table
            csv_data = generate_csv(table)
            
            # Provide CSV download link
            st.download_button(
                label=f"Download Table {i + 1} as CSV",
                data=csv_data,
                file_name=f"table_{i + 1}.csv",
                mime="text/csv"
            )
    else:
        st.write("No tables found in the document.")
