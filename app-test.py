import re
import pandas as pd
import fitz  # PyMuPDF
import streamlit as st

# Define extraction configuration
terms_to_extract = {
    "Plan Name": {"pattern": r"Plan name:\s*(.*?)\n", "page_hint": "Plan Name/Effective Date"},
    "Trustee": {"pattern": r"Trustee:\s*(.*?)\n", "fallback": "Not explicitly mentioned"},
    "EIN": {"pattern": r"EIN:\s*(\d{2}-\d{7})", "page_hint": "EMPLOYER INFORMATION"},
    "Year End": {"pattern": r"fiscal year end:\s*(\d{2}/\d{2})", "page_hint": "Plan Year"},
    "Entity Type": {"pattern": r"entity type:\s*(.*?)\n", "page_hint": "EMPLOYER INFORMATION"},
    "Entity State": {"pattern": r"state:\s*([A-Z]{2})", "page_hint": "EMPLOYER INFORMATION"},
    "Is it a Safe Harbor": {
        "pattern": r"Safe harbor contributions are permitted.*?\n.*?\n\s*(Yes|No)",
        "fallback": "No",
    },
    "Vesting": {"pattern": r"Vesting Schedule.*?\n.*?\n\s*(.*?)\n", "page_hint": "VESTING"},
    "Profit Sharing Vesting": {
        "pattern": r"Non-Elective Contributions.*?Vesting Schedule.*?\n.*?\n\s*(.*?)\n",
        "page_hint": "VESTING",
    },
    "Elapsed Vesting": {"pattern": r"Elapsed Vesting.*?\s(True|False)", "fallback": "False"},
    "Plan Type": {"pattern": r"Plan Type.*?\s*(401\(k\))", "page_hint": "PLAN INFORMATION"},
    "Compensation Definition": {
        "pattern": r"Definition of Statutory Compensation.*?\s*(W-2 Compensation|Withholding|Section 415)",
        "page_hint": "Compensation",
    },
    "Deferral Change Frequency": {
        "pattern": r"Participants modify/start/stop Elective Deferrals.*?\n.*?\n\s*(.*?)\n",
        "page_hint": "CONTRIBUTIONS",
    },
    "Match Frequency": {
        "pattern": r"determining the amount of an allocation.*?\n.*?\n\s*(.*?)\n",
        "page_hint": "CONTRIBUTIONS",
    },
    "Entry Date": {
        "pattern": r"Entry Dates for Plan Participation.*?\n.*?\n\s*(.*?)\n",
        "page_hint": "Eligibility",
    },
    "Match Entry Date": {"pattern": r"Match Entry date.*?\n.*?\n\s*(.*?)\n", "page_hint": "Eligibility"},
    "Profit Share Entry Date": {
        "pattern": r"Profit share entry date.*?\n.*?\n\s*(.*?)\n",
        "page_hint": "Eligibility",
    },
    "Minimum Age": {"pattern": r"Age Requirement.*?\n.*?\n\s*(\d+)", "page_hint": "Eligibility"},
    "Match Minimum Age": {"pattern": r"Match Minimum age.*?\n.*?\n\s*(\d+)", "page_hint": "Eligibility"},
    "Profit Share Minimum Age": {
        "pattern": r"Profit Share Minimum Age.*?\n.*?\n\s*(\d+)",
        "page_hint": "Eligibility",
    },
}

# Function to extract text based on pattern and fallback mechanisms
def extract_terms_from_text(doc, patterns):
    results = []
    for term, config in patterns.items():
        extracted_value = "Not Found"
        page_number = "N/A"
        pattern = config.get("pattern", None)
        fallback = config.get("fallback", None)
        page_hint = config.get("page_hint", None)

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            if pattern:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    extracted_value = match.group(1).strip()
                    page_number = page_num
                    break
            # Check context or fallback if not found
            if page_hint and page_hint.lower() in page_text.lower():
                if fallback:
                    extracted_value = fallback
                    page_number = page_num
        # Add default fallback if nothing is found
        if extracted_value == "Not Found" and fallback:
            extracted_value = fallback
        results.append([term, extracted_value, page_number])
    return results

# PDF parsing and processing
def process_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    extracted_data = extract_terms_from_text(doc, terms_to_extract)
    return pd.DataFrame(extracted_data, columns=["Term", "Response", "Page Number"])

# Streamlit App Interface
def main():
    st.title("Dynamic PDF Information Extraction")
    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    if uploaded_file:
        with st.spinner("Processing the document..."):
            results_df = process_pdf(uploaded_file)
        st.success("Extraction complete!")
        st.subheader("Extracted Information")
        st.dataframe(results_df)
        st.download_button(
            label="Download Results as CSV",
            data=results_df.to_csv(index=False),
            file_name="extracted_terms.csv",
            mime="text/csv",
        )

if __name__ == "__main__":
    main()
