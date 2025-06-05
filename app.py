import os
import json
import logging
import boto3
from flask import Flask, request, jsonify, abort
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from contextlib import contextmanager
import tempfile
import subprocess
from datetime import datetime
from io import BytesIO
from Scripts.OCR_Application import process_application
from Scripts.OCR_EC import process_EC
from Scripts.compare import process_rules, process_photographs

app = Flask(__name__)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Validate environment variables
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in the environment.")
if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME]):
    raise ValueError("AWS credentials or S3 bucket name not set in the environment.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

# Configuration
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
S3_PDF_PREFIX = "pdfs/"
S3_IMAGE_PREFIX = "images/"
S3_JSON_PREFIX = "jsons/"

# Validate Tesseract installation
try:
    subprocess.run(["tesseract", "--version"], capture_output=True, check=True)
except subprocess.CalledProcessError:
    logger.error("Tesseract OCR is not installed or not found in PATH.")
    raise EnvironmentError("Tesseract OCR is required. Install it using your package manager (e.g., `apt-get install tesseract-ocr`).")

# Utility functions
def allowed_file(filename, allowed_extensions=ALLOWED_EXTENSIONS):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions

@contextmanager
def temp_file(suffix=".pdf"):
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp:
        yield temp.name

def upload_to_s3(file_stream, bucket, key):
    """Upload a file stream to S3 and return the S3 path."""
    try:
        s3_client.upload_fileobj(file_stream, bucket, key)
        s3_path = f"s3://{bucket}/{key}"
        logger.info(f"Uploaded file to S3: {s3_path}")
        return s3_path
    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        raise

def download_from_s3(s3_path, local_path):
    """Download a file from S3 to a local path."""
    try:
        bucket, key = parse_s3_path(s3_path)
        s3_client.download_file(bucket, key, local_path)
        logger.info(f"Downloaded file from S3: {s3_path} to {local_path}")
    except Exception as e:
        logger.error(f"Failed to download from S3: {str(e)}")
        raise

def parse_s3_path(s3_path):
    """Parse an S3 path (s3://bucket/key) into bucket and key."""
    if not s3_path.startswith("s3://"):
        raise ValueError(f"Invalid S3 path: {s3_path}")
    parts = s3_path.replace("s3://", "").split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 path format: {s3_path}")
    return parts[0], parts[1]

@app.route("/upload_ec", methods=["POST"])
def upload_ec():
    """
    Upload and process an Elevation Certificate (EC) PDF using OCR_EC.
    Uploads the PDF to S3, processes it, and uploads the JSON to S3.
    """
    logger.info("Received request to upload and process EC PDF")

    if "file" not in request.files:
        logger.error("No file part in the request")
        return abort(400, description="No file part in the request")

    file = request.files["file"]
    if file.filename == "":
        logger.error("No selected file")
        return abort(400, description="No selected file")

    if not allowed_file(file.filename, {"pdf"}):
        logger.error("Invalid file type, only PDFs are allowed")
        return abort(400, description="Only PDF files are allowed")

    try:
        # Upload PDF to S3
        filename = secure_filename(file.filename)
        s3_key = f"{S3_PDF_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        file.seek(0)  # Reset file pointer
        s3_pdf_path = upload_to_s3(file, S3_BUCKET_NAME, s3_key)

        # Download PDF to temporary file for processing
        with temp_file(suffix=".pdf") as temp_path:
            download_from_s3(s3_pdf_path, temp_path)
            json_path = process_EC(
                pdf_path=temp_path,
                output_dir=tempfile.gettempdir(),  # Use temp dir for local JSON
                dpi=300,
                page_limit=None,
                temperature=0,
                max_tokens=1800
            )
            logger.info(f"Processed EC PDF, local JSON saved to: {json_path}")

            # Load JSON data
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)

            # Upload JSON to S3
            json_filename = os.path.basename(json_path)
            s3_json_key = f"{S3_JSON_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}_{json_filename}"
            with open(json_path, "rb") as f:
                s3_json_path = upload_to_s3(f, S3_BUCKET_NAME, s3_json_key)

            return jsonify({
                "status": "success",
                "method": "upload_ec",
                "data": json_data,
                "s3_pdf_path": s3_pdf_path,
                "s3_json_path": s3_json_path
            })
    except Exception as e:
        logger.error(f"Error processing EC PDF: {str(e)}")
        return abort(500, description=f"Error processing EC PDF: {str(e)}")

