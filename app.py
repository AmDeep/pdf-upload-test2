import streamlit as st
import subprocess  # process in the os
import os  # os process manipulation
import base64  # byte object into a pdf file
import camelot as cam  # extracting tables from PDFs
import fitz  # PyMuPDF
import re
from collections import Counter

# Install ghostscript once (used by Camelot)
@st.cache
def gh():
    """Install ghostscript on the linux machine"""
    proc = subprocess.Popen('apt-get install -y ghostscript', shell=True, stdin=None, stdout=open(os.devnull, "wb"), stderr=subprocess.STDOUT, executable="/bin/bash")
    proc.wait()

gh()

# 1. Data Cleaning (for text analysis)
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

# 3. Vectorization (Simple Bag of Words)
def vectorize(tokens):
    return Counter(tokens)

# 4. Extract Contextual Relationships (for text analysis)
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

# 5. Summarize Mentions of the User-Input Term (for text analysis)
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

# Extract tables from PDF (using Camelot)
def extract_tables_from_pdf(pdf_file, page_number):
    with open("input.pdf", "wb") as f:
        base64_pdf = base64.b64encode(pdf_file.read()).decode('utf-8')
        f.write(base64.b64decode(base64_pdf))

    tables = cam.read_pdf("input.pdf", pages=page_number, flavor='stream')
    return tables

# Extract text from PDF (for contextual analysis)
def extract_text_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text += page.get_text("text")
    
    return text

# Function to generate dynamic question prompts based on the extracted term
def generate_dynamic_questions(text, term):
    term = term.lower()
    
    # Extract contextual relationships
    context_data = extract_contextual_relationships(text, term)
    
    # Generate dynamic questions based on context
    questions = []
    if context_data:
        questions.append(f"What is mentioned about '{term}' in the document?")
        questions.append(f"Can you provide examples of '{term}' being discussed in the document?")
        
        # Check for policy, rules, or definitions
        if any("requirement" in sentence.lower() for sentence in [entry['sentence'] for entry in context_data]):
            questions.append(f"What requirements or rules are associated with '{term}'?")
        
        if any("defined" in sentence.lower() for sentence in [entry['sentence'] for entry in context_data]):
            questions.append(f"How is '{term}' defined in the document?")
        
        # Comparative questions if term appears in multiple contexts
        if len(context_data) > 1:
            questions.append(f"How does the discussion of '{term}' differ in various sections of the document?")
    
    return questions

# Function to generate contextual response to a question
def generate_response_to_question(text, question, term):
    term = term.lower()
    
    # Extract contextual relationships
    context_data = extract_contextual_relationships(text, term)
    
    # Identify question type and generate smart, context-aware responses
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
        return f"Across different sections, '{term}' is discussed from various perspectives, such as eligibility conditions, examples of qualifying factors, and eligibility rules."

    else:
        return f"The document offers a detailed exploration of '{term}', providing insight into its significance in relation to other policy terms."

# Streamlit interface
st.title("PDF Text Extractor and Table Extraction")
st.write("Upload a PDF file to extract its text, tables, and analyze content based on a custom term.")

# File uploader widget
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    st.write(f"File: {uploaded_file.name}")
    
    # Extract text from the uploaded PDF for textual analysis
    extracted_text = extract_text_from_pdf(uploaded_file)

    # Clean the extracted text
    cleaned_text = clean_text(extracted_text)

    # Input for custom term (e.g., "eligibility")
    custom_term = st.text_input("Enter a term to summarize references (e.g., 'eligibility')", "eligibility")

    # Generate dynamic question prompts
    dynamic_questions = generate_dynamic_questions(cleaned_text, custom_term)

    # Display dynamic questions for contextual analysis
    st.subheader("Sample Questions Based on Your Text")
    for question in dynamic_questions:
        if st.button(question):
            # Generate and display a response to the clicked question
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

    # Page number input for table extraction
    page_number = st.text_input("Enter the page number for table extraction", value=1)

    if page_number.isdigit():
        page_number = int(page_number)
        # Extract tables from the specified page
        tables = extract_tables_from_pdf(uploaded_file, page_number)

        # Display tables
        st.subheader(f"Extracted Tables from Page {page_number}")
        if len(tables) > 0:
            for i, table in enumerate(tables):
                st.write(f"Table {i + 1}:")
                st.dataframe(table.df)
        else:
            st.write(f"No tables found on page {page_number}.")
