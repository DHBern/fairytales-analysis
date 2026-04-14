# Fairytales Analysis

A complete pipeline for OCR processing and text analysis of Italian fairytale texts.

## Project Structure

```
fairytales-analysis/
├── ocr-processor/        # PDF → Image → OCR → Text pipeline
│   ├── main.py           # CLI orchestrator
│   ├── ocr_processor.py  # OCR via Qwen API
│   ├── pdf_converter.py  # PDF to JPEG conversion
│   ├── evaluate_ocr.py   # Merge and CER evaluation
│   ├── config.py         # Configuration
│   ├── images/           # Input images
│   ├── outputs/          # OCR text outputs
│   ├── pdfs/             # Input PDFs
│   ├── gt/               # Ground truth texts
│   └── reports/          # CER reports
├── analysis/             # Text analysis tools
│   ├── direct_speech.py  # Direct speech and pronoun analysis
│   ├── input_dir/        # Input texts (from ocr-processor/outputs/merged)
│   └── output_tagged/    # Tagged output with annotations
├── README.md             # This file
├── requirements.txt      # Dependencies
└── .gitignore
```

## Quick Start

1. **Setup environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 -m spacy download it_core_news_sm
   ```

2. **Configure OCR:**
   - Create `.env` file in `ocr-processor/` with API settings

3. **Run the pipeline:**
   ```bash
   cd ocr-processor
   python3 main.py all
   cd ../analysis
   python3 direct_speech.py
   ```

## OCR Processor Module

Python utility for image OCR + evaluation with Character Error Rate (CER).

### Features

1. PDF to image conversion (`pdf_converter.py`)
2. OCR images via Qwen API (`ocr_processor.py`)
3. Local pipeline orchestrator (`main.py`):
   - `convert` (PDF → JPEG images)
   - `ocr` (image → text)
   - `merge` (merge text from different pages of the same text)
   - `evaluate` (CER vs manual ground truth)
4. OCR merge/evaluation helper (`evaluate_ocr.py`) with `merge`/`evaluate` CLI commands

### Requirements

- Python 3.8+
- pip packages from `requirements.txt`

### Setup

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

### Usage

#### 0) PDF to JPEG conversion (PDF → images)

Place PDF files in `pdfs/` (or `PDF_DIR`) then run:

```bash
python3 ocr-processor/main.py convert

## default
python3 ocr-processor/main.py convert --input pdfs --output images --dpi 300
```

Converts each PDF page to a JPEG image at 300 DPI, named as `{pdf_name}-{page}.jpg`.

#### 1) OCR extraction (image → text)

Place images in `images/` (or `INPUT_DIR`) then run:

```bash
python3 ocr-processor/main.py ocr

## default
python3 ocr-processor/main.py ocr --input images --output outputs
```

#### 2) Merge OCR outputs

Merge text from different pages of the same text

```bash
python3 ocr-processor/main.py merge

## default
python3 ocr-processor/main.py merge --inputs outputs --output outputs/merged
```

Normalized grouping uses stem rules; e.g.:
- `outputs/Cenerentola-Bernoni-1.txt`
- `outputs/Cenerentola-Bernoni-2.txt`
→ `outputs/merged/Cenerentola-Bernoni.txt`

(Optional) Correct manually:
Make sure that the OCRed texts do not contain sections that are not included in the ground truth, e.g. other fairy tales that ends or starts on the same page in the sources.

#### 3) Evaluate CER (merged vs ground truth)

Put manual corrected text in `gt/` (file names should be the same as in outputs/merged), then run:

```bash
python3 ocr-processor/main.py evaluate

## default
python3 ocr-processor/main.py evaluate --merged outputs/merged --manual gt --csv reports/cer.csv
```

Default output CSV: `reports/cer.csv` + `reports/evaluation_detailed.txt`.

#### 4) Full pipeline (OCR + merge + evaluate)

Run everything in one command:

```bash
python3 ocr-processor/main.py all

## default
python3 ocr-processor/main.py all --input images --output outputs --merged outputs/merged --manual gt --csv reports/cer.csv
```

### CER details

- `character_error_rate = min(levenshtein(hyp, ref) / len(ref) * 100, 100)`
- Reports per-file CER in percentage
- Skips entries in outputs/merged without matching gt file
- See all differences in reports/evaluation_detailed.txt


### Notes

- Each step clears its output directory before processing to ensure clean runs.
- `ocr_processor.py` currently uses base64 embedding for image-to-API payload.
- Check that the OCRed texts do not contain sections that are not included in the ground truth.


--------------------------------


## Analysis Module

Text analysis tools for the merged OCR output.

### Usage

- Put merged OCR files in `analysis/input_dir/` (from `ocr-processor/outputs/merged`).
- Run the direct speech analysis:

```bash
python3 analysis/direct_speech.py
```

The tagged output is written to `analysis/output_tagged/`.
A CSV report with pronoun extraction results is also saved to `analysis/output_tagged/pronoun_report.csv`.

> **Note:** The output directory is cleared before each run to ensure clean results.

### Functions

- `normalize_text(text)` — normalizza simboli tipografici.
- `tag_quoted_speech(text)` — tagga il discorso tra virgolette.
- `tag_inline_dash_speech(text)` — tagga il discorso diretto inline dopo i due punti.
- `tag_dash_speech(text)` — tagga le linee che iniziano con trattino.
- `tag_direct_speech(text)` — esegue l’intera pipeline.
- `extract_spans(text)` — estrae i segmenti già taggati come discorso diretto.
- `annotate_span(span)` — cerca pronomi e verbi in un segmento di discorso diretto.
- `process_text(text)` — analizza tutti gli span e restituisce le annotazioni.
- `annotate_text_pronouns(text)` — sostituisce gli span nel testo con versioni annotate.
- `analyze_directory(input_dir, output_dir)` — analizza tutti i file `.txt` in una directory.

## Dependencies

All dependencies are in `requirements.txt`:
- `requests` — HTTP client
- `Pillow` — Image processing
- `python-dotenv` — Environment variable management
- `pdf2image` — PDF to image conversion (requires `pdftoppm` system package)
- `spacy` — NLP processing for Italian

**Additional system dependency:**
```bash
# Ubuntu/Debian
sudo apt-get install poppler-utils

# macOS
brew install poppler
```

**SpaCy Italian model:**
```bash
python3 -m spacy download it_core_news_sm
```
