import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import os
import json
import logging

from src.chapter_generation import generate_chapterwise_json
from src.openai_utils import (
    get_chapter_files,
    load_chapter_content,
    build_prompt,
    call_openai,
)
from src.text_extraction import extract_text_from_pdf

# Ensure logs and uploaded_data directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("uploaded_data", exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join("logs", "app.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

st.title("Custom Question Bank Generator")
logging.info("App started.")

MAX_QUESTION_BANKS = 20

num_question_banks = st.number_input(
    "Enter the number of question banks required:",
    min_value=1,
    max_value=MAX_QUESTION_BANKS,
    value=1,
    step=1
)
if num_question_banks > MAX_QUESTION_BANKS:
    st.warning(f"Maximum allowed is {MAX_QUESTION_BANKS}. Resetting to {MAX_QUESTION_BANKS}.")
    num_question_banks = MAX_QUESTION_BANKS

logging.info(f"Number of question banks required: {num_question_banks}")

# Show only the PDF name, no selection
pdf_choice = "book.pdf"
st.markdown(f'**PDF:** "{pdf_choice}"')
logging.info(f"PDF set to: {pdf_choice}")

# Only show the rest of the UI if a valid number is entered
if num_question_banks:
    # Step 1: PDF selection/upload
    default_pdf = os.path.join("data", "book.pdf")
    pdf_files = [f for f in os.listdir("data") if f.endswith(".pdf")]
    logging.info(f"PDF files found: {pdf_files}")

    pdf_path = os.path.join("data", pdf_choice)
    is_default = (pdf_path == default_pdf)
    logging.info(f"Using default PDF: {pdf_path}, is_default={is_default}")
    chapters_folder = "chapters"

    # Step 2: Select the number of Question Banks to generate
    num_question_banks = st.number_input("Number of Question Banks to generate:", min_value=1, max_value=5, value=1)

    # Only show the extraction/generation button if a new PDF is uploaded
    if not is_default:
        if st.button("Extract & Generate Chapters"):
            logging.info("Extract & Generate Chapters button clicked.")
            with st.spinner("Extracting text and generating chapters..."):
                # Extract text and save pagewise content in uploaded_data
                pagewise_content = extract_text_from_pdf(pdf_path)
                uploaded_json_path = os.path.join(
                    "uploaded_data", f"{os.path.splitext(pdf_choice)[0]}_pagewise_content.json"
                )
                with open(uploaded_json_path, "w", encoding="utf-8") as f:
                    json.dump(pagewise_content, f, ensure_ascii=False, indent=2)
                logging.info(f"Pagewise content saved to {uploaded_json_path}.")
                # Generate chapters in chapters_generated/book-x/
                os.makedirs(chapters_folder, exist_ok=True)
                generate_chapterwise_json(uploaded_json_path, output_folder=chapters_folder)
                logging.info(f"Chapters generated in {chapters_folder}.")
                st.success("Chapters generated from PDF!")

    # Step 3: Chapter and question selection (only if chapters exist)
    if os.path.exists(chapters_folder) and len(os.listdir(chapters_folder)) > 0:
        chapter_files = get_chapter_files(chapter_dir=chapters_folder)
        logging.info(f"Chapter files found: {chapter_files}")
        chapter_names = []
        for file in chapter_files:
            with open(os.path.join(chapters_folder, file), "r", encoding="utf-8") as f:
                data = json.load(f)
                chapter_names.append(data.get("chapter_name", file))

        selected_chapters = st.multiselect(
            "Select chapter(s) for question generation:",
            options=chapter_files,
            format_func=lambda x: chapter_names[chapter_files.index(x)]
        )
        logging.info(f"Chapters selected: {selected_chapters}")

        difficulty = st.selectbox("Select difficulty:", ["Easy", "Medium", "Hard"])
        domain = st.multiselect(
            "Select cognitive domain(s):",
            ["Knowledge", "Comprehension", "Application", "Analysis", "Evaluation"]    
        )
        num_mcq = st.number_input("Number of MCQs:", min_value=0, max_value=20, value=5)
        num_tf = st.number_input("Number of True/False questions:", min_value=0, max_value=20, value=3)
        num_short = st.number_input("Number of Short Answer questions:", min_value=0, max_value=20, value=2)

        if st.button("Generate Question Bank"):
            logging.info("Generate Question Bank button clicked.")
            if not selected_chapters:
                st.warning("Please select at least one chapter.")
                logging.warning("No chapters selected.")
            elif num_mcq + num_tf + num_short == 0:
                st.warning("Please select at least one question.")
                logging.warning("No questions selected.")
            else:
                with st.spinner("Generating questions..."):
                    chapters = load_chapter_content(selected_chapters, chapter_dir=chapters_folder)
                    logging.info(f"Loaded chapter content for: {selected_chapters}")
                    combined_content = "\n\n".join([c["content"] for c in chapters])
                    domain_str = ", ".join(domain) if isinstance(domain, list) else domain
                    prompt = build_prompt(
                        combined_content, num_mcq, num_tf, num_short, difficulty, domain_str
                    )
                    logging.info(f"Prompt built for OpenAI: {prompt[:100]}...")  # Log first 100 chars
                    try:
                        questions = call_openai(prompt)
                        st.success("Question bank generated!")
                        st.text_area("Generated Question Bank", questions, height=400)
                        st.download_button(
                            label="Download as .txt",
                            data=questions,
                            file_name="question_bank.txt",
                            mime="text/plain"
                        )
                        logging.info("Question bank generated and displayed.")
                    except Exception as e:
                        st.error(f"Error: {e}")
                        logging.error(f"Error during question generation: {e}")
    else:
        st.info("Please extract chapters from a PDF first (only needed for uploaded PDFs).")
        logging.info("No chapters found. Prompted user to extract chapters.")

