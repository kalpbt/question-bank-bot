import os
import json
from dotenv import load_dotenv
import openai
import logging
import time

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logger to log to both file and console
logger = logging.getLogger("openai_utils")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

# File handler
file_handler = logging.FileHandler(os.path.join("logs", "openai_utils.log"))
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = ""
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_API_BASE
logger.info("OpenAI API key and base URL loaded successfully.")
logger.info(f"Using KEY: {OPENAI_API_KEY[:40]}... and MODEL: {OPENAI_MODEL}")

def get_chapter_files(chapter_dir="chapters"):
    files = [f for f in os.listdir(chapter_dir) if f.endswith(".json")]
    files.sort()
    return files

def load_chapter_content(chapter_files, chapter_dir="chapters"):
    chapters = []
    for file in chapter_files:
        with open(os.path.join(chapter_dir, file), "r", encoding="utf-8") as f:
            data = json.load(f)
            chapters.append({
                "file": file,
                "name": data.get("chapter_name", file),
                "content": "\n\n".join(page["content"] for page in data.get("pages", []))
            })
    return chapters

def build_prompt(chapter_contents, chapter_question_counts, difficulty, domains):
    """
    chapter_contents: list of dicts, each with 'file', 'name', and 'content'
    chapter_question_counts: dict mapping chapter file to dict with 'mcq', 'tf', 'short'
    domains: list of selected domains
    difficulty: string, passed from app.py per question bank
    """
    prompt = (
        f"You are to generate a question bank from the following chapters.\n"
        f"For each chapter, generate the specified number of each question type as listed below.\n"
        f"Use the following cognitive domains for random assignment per question: {', '.join(domains)}.\n"
        f"For each question, randomly select one cognitive domain from this list and clearly mention the domain beside each question as [Domain: ...].\n"
        f"Format the output as shown below for each chapter.\n\n"
        f"Chapters and required question counts per type:\n"
    )
    for chapter in chapter_contents:
        file = chapter['file']
        counts = chapter_question_counts.get(file, {"mcq": 0, "tf": 0, "short": 0})
        if counts["mcq"] > 0 or counts["tf"] > 0 or counts["short"] > 0:
            prompt += (
                f"- {chapter['name']}:\n"
                f"    MCQ: {counts['mcq']}\n"
                f"    True/False: {counts['tf']}\n"
                f"    Short Answer: {counts['short']}\n"
            )
    prompt += "\nContent for each chapter:\n"
    for chapter in chapter_contents:
        prompt += f"\nChapter: {chapter['name']}\n{chapter['content']}\n"
    prompt += (
        f"\nAll questions should be at the '{difficulty}' difficulty level.\n"
        "For each chapter, generate the questions in this format:\n"
        "MCQ:\nQ1. ... [Domain: ...]\nA. ...\nB. ...\nC. ...\nD. ...\nAnswer: ...\n\n"
        "True/False:\nQ1. ... [Domain: ...] (True/False)\nAnswer: ...\n\n"
        "Short Answer:\nQ1. ... [Domain: ...]\nAnswer: ...\n"
        "\nMake sure the domain is randomly assigned per question and shown beside each question.\n"
        "Do not generate more than the specified number of each question type per chapter."
    )
    return prompt

def call_openai(
    prompt,
    model=OPENAI_MODEL,
    system_prompt=(
        "You are an instructor that generates question banks from the provided book content (from a PDF). "
        "You take user input such as cognitive domains, difficulty levels, type of questions, and chapter selection. "
        "Generate questions and answers based on these inputs, ensuring each question is relevant to the specified chapter and domain."
    )
):
    client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1024,
            temperature=0.7,
        )
        logger.info("OpenAI API call successful.")
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        raise

def split_text(text, max_words=150):
    """
    Splits text into chunks of approximately max_words (words, as a proxy).
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i+max_words])
        chunks.append(chunk)
    return chunks

def split_text_with_overlap(text, max_tokens=1000, overlap=200):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+max_tokens])
        chunks.append(chunk)
        i += max_tokens - overlap  # move forward, but keep some overlap
    return chunks

def generate_questions_per_chapter(
    chapter_contents,
    chapter_question_counts,
    mcq,
    tf,
    short,
    difficulty,
    domains
):
    """
    Calls OpenAI for each chapter (or chunk) individually to avoid token limits.
    Returns a dict mapping chapter file to generated questions.
    """
    results = {}
    for chapter in chapter_contents:
        file = chapter['file']
        counts = chapter_question_counts.get(file, {"mcq": 0, "tf": 0, "short": 0})
        if counts["mcq"] == 0 and counts["tf"] == 0 and counts["short"] == 0:
            continue

        # Split chapter content if too large
        chapter_chunks = split_text(chapter['content'], max_words=150)
        chapter_results = []
        for idx, chunk in enumerate(chapter_chunks):
            single_chapter_prompt = (
                f"You are to generate a question bank from the following chapter chunk.\n"
                f"Generate the specified number of each question type as listed below.\n"
                f"Use the following cognitive domains for random assignment per question: {', '.join(domains)}.\n"
                f"For each question, randomly select one cognitive domain from this list and clearly mention the domain beside each question as [Domain: ...].\n"
                f"Format the output as shown below.\n\n"
                f"Chapter and required question counts per type:\n"
                f"- {chapter['name']} (chunk {idx+1} of {len(chapter_chunks)}):\n"
                f"    MCQ: {counts['mcq']}\n"
                f"    True/False: {counts['tf']}\n"
                f"    Short Answer: {counts['short']}\n"
                f"\nContent for the chapter chunk:\n"
                f"{chunk}\n"
                f"\nAll questions should be at the '{difficulty}' difficulty level.\n"
                "Generate the questions in this format:\n"
                "MCQ:\nQ1. ... [Domain: ...]\nA. ...\nB. ...\nC. ...\nD. ...\nAnswer: ...\n\n"
                "True/False:\nQ1. ... [Domain: ...] (True/False)\nAnswer: ...\n\n"
                "Short Answer:\nQ1. ... [Domain: ...]\nAnswer: ...\n"
                "\nMake sure the domain is randomly assigned per question and shown beside each question.\n"
                "Do not generate more than the specified number of each question type."
            )
            logger.info(f"Prompt length (chars): {len(single_chapter_prompt)}")
            logger.info(f"Prompt preview: {single_chapter_prompt[:500]}")  # Log first 500 chars
            try:
                result = call_openai(
                    prompt=single_chapter_prompt,
                    model=OPENAI_MODEL
                )
                chapter_results.append(result)
                logger.info(f"Questions generated for chapter: {chapter['name']} chunk {idx+1}")
                time.sleep(2)  # <-- Add a delay (2 seconds) between requests
            except Exception as e:
                logger.error(f"Failed to generate questions for chapter {chapter['name']} chunk {idx+1}: {e}")
                chapter_results.append(None)
        results[file] = chapter_results
    return results