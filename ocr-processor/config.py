# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ===============================
# API Configuration
# ===============================
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
PROMPT_OCR = os.getenv("PROMPT_TEMPLATE")

# ===============================
# Image Processing Settings
# ===============================
INPUT_DIR = os.getenv("INPUT_DIR", str(PROJECT_ROOT / "ocr-processor" / "images"))
PDF_DIR = os.getenv("PDF_DIR", str(PROJECT_ROOT / "ocr-processor" / "pdfs"))
IMAGE_FORMAT = os.getenv("IMAGE_FORMAT", "JPEG")
IMAGE_QUALITY = int(os.getenv("IMAGE_QUALITY", 90))
MAX_IMAGE_SIZEBYTES = int(os.getenv("MAX_IMAGE_SIZE_BYTES", 5_000_000))
ALLOWED_EXTENSIONS = [ext.strip() for ext in os.getenv("ALLOWED_EXTENSIONS", "[.jpg, .jpeg, .png, .tiff, .webp]").strip("[]").split(",")]

# ===============================
# Output Settings
# ===============================
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "ocr-processor" / "outputs"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

