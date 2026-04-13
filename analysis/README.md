# Analysis

This folder contains text analysis tools for the merged OCR output.

## Usage

- Put merged OCR files in `analysis/input_dir/`.
- These should come from `ocr-processor/outputs/merged`.
- Run the direct speech analysis:

```bash
python3 analysis/direct_speech.py
```

The tagged output is written to `analysis/output_tagged/`.
A CSV report with pronoun extraction results is also saved to `analysis/output_tagged/pronoun_report.csv`.

> Requires `spaCy` with the Italian model:
> 
> ```bash
> pip install spacy
> python3 -m spacy download it_core_news_sm
> ```

## Functions

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
