import csv
import os
import re
import shutil
from pathlib import Path

PRON_2 = {"tu", "te", "ti", "voi", "vi"}
PRON_3 = {"lui", "lei", "loro", "lo", "la", "li", "le", "gli"}
_nlp = None


def clear_directory(dir_path):
    """Clear all contents of a directory."""
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)


def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
        except ImportError as exc:
            raise ImportError(
                "spaCy is required for pronoun extraction. "
                "Install with `pip install spacy it-core-news-sm`."
            ) from exc

        _nlp = spacy.load("it_core_news_sm")
    return _nlp


def normalize_text(text):
    """Normalizza alcuni simboli tipografici."""
    text = text.replace("—", "-")
    text = text.replace("«", '"').replace("»", '"')
    return text


def tag_quoted_speech(text):
    """Tagga il discorso diretto tra virgolette."""
    pattern = r'"([^\"]+)"'

    def repl(match):
        content = match.group(0)
        return f"<sp>{content}</sp>"

    return re.sub(pattern, repl, text)


def tag_inline_dash_speech(text):
    """Tagga discorso diretto inline: esempio: disse: - Ciao!"""
    pattern = r'(:\s*)-\s*([^<\n][^-]*)'

    def repl(match):
        prefix = match.group(1)
        content = match.group(2).strip()
        return f"{prefix}<sp>{content}</sp>"

    return re.sub(pattern, repl, text)


def tag_dash_speech(text):
    """Tagga il discorso diretto introdotto da trattino."""
    lines = text.split("\n")
    new_lines = []

    for line in lines:
        stripped = line.strip()

        if re.match(r"^-\s*", stripped):
            if "<sp>" not in line:
                content = re.sub(r"^-\s*", "", stripped)
                line = line.replace(stripped, f"<sp>{content}</sp>")

        new_lines.append(line)

    return "\n".join(new_lines)


def tag_direct_speech(text):
    """Pipeline completa per individuare il parlato diretto."""
    text = normalize_text(text)
    text = tag_quoted_speech(text)
    text = tag_inline_dash_speech(text)
    text = tag_dash_speech(text)
    return text


def extract_spans(text):
    """Estrae il contenuto dei segmenti di discorso diretto già taggati."""
    return re.findall(r"<sp>(.*?)</sp>", text, re.DOTALL)


def annotate_span(span):
    """Cerca pronomi e verbi all'interno di un segmento di discorso diretto."""
    nlp = get_nlp()
    doc = nlp(span)
    annotated = span
    found = []
    pron_found = False

    for token in doc:
        if token.pos_ == "PRON":
            lower = token.text.lower()
            if lower in PRON_2:
                tag = f'<ab type="pron" ana="2">{token.text}</ab>'
                annotated = annotated.replace(token.text, tag, 1)
                found.append((token.text, "2"))
                pron_found = True
            elif lower in PRON_3:
                tag = f'<ab type="pron" ana="3">{token.text}</ab>'
                annotated = annotated.replace(token.text, tag, 1)
                found.append((token.text, "3"))
                pron_found = True

    if not pron_found:
        for token in doc:
            if token.pos_ == "VERB":
                feats = token.morph
                if "Person=2" in feats:
                    tag = f'<ab type="pron" ana="verb_2">{token.text}</ab>'
                    annotated = annotated.replace(token.text, tag, 1)
                    found.append((token.text, "verb_2"))
                elif "Person=3" in feats:
                    tag = f'<ab type="pron" ana="verb_3">{token.text}</ab>'
                    annotated = annotated.replace(token.text, tag, 1)
                    found.append((token.text, "verb_3"))

    return annotated, found


def process_text(text):
    """Analizza i segmenti di discorso diretto e restituisce annotazioni per ciascuno."""
    spans = extract_spans(text)
    results = []

    for sp in spans:
        annotated, found = annotate_span(sp)
        results.append({
            "original": sp,
            "annotated": annotated,
            "features": found,
        })

    return results


def annotate_text_pronouns(text):
    """Annota i pronomi all'interno di tutti gli span di discorso diretto."""
    def repl(match):
        annotated, _ = annotate_span(match.group(1))
        return f"<sp>{annotated}</sp>"

    return re.sub(r"<sp>(.*?)</sp>", repl, text, flags=re.DOTALL)


def write_pronoun_report(rows, csv_path):
    """Scrive un CSV con le estrazioni dei pronomi per ciascun span."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "span_index", "original", "annotated", "features"])
        for row in rows:
            features = "|".join(f"{tok}:{ana}" for tok, ana in row["features"])
            writer.writerow([row["file"], row["span_index"], row["original"], row["annotated"], features])


def analyze_directory(input_dir=None, output_dir=None):
    """Analizza tutti i file TXT in una directory e salva le versioni taggate."""
    if input_dir is None:
        input_dir = Path(__file__).resolve().parent / "input_dir"
    else:
        input_dir = Path(input_dir)

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "output_tagged"
    else:
        output_dir = Path(output_dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"Directory non trovata: {input_dir}")

    clear_directory(output_dir)

    report_rows = []
    processed = []
    for path in sorted(input_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        tagged = tag_direct_speech(text)
        annotated_text = annotate_text_pronouns(tagged)

        target_path = output_dir / path.name
        target_path.write_text(annotated_text, encoding="utf-8")
        processed.append(target_path)

        for index, item in enumerate(process_text(tagged), start=1):
            report_rows.append({
                "file": path.name,
                "span_index": index,
                "original": item["original"],
                "annotated": item["annotated"],
                "features": item["features"],
            })

    report_path = output_dir / "dialogue_report.csv"
    write_pronoun_report(report_rows, report_path)

    return processed, report_path


if __name__ == "__main__":
    source_dir = Path(__file__).resolve().parent / "input_dir"
    target_dir = Path(__file__).resolve().parent / "output_tagged"
    print(f"Analisi file da: {source_dir}")
    print(f"Salvo output in: {target_dir}")
    processed, report_path = analyze_directory(source_dir, target_dir)
    print(f"Analisi completata. {len(processed)} file elaborati.")
    print(f"Report pronoun extraction: {report_path}")
