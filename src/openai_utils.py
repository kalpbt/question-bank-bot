import os
import json
from dotenv import load_dotenv
import openai
import logging

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join("logs", "openai_utils.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_API_BASE

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

def build_prompt(chapter_contents, num_mcq, num_tf, num_short, difficulty, domain):
    prompt = (
        f"Generate a question bank from the following content. "
        f"Difficulty: {difficulty}. Cognitive domain: {domain}.\n"
        f"Generate {num_mcq} MCQs, {num_tf} True/False, and {num_short} Short Answer questions.\n\n"
        f"Content:\n{chapter_contents}\n\n"
        "Format the output as:\n"
        "MCQ:\nQ1. ...\nA. ...\nB. ...\nC. ...\nD. ...\nAnswer: ...\n\n"
        "True/False:\nQ1. ... (True/False)\nAnswer: ...\n\n"
        "Short Answer:\nQ1. ...\nAnswer: ...\n"
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
            max_tokens=2048,
            temperature=0.7,
        )
        logging.info("OpenAI API call successful.")
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API call failed: {e}")
        raise