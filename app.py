import os
from dotenv import load_dotenv
from PIL import Image
import streamlit as st
import google.generativeai as genai
import json

# ========================================
# Load API key
# ========================================
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ========================================
# Initialize Gemini 2.5 Flash (multimodal)
# ========================================
model = genai.GenerativeModel("gemini-2.5-flash")

# ========================================
# Helper: ask Gemini about an image
# ========================================
def get_gemini_response(image_path, question):
    """
    Send image + question to Gemini and safely return text output or JSON.
    """
    with open(image_path, "rb") as img_file:
        image_bytes = img_file.read()

    response = model.generate_content(
        [question, {"mime_type": "image/jpeg", "data": image_bytes}],
        generation_config={"max_output_tokens": 1024},
    )

    if response.candidates:
        content = response.candidates[0].content  # single Content object
        if hasattr(content, "text") and content.text:
            text = content.text.strip()
            # Try parsing JSON if possible
            try:
                return json.loads(text)
            except:
                return text

    return "⚠️ No valid text returned. Try a simpler question."

# ========================================
# Streamlit UI
# ========================================
st.set_page_config(page_title="Invoice Extractor", page_icon="📄", layout="centered")
st.title("📄 Invoice Extractor using Google Gemini 2.5 Flash")
st.caption("Upload an invoice and ask any question — powered by Gemini 2.5 Flash.")

# Question input
question = st.text_input(
    "Enter your question (e.g., 'What is the invoice number?')", key="question"
)

# File uploader
uploaded_file = st.file_uploader("Upload invoice image", type=["jpg", "jpeg", "png"])

# JSON extraction checkbox
extract_json = st.checkbox("Structured JSON extraction (invoice fields)")

# Process button
if st.button("Extract Information"):
    if uploaded_file and question.strip():
        # Save uploaded image temporarily
        temp_path = "temp_invoice_image.jpg"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Display uploaded image
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Invoice", use_column_width=True)

        # Modify question for structured extraction if checkbox is checked
        if extract_json:
            question = f"""
            Extract the following fields from this invoice:
            - Invoice Number
            - Date
            - Vendor Name
            - Total Amount
            - Tax Amount
            Return the answer in strict JSON format.
            Original question: {question}
            """

        # Query Gemini
        with st.spinner("Analyzing invoice with Gemini..."):
            try:
                answer = get_gemini_response(temp_path, question)
                st.success("✅ Extracted Information:")

                # Display JSON or text
                if isinstance(answer, dict):
                    st.json(answer)
                else:
                    st.write(answer)
            except Exception as e:
                st.error(f"❌ Error: {e}")

        # Clean up temporary file
        os.remove(temp_path)
    else:
        st.warning("Please upload an image and enter a question first.")

# Footer
st.markdown("---")
st.markdown("Built with ❤️ using Google Gemini API + Streamlit")
