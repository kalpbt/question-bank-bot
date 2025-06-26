import re
import pandas as pd
import pytesseract
from pdf2image import convert_from_path
import json
import logging
import os
import pdfplumber

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join("logs", "extraction.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def extract_page_number_from_text(text):
    """
    Check the last 5 lines of text for a standalone number (likely page number).
    Returns the number if found, else None.
    """
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    for line in reversed(lines[-5:]):
        match = re.match(r'^(\d{1,4})$', line)
        if match:
            return int(match.group(1))
    return None

def extract_text_from_pdf(pdf_path):
    logging.info(f"Starting text extraction from PDF: {pdf_path}")
    images = convert_from_path(pdf_path)
    logging.info(f"Converted PDF to {len(images)} images/pages.")
    pages = []
    assigned_page_num = 1
    for idx, image in enumerate(images):
        logging.info(f"Processing page {idx + 1}")
        text = pytesseract.image_to_string(image, lang='eng')
        detected_page_num = extract_page_number_from_text(text)
        page_number = detected_page_num if detected_page_num is not None else assigned_page_num
        pages.append({
            'page_number': page_number,
            'content': text
        })
        assigned_page_num += 1
    logging.info(f"Extraction complete. Extracted {len(pages)} pages.")
    return pages


if __name__ == "__main__":
    os.makedirs("uploaded_data", exist_ok=True)
    os.makedirs("extracted_data", exist_ok=True)

    pdf_files = []
    for folder in ["data", "uploaded_data"]:
        if os.path.exists(folder):
            pdf_files += [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".pdf")]

    if not pdf_files:
        print("No PDF files found in 'data' or 'uploaded_data' folders.")
    else:
        print("Available PDFs:")
        for idx, pdf in enumerate(pdf_files, 1):
            print(f"{idx}. {pdf}")

        choice = input("Enter the number of the PDF to extract (or press Enter for first): ").strip()
        try:
            idx = int(choice) - 1 if choice else 0
            pdf_path = pdf_files[idx]
        except Exception:
            print("Invalid selection. Exiting.")
            exit(1)

        print(f"Extracting text from: {pdf_path}")

        # Always use OCR extraction
        pages = extract_text_from_pdf(pdf_path)

        print("Detected page numbers:")
        for i, page in enumerate(pages, 1):
            print(f"Page {i}: Detected page number = {page['page_number']}")

        # Save detected page numbers and content in JSON
        pagewise_content = []
        for page in pages:
            pagewise_content.append({
                "page_number": page['page_number'],
                "content": page['content']
            })

        # Dynamically set output directory based on input PDF location
        output_dir = os.path.dirname(pdf_path)
        out_file = os.path.join(output_dir, "pagewise_content.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(pagewise_content, f, ensure_ascii=False, indent=2)
        print(f"Extraction complete. Pages saved to {out_file}.")
