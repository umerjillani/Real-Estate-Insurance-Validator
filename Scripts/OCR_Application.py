import os
import json
import fitz  # PyMuPDF
import pytesseract
import openai
import re
from PIL import Image
from dotenv import load_dotenv
import logging
from contextlib import contextmanager
import tempfile
from tenacity import retry, stop_after_attempt, wait_exponential
import subprocess

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logger.error("OPENAI_API_KEY is not set in the environment.")
    raise ValueError("OPENAI_API_KEY is required.")

# Validate Tesseract installation
try:
    subprocess.run(["tesseract", "--version"], capture_output=True, check=True)
except subprocess.CalledProcessError:
    logger.error("Tesseract OCR is not installed or not found in PATH.")
    raise EnvironmentError("Tesseract OCR is required. Install it using your package manager (e.g., `apt-get install tesseract-ocr`).")

@contextmanager
def temp_image_file():
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)  # close the file descriptor immediately so it can be written later
    try:
        yield path
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def process_application(pdf_path, output_dir="JSONs", zoom=4, save_text=False, model="gpt-4o", temperature=0, clean_non_ascii=False):
    """
    Process a PDF file to extract text using OCR, convert to JSON using OpenAI, and save results.
    
    Args:
        pdf_path (str): Path to the input PDF file.
        output_dir (str): Directory to save output files.
        zoom (float): Zoom factor for PDF rendering.
        save_text (bool): Whether to save extracted OCR text.
        model (str): OpenAI model to use (e.g., 'gpt-4o').
        temperature (float): Temperature for OpenAI API call.
        clean_non_ascii (bool): Whether to remove non-ASCII characters from text.
    
    Returns:
        dict: Paths to output files and extracted data.
    """
    # Validate inputs
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    if not os.access(output_dir, os.W_OK):
        logger.error(f"No write permission for output directory: {output_dir}")
        raise PermissionError(f"No write permission for output directory: {output_dir}")

    os.makedirs(output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    json_output_path = os.path.join(output_dir, base_name + ".json")
    text_output_path = os.path.join(output_dir, base_name + "_ocr.txt") if save_text else ""
    raw_response_path = os.path.join(output_dir, base_name + "_raw.txt")

    # Process PDF
    try:
        doc = fitz.open(pdf_path)
    except fitz.FitzError as e:
        logger.error(f"Failed to open PDF: {str(e)}")
        raise

    all_text = ""
    for page_num in range(len(doc)):
        try:
            page = doc.load_page(page_num)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            with temp_image_file() as temp_img_path:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.save(temp_img_path, format="PNG")
                text = pytesseract.image_to_string(img)
                all_text += text + "\n"
        except Exception as e:
            logger.error(f"Failed to process page {page_num + 1}: {str(e)}")
            all_text += f"[Error on page {page_num + 1}: {str(e)}]\n"

    if clean_non_ascii:
        all_text = re.sub(r'[^\x00-\x7F]+', ' ', all_text)

    if save_text:
        try:
            with open(text_output_path, "w", encoding="utf-8") as f:
                f.write(all_text)
            logger.info(f"Saved OCR text to: {text_output_path}")
        except IOError as e:
            logger.error(f"Failed to save OCR text to {text_output_path}: {str(e)}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def call_openai_api(text):
        return openai.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Extract all possible key-value pairs from the input text. Fill the missing filed with empty string, don't miss any key, and return a valid JSON object." 
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=temperature
        )

    def clean_response(response_text):
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text.removeprefix("```json").removesuffix("```").strip()
        elif response_text.startswith("```"):
            response_text = response_text.removeprefix("```").removesuffix("```").strip()
        elif response_text.lower().startswith("json"):
            response_text = response_text[4:].strip()
        return response_text

    try:
        response = call_openai_api(all_text)
        if not response.choices or not hasattr(response.choices[0].message, "content"):
            logger.error("No valid response content from OpenAI.")
            raise ValueError("No valid response content from OpenAI.")

        raw_response = response.choices[0].message.content
        cleaned_response = clean_response(raw_response)
        try:
            json_data = json.loads(cleaned_response)
            if not isinstance(json_data, dict):
                logger.warning("OpenAI response is not a dictionary, wrapping as error.")
                json_data = {"error": "Non-dict response", "raw": cleaned_response}
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}, raw response: {cleaned_response}")
            json_data = {"error": "Invalid JSON", "raw": cleaned_response}

    except openai.APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        json_data = {"error": f"OpenAI API error: {str(e)}"}
        with open(raw_response_path, "w", encoding="utf-8") as f:
            f.write(f"OpenAI API error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during API call: {str(e)}")
        json_data = {"error": f"Unexpected error: {str(e)}"}
        with open(raw_response_path, "w", encoding="utf-8") as f:
            f.write(f"Exception occurred: {str(e)}")

    try:
        with open(json_output_path, "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, indent=4, ensure_ascii=False)
        logger.info(f"Saved JSON to: {json_output_path}")
    except IOError as e:
        logger.error(f"Failed to save JSON to {json_output_path}: {str(e)}")
        raise

    logger.info(f"Processed PDF: {pdf_path}")
    return {
        "text_path": text_output_path if save_text else "",
        "json_path": json_output_path,
        "raw_response_path": raw_response_path,
        "data": json_data
    }

if __name__ == "__main__":
    process_application(
        pdf_path=r"PDFs\application.pdf",  # Replace with your PDF file path 
        output_dir="JSONs",
        zoom=4,
        save_text=False,
        model="gpt-4o",
        temperature=0,
        clean_non_ascii=True
    ) 