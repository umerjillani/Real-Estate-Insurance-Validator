import openai
import base64
import os
import json
import re
import logging
from PIL import Image
import fitz  # PyMuPDF
from dotenv import load_dotenv
from contextlib import contextmanager
import tempfile
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from io import BytesIO
 
# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment.")

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Utility to convert keys to camelCase
def to_camel_case(s):
    if not s:
        return s
    s = re.sub(r'[^a-zA-Z0-9]', ' ', s).strip()
    words = [word for word in re.split(r'\s+|_', s) if word]
    if not words:
        return s.lower()
    return words[0].lower() + ''.join(word.capitalize() for word in words[1:])

def convert_keys_to_camel_case(data):
    if isinstance(data, dict):
        return {to_camel_case(k): convert_keys_to_camel_case(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_keys_to_camel_case(item) for item in data]
    return data

# Context manager for creating temporary image files
@contextmanager
def temp_image_file():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as temp_file:
        yield temp_file.name

# Convert PDF to list of PIL images
def pdf_to_images(path, dpi, page_limit):
    try:
        doc = fitz.open(path)
        total_pages = len(doc)
        if total_pages > page_limit:
            logger.warning(f"PDF has {total_pages} pages, but only {page_limit} will be processed.")
        return [
            Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            for pix in [doc[i].get_pixmap(dpi=dpi) for i in range(min(total_pages, page_limit))]
        ]
    except Exception as e:
        logger.error(f"Failed to process PDF: {str(e)}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def image_to_base64(image):
    try:
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        logger.exception("Failed to convert image to base64")
        raise

# Retryable: Extract JSON from image via OpenAI Vision API
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def extract_json_from_image(image, temperature, max_tokens):
    try:
        base64_img = image_to_base64(image)
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all meaningful key-value pairs from this image, try to structure the key-values pairs according to sections. Some keys may repeat, fetch them as it, nothing to miss if any key does not have any value fill it with empty string, and return only a valid JSON object."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_img}"}
                        }
                    ]
                }
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
        return content
    except Exception as e:
        logger.exception("OpenAI API call failed inside extract_json_from_image")
        raise

# Main processing function
def process_EC(pdf_path, output_dir="JSONs", dpi=300, page_limit=None, temperature=0.2, max_tokens=1800):
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    page_limit = page_limit or int(os.getenv("VALID_PAGES_LIMIT", 8))
    if page_limit <= 0:
        raise ValueError("Page limit must be a positive integer.")

    logger.info(f"Processing PDF: {pdf_path}")
    images = pdf_to_images(pdf_path, dpi=dpi, page_limit=page_limit)
    all_pages_data = {}

    for i, img in enumerate(images):
        logger.info(f"Processing page {i+1}")
        try:
            result = extract_json_from_image(img, temperature, max_tokens)
            try:
                parsed = json.loads(result)
                if not isinstance(parsed, dict):
                    logger.warning(f"Page {i+1}: Response is not a dictionary, skipping.")
                    all_pages_data[f"page_{i+1}"] = {"error": "Non-dict response", "raw": result}
                    continue
                if not parsed:
                    logger.info(f"Page {i+1}: Empty JSON object, skipping.")
                    continue
                all_pages_data[f"page_{i+1}"] = convert_keys_to_camel_case(parsed)
            except json.JSONDecodeError as e:
                logger.error(f"Page {i+1}: JSON decode error: {str(e)}")
                all_pages_data[f"page_{i+1}"] = {"error": "Invalid JSON", "raw": result}
        except RetryError as e:
            root_cause = e.last_attempt.exception()
            logger.error(f"Page {i+1}: RetryError - {type(root_cause).__name__}: {root_cause}")
            all_pages_data[f"page_{i+1}"] = {"error": "RetryError", "details": str(root_cause)}
        except Exception as e:
            logger.error(f"Page {i+1}: Failed to process: {str(e)}")
            all_pages_data[f"page_{i+1}"] = {"error": str(e)}

    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    json_path = os.path.join(output_dir, base_name + ".json")

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_pages_data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON saved to: {json_path}")
    except IOError as e:
        logger.error(f"Failed to write JSON to {json_path}: {str(e)}")
        raise

    return json_path

# Run the function
if __name__ == "__main__":
    process_EC(r"PDFs\1 done.pdf")
