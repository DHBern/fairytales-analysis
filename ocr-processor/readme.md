# Fairytales OCR Processor

Python utility for image OCR + evaluation with Character Error Rate (CER).

## Features

1. PDF to image conversion (`pdf_converter.py`)
2. OCR images via Qwen API (`ocr_processor.py`)
3. Local pipeline orchestrator (`main.py`):
   - `convert` (PDF → JPEG images)
   - `ocr` (image → text)
   - `merge` (merge text from different pages of the same text)
   - `evaluate` (CER vs manual ground truth)
4. OCR merge/evaluation helper (`evaluate_ocr.py`) with `merge`/`evaluate` CLI commands

## Requirements

- Python 3.8+
- pip packages from `requirements.txt`

## Setup

1. Create a virtual env (recommended):

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure `.env` with API settings:

```ini
API_KEY=your_api_key
API_URL=https://api.yourprovider.com/v1/chat/completions
MODEL_NAME=qwen3-vl-8b-instruct
PROMPT_TEMPLATE=Extract text from this image.
INPUT_DIR=images
OUTPUT_DIR=outputs
```

## Usage

### 0) PDF to JPEG conversion (PDF → images)

Place PDF files in `pdfs/` (or `PDF_DIR`) then run:

```bash
python3 main.py convert

## default
python3 main.py convert --input pdfs --output images --dpi 300
```

Converts each PDF page to a JPEG image at 300 DPI, named as `{pdf_name}-{page}.jpg`.

### 1) OCR extraction (image → text)

Place images in `images/` (or `INPUT_DIR`) then run:

```bash
python3 main.py ocr

## default
python3 main.py ocr --input images --output outputs
```

### 2) Merge OCR outputs
Merge text from different pages of the same text

```bash
python3 main.py merge

## default
python3 main.py merge --inputs outputs --output outputs/merged
```

Normalized grouping uses stem rules; e.g.:
- `outputs/Cenerentola-Bernoni-1.txt`
- `outputs/Cenerentola-Bernoni-2.txt`
→ `outputs/merged/Cenerentola-Bernoni.txt`

(Optional) Correct manually:
Make sure that the OCRed texts do not contain sections that are not included in the ground truth, e.g. other fairy tales that ends or starts on the same page in the sources.

### 3) Evaluate CER (merged vs ground truth)

Put manual corrected text in `gt/` (file names should be the same as in outputs/merged), then run:

```bash
python3 main.py evaluate

## default
python3 main.py evaluate --merged outputs/merged --manual gt --csv reports/cer.csv
```

Default output CSV: `reports/cer.csv`

### 4) Full pipeline (OCR + merge + evaluate)

Run everything in one command:

```bash
python3 main.py all

## default
python3 main.py all --input images --output outputs --merged outputs/merged --manual gt --csv reports/cer.csv
```

## CER details

- `character_error_rate = min(levenshtein(hyp, ref) / len(ref) * 100, 100)`
- Reports per-file CER in percentage
- Skips entries in outputs/merged without matching gt file

## Troubleshooting

- No output files: check `INPUT_DIR`, file extension list in `main.py`
- API errors: confirm `API_URL`, `API_KEY`, and network access

## Notes

- Each step clears its output directory before processing to ensure clean runs.
- `ocr_processor.py` currently uses base64 embedding for image-to-API payload. 
- Check that the OCRed texts do not contain sections that are not included in the ground truth.