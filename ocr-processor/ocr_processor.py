# ocr_processor.py
import os
import base64
import requests
from config import API_KEY, API_URL, MODEL_NAME, PROMPT_OCR
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)


def ocr_image(image_path):
    """
    Extract text from image using Qwen model via API.
    All configuration comes from config.py.
    """
    # 1. Check if file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # 2. Convert image to base64
    try:
        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            if max(img.size) > 1280:
                # Resize proportionally to fit within 1280x1280
                ratio = 1280 / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            base64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        raise Exception(f"Error encoding image: {e}")

    # 3. Prepare request to Qwen API
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_OCR},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }
        ],
        "max_tokens": 4000,
    }

    # 4. Send request
    try:
        logger.info("Sending image to Qwen API...")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {e}")
    except KeyError:
        raise Exception("Unexpected response format from Qwen API")
