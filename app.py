import streamlit as st
import fitz  # PyMuPDF
import re
import math
from collections import Counter

# 1. Data Cleaning
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 2. Tokenization
def tokenize(text):
    return text.split()

# 3. Vectorization (Manual TF-IDF Implementation)
def compute_tfidf(text):
    # Tokenize and count term frequencies
    sentences = text.split('.')
    term_freq = [Counter(tokenize(sentence)) for sentence in sentences]
    term_set = set(word for sentence in term_freq for word in sentence)
    
    # Calculate term frequency-inverse document frequency (TF-IDF)
    tfidf_matrix = []
    num_sentences = len(sentences)
    
    for tf in term_freq:
        tfidf_vector = {}
        for term in term_set:
            tf_val = tf.get(term, 0)
            idf_val = math.log((num_sentences + 1) / (sum(1 for tf_sentence in term_freq if term in tf_sentence) + 1))
            tfidf_vector[term] = tf_val * idf_val
        tfidf_matrix.append(tfidf_vector)
    
    return tfidf_matrix, term_set

# 4. Cosine Similarity (Manual Implementation)
def cosine_similarity(vec1, vec2):
    # Dot product
    dot_product = sum(vec1.get(term, 0) * vec2.get(term, 0) for term in vec1.keys())
    
    # Magnitudes (L2 norms)
    magnitude1 = math.sqrt(sum(val ** 2 for val in vec1.values()))
    magnitude2 = math.sqrt(sum(val ** 2 for val in vec2.values()))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0  # Prevent division by zero
    
    return dot_product / (magnitude1 * magnitude2)

# 5. Calculate Similarity between Term and Sentences
def calculate_similarity(text, term):
    similarity_scores = []
    tfidf_matrix, terms = compute_tfidf(text)
    
    # Compute TF-IDF vector for the input term
    term_vec = Counter(tokenize(term))
    term_tfidf = {}
    for word in terms:
        term_tfidf[word] = term_vec.get(word, 0) * math.log((len(tfidf_matrix) + 1) / (sum(1 for sentence in tfidf_matrix if word in sentence) + 1))
    
    # Calculate similarity score for each sentence
    sentences = text.split('.')
    for idx, tfidf_vector in enumerate(tfidf_matrix):
        similarity = cosine_similarity(tfidf_vector, term_tfidf)
        similarity_scores.append((idx, similarity, sentences[idx]))
    
    # Sort sentences by similarity score in descending order
    similarity_scores.sort(key=lambda x: x[1], reverse=True)
    
    return similarity_scores

# 6. Extract Contextual Relationships using Similarity Scoring
def extract_contextual_relationships(text, term):
    similarity_scores = calculate_similarity(text, term)
    
    context_data = []
    for idx, score, sentence in similarity_scores:
        if score > 0.1:  # Only keep relevant sentences based on similarity threshold
            context_data.append({
                "sentence": sentence.strip(),
                "similarity_score": score
            })
    
    return context_data

# 7. Summarize Mentions of the User-Input Text
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

# 8. Generate Dynamic Questions
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

# 9. Generate Response to a Question
def generate_response_to_question(text, question, term):
    term = term.lower()
    context_data = extract_contextual_relationships(text, term)
    
    if "about" in question or "what" in question.lower():
        if context_data:
            response = f"The document discusses '{term}' in various contexts: "
            for entry in context_data:
                response += f"\n- In the sentence: '{entry['sentence']}', similarity score: {entry['similarity_score']:.2f}."
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

# 10. Function to Extract Text from PDF
def extract_text_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text += page.get_text("text")  # Standard text extraction
    
    return text

# 11. Function to Print Full Lines with the Term (No Page Info)
def print_full_lines_with_term(extracted_text, term):
    term = term.lower()
    full_lines_with_term = []
    
    lines = extracted_text.split('\n')
    for idx, line in enumerate(lines):
        if term in line.lower():
            full_line = line.replace(term, f"**_{term}_**")
            full_lines_with_term.append(f"{idx + 1}. {full_line}")  # Ordered list: 1., 2., 3.
    
    return "\n".join(full_lines_with_term)

# 12. Extract Related Terms
def extract_related_terms(text, term):
    term = term.lower()
    related_terms = set()
    
    words = text.split()
    for word in words:
        if term in word.lower() and word.lower() != term:
            related_terms.add(word)
    
    return list(related_terms)

# Main Streamlit App Interface
st.title("PDF Text Extractor and Contextual Analysis")
st.write("Upload a PDF file to extract its text, clean it, and analyze content based on a custom term.")

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
            st.write(f"Sentence: {entry['sentence']} - Similarity: {entry['similarity_score']:.2f}")
    else:
        st.write(f"No mentions of '{custom_term}' found in the document.")

    st.subheader(f"Full Lines Containing '{custom_term.capitalize()}'")
    full_lines = print_full_lines_with_term(extracted_text, custom_term)
    st.write(full_lines)

    related_terms = extract_related_terms(extracted_text, custom_term)
    st.subheader(f"Related Terms to '{custom_term.capitalize()}'")
    if related_terms:
        st.write(f"Related terms found in the document: {', '.join(related_terms)}")
    else:
        st.write(f"No related terms found for '{custom_term}' in the document.")