@app.route("/upload_application", methods=["POST"])
def upload_application():
    """
    Upload and process an Application PDF using OCR_Application.
    Uploads the PDF to S3, processes it, and uploads the JSON to S3.
    """
    logger.info("Received request to upload and process Application PDF")

    if "file" not in request.files:
        logger.error("No file part in the request")
        return abort(400, description="No file part in the request")

    file = request.files["file"]
    if file.filename == "":
        logger.error("No selected file")
        return abort(400, description="No selected file")

    if not allowed_file(file.filename, {"pdf"}):
        logger.error("Invalid file type, only PDFs are allowed")
        return abort(400, description="Only PDF files are allowed")

    try:
        # Upload PDF to S3
        filename = secure_filename(file.filename)
        s3_key = f"{S3_PDF_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        file.seek(0)  # Reset file pointer
        s3_pdf_path = upload_to_s3(file, S3_BUCKET_NAME, s3_key)

        # Download PDF to temporary file for processing
        with temp_file(suffix=".pdf") as temp_path:
            download_from_s3(s3_pdf_path, temp_path)
            result = process_application(
                pdf_path=temp_path,
                output_dir=tempfile.gettempdir(),
                zoom=4,
                save_text=True,
                model="gpt-4o",
                clean_non_ascii=False
            )
            logger.info(f"Processed Application PDF, local JSON saved to: {result['json_path']}")

            # Upload JSON to S3
            json_filename = os.path.basename(result["json_path"])
            s3_json_key = f"{S3_JSON_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}_{json_filename}"
            with open(result["json_path"], "rb") as f:
                s3_json_path = upload_to_s3(f, S3_BUCKET_NAME, s3_json_key)

            # Upload text and raw response files to S3 if they exist
            s3_text_path = None
            s3_raw_response_path = None
            if result["text_path"]:
                text_filename = os.path.basename(result["text_path"])
                s3_text_key = f"{S3_JSON_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}_{text_filename}"
                with open(result["text_path"], "rb") as f:
                    s3_text_path = upload_to_s3(f, S3_BUCKET_NAME, s3_text_key)
            if result["raw_response_path"]:
                raw_filename = os.path.basename(result["raw_response_path"])
                s3_raw_key = f"{S3_JSON_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}_{raw_filename}"
                with open(result["raw_response_path"], "rb") as f:
                    s3_raw_response_path = upload_to_s3(f, S3_BUCKET_NAME, s3_raw_key)

            return jsonify({
                "status": "success",
                "method": "upload_application",
                "data": result["data"],
                "s3_pdf_path": s3_pdf_path,
                "s3_json_path": s3_json_path,
                "s3_text_path": s3_text_path,
                "s3_raw_response_path": s3_raw_response_path
            })
    except Exception as e:
        logger.error(f"Error processing Application PDF: {str(e)}")
        return abort(500, description=f"Error processing Application PDF: {str(e)}")

@app.route("/process_rules", methods=["POST"])
def process_rules_endpoint():
    """
    Run comparison rules using JSON files from S3.
    Expects S3 paths for EC and Application JSONs in the request body.
    """
    logger.info("Received request to process rules")

    data = request.get_json()
    if not data or "ec_json_path" not in data or "app_json_path" not in data:
        logger.error("Missing ec_json_path or app_json_path in request body")
        return abort(400, description="ec_json_path and app_json_path are required in the request body")

    ec_json_path = data["ec_json_path"]
    app_json_path = data["app_json_path"]

    try:
        # Download JSONs from S3
        with temp_file(suffix=".json") as ec_temp_path:
            download_from_s3(ec_json_path, ec_temp_path)
            with open(ec_temp_path, "r", encoding="utf-8") as f:
                data_pdf = json.load(f)

        with temp_file(suffix=".json") as app_temp_path:
            download_from_s3(app_json_path, app_temp_path)
            with open(app_temp_path, "r", encoding="utf-8") as f:
                data_app = json.load(f)

        # Redirect print statements to capture output
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            # Temporarily set global variables for compare.py
            sys.modules["Scripts.compare"].data_pdf = data_pdf
            sys.modules["Scripts.compare"].data_app = data_app
            process_rules()
            rules_output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            # Clean up global variables
            del sys.modules["Scripts.compare"].data_pdf
            del sys.modules["Scripts.compare"].data_app

        return jsonify({
            "status": "success",
            "method": "process_rules",
            "rules_output": rules_output
        })
    except Exception as e:
        logger.error(f"Error during rules processing: {str(e)}")
        return abort(500, description=f"Error during rules processing: {str(e)}")

