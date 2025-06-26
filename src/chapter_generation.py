import os
import json
import re
import logging

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=os.path.join("logs", "chapter_generation.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

def extract_chapter_info(text):
    """
    Extract chapter number and chapter name from the page content.
    Looks for patterns like '1 — Chapter Name', '2 - Another Name', etc.
    Returns (chapter_number, chapter_title) or (None, None) if not found.
    """
    match = re.search(r'\b(\d+)\s*[—-]\s*([^\n]+)', text)
    if match:
        chapter_number = match.group(1)
        chapter_title = match.group(2).strip()
        return chapter_number, chapter_title
    return None, None

def extract_page_number(text):
    """
    Extract the last number in the text as the page number.
    """
    match = re.search(r'(\d+)\s*$', text)
    return match.group(1) if match else None

def generate_chapterwise_json(pagewise_json_path, output_folder='chapters'):
    import shutil

    with open(pagewise_json_path, 'r', encoding='utf-8') as f:
        pages = json.load(f)

    os.makedirs(output_folder, exist_ok=True)

    def split_by_page_number_reset():
        chapters = []
        current_chapter_pages = []
        current_chapter_title = None

        for idx, page in enumerate(pages):
            text = page['content']
            page_number = extract_page_number(text)
            chapter_number, chapter_title = extract_chapter_info(text)

            if page_number == "1" and current_chapter_pages:
                chapters.append({
                    "chapter_name": current_chapter_title or f"Chapter {len(chapters)+1}",
                    "pages": current_chapter_pages
                })
                current_chapter_pages = []

            if chapter_number and chapter_title:
                current_chapter_title = f"{chapter_number}: {chapter_title}"

            current_chapter_pages.append({
                'page_number': page_number,
                'content': text
            })

        if current_chapter_pages:
            chapters.append({
                "chapter_name": current_chapter_title or f"Chapter {len(chapters)+1}",
                "pages": current_chapter_pages
            })
        return chapters

    def split_by_chapter_heading():
        chapters = []
        current_chapter_pages = []
        current_chapter_title = None

        for idx, page in enumerate(pages):
            text = page['content']
            page_number = extract_page_number(text)
            first_5_lines = "\n".join(text.splitlines()[:5])
            chapter_number, chapter_title = extract_chapter_info(first_5_lines)

            if chapter_number and chapter_title:
                if current_chapter_pages:
                    chapters.append({
                        "chapter_name": current_chapter_title or f"Chapter {len(chapters)+1}",
                        "pages": current_chapter_pages
                    })
                    current_chapter_pages = []
                current_chapter_title = f"{chapter_number}: {chapter_title}"

            current_chapter_pages.append({
                'page_number': page_number,
                'content': text
            })

        if current_chapter_pages:
            chapters.append({
                "chapter_name": current_chapter_title or f"Chapter {len(chapters)+1}",
                "pages": current_chapter_pages
            })
        return chapters

    chapters = split_by_page_number_reset()
    if len(chapters) <= 1:
        chapters = split_by_chapter_heading()

    for filename in os.listdir(output_folder):
        file_path = os.path.join(output_folder, filename)
        if os.path.isfile(file_path):
            os.unlink(file_path)

    for idx, chapter in enumerate(chapters, 1):
        chapter_file = os.path.join(output_folder, f'chapter_{idx}.json')
        with open(chapter_file, 'w', encoding='utf-8') as f:
            json.dump(chapter, f, ensure_ascii=False, indent=2)

    logging.info(f"Chapterwise JSON files created in '{output_folder}' folder.")

if __name__ == "__main__":
    generate_chapterwise_json('data/pagewise_content.json')