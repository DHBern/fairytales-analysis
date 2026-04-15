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


-----------

## Extended

A Python script that processes Italian `.txt` files, identifies direct speech, attributes speakers using regex and spaCy NLP, and counts dialogue words per character. Outputs annotated texts and detailed CSV reports.

### Requirements
- Python 3.8 or higher
- spaCy library
- Italian language model for spaCy (`it_core_news_sm`)

### Installation
```bash
pip install spacy
python -m spacy download it_core_news_sm
```

### Project Structure
```
your_project/
├── extended.py   # The main script
├── input_dir/              # Place your .txt files here
└── output_tagged/          # Automatically created on run
```

### How to Run
```bash
python3 extended.py
```

### Output Files
All outputs are saved in the `output_tagged/` directory:

| File | Description |
|------|-------------|
| `*.txt` | Original texts with pronoun annotations (`<ab type="pron" ...>`) |
| `dialogue_report.csv` | Detailed span-by-span report with columns: file, span_index, speaker, speaker_source, word_count, question_count, mio_mia_count, validity/skip info, original text, annotated text, extracted features |
| `dialogue_summary.csv` | Aggregated statistics with columns: file, character, word_count, word_percentage, question_count, question_percentage, mio_mia_count, mio_mia_percentage for each file |
| `diagnostics/speaker_diagnostics_overview.csv` | Per-file attribution diagnostics: source distribution, skipped spans, context fallback share, context chain length, regex/NLP disagreement counts |
| `diagnostics/speaker_diagnostics_spans.csv` | Per-span diagnostics: regex and NLP candidates, matched verbs, distances from speech span, final source, suspicious speaker flags, nearby verb candidates |
| `diagnostics/speaker_diagnostics_span_lengths.csv` | Histogram of speech span lengths plus skip-reason counts (`too_short`, `punctuation_only`) |
| `diagnostics/speaker_diagnostics_speaker_quality.csv` | Speaker quality and alias fragmentation diagnostics: suspicious labels, singleton speakers, singleton word share |
| `diagnostics/speaker_diagnostics_speech_verbs.csv` | Counts of regex hits, NLP hits, and nearby verb candidates that are not currently in the speech-verb lexicons |

### Diagnostics Guide

The diagnostics reports are meant to answer seven common failure questions:

1. **How much attribution comes from `regex`, `nlp`, `context`, or `unknown`?**
   Check `speaker_diagnostics_overview.csv`.
2. **How long are context carry-over chains?**
   Check `avg_context_chain` and `max_context_chain` in `speaker_diagnostics_overview.csv`.
3. **How many spans are being discarded before attribution?**
   Check `speaker_diagnostics_span_lengths.csv`.
4. **Do regex and NLP disagree on the same span?**
   Check `candidate_disagreement` in `speaker_diagnostics_spans.csv` and the per-file rows in `speaker_diagnostics_overview.csv`.
5. **Are the extracted speaker labels suspicious?**
   Check `speaker_diagnostics_speaker_quality.csv` for lowercase labels, long labels, pronoun-like labels, and singleton aliases.
6. **How far is the attribution cue from the speech span?**
   Check `regex_distance`, `nlp_distance`, and `attribution_distance` in `speaker_diagnostics_spans.csv`.
7. **Which verbs are driving matches, and which nearby verbs are missing from the lexicons?**
   Check `speaker_diagnostics_speech_verbs.csv`.

### Configuration Options

### Adjust Attribution Context Window
If speaker names appear far from dialogue tags, increase the context window in `extract_speech_with_context()`:
```python
segments = extract_speech_with_context(tagged_text, window=300)  # Default is 150
```

#### Add Custom Speech Verbs
Extend the verb lists to improve attribution for literary or dialectal texts:
```python
# In ITALIAN_VERB_LEMMAS (for spaCy lemmatization)
ITALIAN_VERB_LEMMAS.add("sussurrare")

# In SPEECH_VERB_FORMS (for regex matching)
SPEECH_VERB_FORMS.append("sussurrò")
```

#### Filter Thresholds
Adjust the minimum span length to include shorter utterances:
```python
# In extract_speech_with_context()
if len(speech) < 3 or not re.search(r'\w', speech):  # Change 3 to 1 or 2
```

## Notes and Troubleshooting

**File Encoding**: Input files should be UTF-8 encoded. The script includes `errors="replace"` as a fallback for malformed characters.

**Missing Language Model**: If you encounter an error loading `it_core_news_sm`, verify installation with:
```bash
python -m spacy validate
```

**Skipped Segments**: Spans shorter than 3 words or containing only punctuation are excluded to reduce false positives. Adjust the threshold in `extract_speech_with_context()` if your use case requires capturing shorter utterances.

**Unknown Speakers**: Dialogue attributed to "Sconosciuto" indicates the attribution logic could not identify a speaker. If this exceeds 20% of your corpus, consider:
- Expanding the context window
- Adding more speech verb variants
- Post-processing the CSV to merge character aliases (e.g., "Mario", "il signore", "egli" -> "Mario")

### Example Workflow
1. Prepare 2-3 sample files in `input_dir/` for testing
2. Run the script and inspect `pronoun_report.csv` to verify attribution accuracy
3. Review `dialogue_summary.csv` for character dialogue distribution
4. Scale to your full corpus once satisfied with results
