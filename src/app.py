import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import os
import json
import logging
import time
import tiktoken  # pip install tiktoken

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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s    ')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

st.title("Custom Question Bank Generator")
logger.info("App started.")

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

# Use session_state to persist confirmation
if "confirmed" not in st.session_state:
    st.session_state.confirmed = False

if not st.session_state.confirmed:
    if st.button("Confirm number of question banks"):
        st.session_state.confirmed = True

if st.session_state.confirmed:
    # Step 1: PDF selection/upload
    default_pdf = os.path.join("data", "book.pdf")
    pdf_files = [f for f in os.listdir("data") if f.endswith(".pdf")]
    logging.info(f"PDF files found: {pdf_files}")

    pdf_path = os.path.join("data", pdf_choice)
    is_default = (pdf_path == default_pdf)
    logging.info(f"Using default PDF: {pdf_path}, is_default={is_default}")
    chapters_folder = "chapters"

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

        # st.markdown("### Select number of questions for each chapter:")
        # chapter_question_counts = {}
        # for idx, file in enumerate(chapter_files):
        #     # Try to get the chapter name from the JSON, fallback to file name
        #     with open(os.path.join(chapters_folder, file), "r", encoding="utf-8") as f:
        #         data = json.load(f)
        #         chapter_display = data.get("chapter_name", file)
        #     label = f'select number of questions from chapter: "{chapter_display}"'
        #     chapter_question_counts[file] = st.number_input(
        #         label,
        #         min_value=0,
        #         max_value=20,
        #         value=0,
        #         step=1,
        #         key=f"num_questions_{file}"
        #     )

        # # Only include chapters with at least 1 question selected
        # selected_chapters = [file for file, count in chapter_question_counts.items() if count > 0]
        # logging.info(f"Chapters selected: {selected_chapters}")

        # Difficulty per question bank
        st.markdown("### Select difficulty per question bank:")
        difficulties = []
        num_per_row = 5
        for row_start in range(0, num_question_banks, num_per_row):
            cols = st.columns(num_per_row)
            for col_idx in range(num_per_row):
                qb_idx = row_start + col_idx
                if qb_idx < num_question_banks:
                    with cols[col_idx]:
                        diff = st.selectbox(
                            f"{qb_idx+1}",
                            ["Easy", "Medium", "Hard"],
                            key=f"difficulty_qb_{qb_idx}"
                        )
                        difficulties.append(diff)
                else:
                    with cols[col_idx]:
                        st.empty()

        domain = st.multiselect(
            "Select cognitive domain(s):",
            ["Knowledge", "Comprehension", "Application", "Analysis", "Evaluation"]    
        )

        st.markdown("### Select number of each question type for each chapter:")
        chapter_question_counts = {}
        for idx, file in enumerate(chapter_files):
            with open(os.path.join(chapters_folder, file), "r", encoding="utf-8") as f:
                data = json.load(f)
                chapter_display = data.get("chapter_name", file)
            st.markdown(f'**{chapter_display}**')
            col1, col2, col3 = st.columns(3)
            with col1:
                mcq = st.number_input(
                    f"MCQ's",
                    min_value=0,
                    max_value=20,
                    value=0,
                    step=1,
                    key=f"mcq_{file}"
                )
            with col2:
                tf = st.number_input(
                    f"True/False's",
                    min_value=0,
                    max_value=20,
                    value=0,
                    step=1,
                    key=f"tf_{file}"
                )
            with col3:
                short = st.number_input(
                    f"Short Answers",
                    min_value=0,
                    max_value=20,
                    value=0,
                    step=1,
                    key=f"short_{file}"
                )
            chapter_question_counts[file] = {
                "mcq": mcq,
                "tf": tf,
                "short": short
            }

        # Only include chapters with at least 1 question selected
        selected_chapters = [
            file for file, counts in chapter_question_counts.items()
            if counts["mcq"] > 0 or counts["tf"] > 0 or counts["short"] > 0
        ]
        logging.info(f"Chapters selected: {selected_chapters}")

        def get_chunks_with_context(text, max_tokens=1000, overlap=200):
            """Split text into overlapping chunks, including previous paragraph for context."""
            words = text.split()
            chunks = []
            i = 0
            prev_paragraph = ""
            while i < len(words):
                chunk_words = words[i:i+max_tokens]
                chunk_text = " ".join(chunk_words)
                # Add previous paragraph for context if not the first chunk
                if prev_paragraph:
                    chunk_text = prev_paragraph + "\n\n" + chunk_text
                # Save last paragraph for next chunk's context
                paragraphs = chunk_text.split("\n\n")
                prev_paragraph = paragraphs[-1] if paragraphs else ""
                chunks.append(chunk_text)
                i += max_tokens - overlap
            return chunks

        def num_tokens_from_string(string: str, model_name: str = "gpt-4o"):
            encoding = tiktoken.encoding_for_model(model_name)
            return len(encoding.encode(string))

        MAX_TOKENS_PER_CHAPTER = 25000  # adjust as needed 

        if "qb_results" not in st.session_state:
            st.session_state.qb_results = None

        # Store chapters in session_state to avoid reloading for each QB
        if "loaded_chapters" not in st.session_state or st.session_state.get("loaded_chapters_selected") != selected_chapters:
            st.session_state.loaded_chapters = load_chapter_content(selected_chapters, chapter_dir=chapters_folder)
            st.session_state.loaded_chapters_selected = selected_chapters.copy()

        if st.button("Generate Question Bank(s)"):
            logging.info("Generate Question Bank button clicked.")
            if not selected_chapters:
                st.warning("Please select at least one chapter with at least one question.")
                logging.warning("No chapters selected.")
            else:
                chapters = st.session_state.loaded_chapters
                logging.info(f"Loaded chapter content for: {selected_chapters}")
                qb_results = []
                qb_placeholders = []
                for i in range(num_question_banks):
                    qb_placeholder = st.empty()
                    qb_placeholders.append(qb_placeholder)
                    qb_results.append("")  # Initialize with empty string

                for i in range(num_question_banks):
                    qb_text = ""
                    for chapter_idx, chapter in enumerate(chapters):
                        file = chapter['file']
                        chapter_counts = {file: chapter_question_counts[file]}
                        chapter_tokens = num_tokens_from_string(chapter['content'])
                        if chapter_tokens > MAX_TOKENS_PER_CHAPTER:
                            st.warning(f"Chapter '{chapter['name']}' is too large ({chapter_tokens} tokens). Splitting into chunks.")
                            continue  # or handle chunking as before
                        chapter_prompt = build_prompt(
                            [{"file": file, "name": chapter['name'], "content": chapter['content']}],
                            chapter_counts,
                            difficulties[i],
                            domain
                        )
                        logging.info(f"Prompt built for OpenAI (QB {i+1}, Chapter: {chapter['name']}): {chapter_prompt[:100]}...")
                        try:
                            questions = call_openai(chapter_prompt)
                            qb_text += f"--- {chapter['name']} ---\n{questions}\n\n"
                            logging.info(f"Questions for chapter {chapter['name']} (QB {i+1}) generated.")
                            # Update the placeholder with current questions
                            qb_placeholders[i].markdown(f"### Question Bank {i+1}\n```\n{qb_text}\n```")
                            time.sleep(60)  # Wait 60 seconds before next chapter to avoid rate limits
                        except Exception as e:
                            st.error(f"Error in QB {i+1}, chapter {chapter['name']}: {e}")
                            logging.error(f"Error during question generation for QB {i+1}, chapter {chapter['name']}: {e}")
                        if chapter_idx < len(chapters) - 1:
                            logging.info(f"Waiting 60 seconds before next chapter.")
                            time.sleep(60)
                    qb_results[i] = qb_text
                st.session_state.qb_results = qb_results
                st.success("All question banks generated! Download buttons are now available below.")

    # Show download buttons only if all QBs are generated
    if st.session_state.qb_results:
        for i, qb_text in enumerate(st.session_state.qb_results):
            st.markdown(f"## Question Bank {i+1}")
            st.text_area(
                f"Generated Questions for Question Bank {i+1}",
                qb_text,
                height=400,
                key=f"qb_{i}_text"
            )
            st.download_button(
                label=f"Download Question Bank {i+1} as .txt",
                data=qb_text,
                file_name=f"question_bank_{i+1}.txt",
                mime="text/plain",
                key=f"qb_{i}_download"
            )
    else:
        st.info("Please extract chapters from a PDF first (only needed for uploaded PDFs).")
        logging.info("No chapters found. Prompted user to extract chapters.")

