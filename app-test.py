import re
import pandas as pd
from pypdf import PdfReader

# Define the terms to extract with respective patterns
terms_to_extract = {
    "Plan Name": r"Plan name:\s*(.*?)\n",
    "Trustee": r"Trustee:\s*(.*?)\n",
    "EIN": r"EIN:\s*(\d{2}-\d{7})",
    "Year End": r"fiscal year end:\s*(\d{2}/\d{2})",
    "Entity Type": r"entity type:\s*(.*?)\n",
    "Entity State": r"state:\s*([A-Z]{2})",
    "Is it a Safe Harbor": r"Safe harbor contributions are permitted.*?\n.*?\n\s*(Yes|No)",
    "Vesting": r"Vesting Schedule.*?\n.*?\n\s*(.*?)\n",
    "Profit Sharing Vesting": r"Non-Elective Contributions.*?Vesting Schedule.*?\n.*?\n\s*(.*?)\n",
    "Elapsed Vesting": r"Elapsed Vesting.*?\s(True|False)",
    "Plan Type": r"Plan Type.*?\s*(401\(k\))",
    "Compensation Definition": r"Definition of Statutory Compensation.*?\s*(W-2 Compensation|Withholding|Section 415)",
    "Deferral Change Frequency": r"Participants modify/start/stop Elective Deferrals.*?\n.*?\n\s*(.*?)\n",
    "Match Frequency": r"determining the amount of an allocation.*?\n.*?\n\s*(.*?)\n",
    "Entry Date": r"Entry Dates for Plan Participation.*?\n.*?\n\s*(.*?)\n",
    "Match Entry Date": r"Match Entry date.*?\n.*?\n\s*(.*?)\n",
    "Profit Share Entry Date": r"Profit share entry date.*?\n.*?\n\s*(.*?)\n",
    "Minimum Age": r"Age Requirement for Plan Participation.*?\n.*?\n\s*(\d+)",
    "Match Minimum Age": r"Match Minimum age.*?\n.*?\n\s*(\d+)",
    "Profit Share Minimum Age": r"Profit Share Minimum Age.*?\n.*?\n\s*(\d+)",
}

# Function to extract specific terms from text
def extract_terms_from_text(text, patterns):
    results = []
    for term, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            results.append([term, match.group(1).strip(), find_page_number(text, match.start())])
        else:
            results.append([term, "Not Found", ""])
    return results

# Helper function to find the page number for a matched term
def find_page_number(text, match_start):
    # Split the document into pages
    pages = text.split("\f")
    cumulative_index = 0
    for i, page in enumerate(pages):
        cumulative_index += len(page)
        if match_start < cumulative_index:
            return i + 1
    return "Unknown"

# Streamlit interface
def main():
    st.title("PDF Information Extraction")
    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

    if uploaded_file is not None:
        # Load PDF
        pdf_reader = PdfReader(uploaded_file)
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text()

        # Extract terms
        extracted_data = extract_terms_from_text(full_text, terms_to_extract)

        # Display the results
        df = pd.DataFrame(extracted_data, columns=["Term", "Response", "Page Number"])
        st.subheader("Extracted Information")
        st.dataframe(df)

if __name__ == "__main__":
    main()