@app.route("/process_photographs", methods=["POST"])
def process_photographs_endpoint():
    """
    Process photographs and run comparison logic.
    Expects S3 paths for EC and Application JSONs and image files in the request.
    """
    logger.info("Received request to process photographs")

    if "ec_json_path" not in request.form or "app_json_path" not in request.form:
        logger.error("Missing ec_json_path or app_json_path in request form")
        return abort(400, description="ec_json_path and app_json_path are required in the request form")

    ec_json_path = request.form["ec_json_path"]
    app_json_path = request.form["app_json_path"]

    image_files = request.files.getlist("images")
    image_paths = []
    for img_file in image_files:
        if img_file and allowed_file(img_file.filename, {"png", "jpg", "jpeg"}):
            try:
                filename = secure_filename(img_file.filename)
                s3_key = f"{S3_IMAGE_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                img_file.seek(0)
                s3_image_path = upload_to_s3(img_file, S3_BUCKET_NAME, s3_key)
                # Download image to temporary file for processing
                with temp_file(suffix=f".{filename.rsplit('.', 1)[1]}") as temp_img_path:
                    download_from_s3(s3_image_path, temp_img_path)
                    image_paths.append(temp_img_path)
                logger.info(f"Uploaded and downloaded image: {s3_image_path}")
            except Exception as e:
                logger.error(f"Error handling image file {img_file.filename}: {str(e)}")
                return abort(500, description=f"Error handling image file: {str(e)}")
        else:
            logger.error(f"Invalid image file type: {img_file.filename}")
            return abort(400, description=f"Invalid image file type: {img_file.filename}")

    if not image_paths:
        logger.error("No valid image files provided")
        return abort(400, description="At least one valid image file (png, jpg, jpeg) is required")

    try:
        # Download JSONs from S3
        with temp_file(suffix=".json") as ec_temp_path:
            download_from_s3(ec_json_path, ec_temp_path)
            with open(ec_temp_path, "r", encoding="utf-8") as f:
                data_pdf = json.load(f)

        with temp_file(suffix=".json") as app_temp_path:
            download_from_s3(app_json_path, app_temp_path)
            with open(app_temp_path, "r", encoding="utf-8") as f:
                data_app = json.load(f)

        # Redirect print statements to capture output
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            # Temporarily set global variables for compare.py
            sys.modules["Scripts.compare"].data_pdf = data_pdf
            sys.modules["Scripts.compare"].data_app = data_app
            sys.modules["Scripts.compare"].image_path = image_paths
            process_photographs()
            photographs_output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            # Clean up global variables
            del sys.modules["Scripts.compare"].data_pdf
            del sys.modules["Scripts.compare"].data_app
            del sys.modules["Scripts.compare"].image_path

        return jsonify({
            "status": "success",
            "method": "process_photographs",
            "photographs_output": photographs_output,
            "s3_image_paths": [f"s3://{S3_BUCKET_NAME}/{S3_IMAGE_PREFIX}{os.path.basename(path)}" for path in image_paths]
        })
    except Exception as e:
        logger.error(f"Error during photographs processing: {str(e)}")
        return abort(500, description=f"Error during photographs processing: {str(e)}")

# Error handlers
@app.errorhandler(400)
def bad_request(error):
    logger.error(f"Bad request: {str(error.description)}")
    return jsonify({
        "status": "error",
        "message": str(error.description)
    }), 400

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error.description)}")
    return jsonify({
        "status": "error",
        "message": str(error.description)
    }), 500

if __name__ == "__main__":
    logger.info("Starting Flask API server")
    app.run(debug=False, host="0.0.0.0", port=5000)