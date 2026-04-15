import csv
import logging
import os
import re
import shutil
from pathlib import Path
from collections import defaultdict

PRON_2 = {"tu", "te", "ti", "voi", "vi"}
PRON_3 = {"lui", "lei", "loro", "lo", "la", "li", "le", "gli"}
_nlp = None
logger = logging.getLogger(__name__)
MIN_SPEECH_LEN = 3
CONTEXT_WINDOW = 150
SUSPICIOUS_SPEAKER_MAX_TOKENS = 4
MIO_MIA_PATTERN = re.compile(r"\b(?:mio|mia)\b", re.IGNORECASE)

# Italian speech verbs (lemmas for spaCy, forms for regex)
ITALIAN_VERB_LEMMAS = {
    "dire", "rispondere", "chiedere", "esclamare", "sussurrare", "mormorare",
    "affermare", "replicare", "aggiungere", "gridare", "domandare", "ribattere",
    "confermare", "negare", "ammonire", "osservare", "continuare", "proseguire",
    "interrompere", "concludere", "iniziare", "parlare", "intervenire"
}

SPEECH_VERB_FORMS = [
    "disse", "rispose", "chiese", "esclamò", "sussurrò", "mormorò", "affermò",
    "replicò", "aggiunse", "gridò", "domandò", "ribatté", "confermò", "negò",
    "ammonì", "osservò", "continuò", "proseguì", "interruppe", "concluse",
    "iniziò", "dissero", "risposero", "chiesero", "esclamarono", "sussurrarono",
    "mormorarono", "affermarono", "replicarono", "aggiunsero", "gridarono",
    "domandarono", "ribatterono", "confermarono", "negarono", "ammonirono",
    "osservarono", "continuarono", "proseguirono", "interruppero", "conclusero",
    "finirono", "iniziarono", "dice", "diceva", "parlava", "rispondeva",
    "chiedeva", "parla", "risponde", "domanda", "esclama", "mormora",
    "affermava", "replicava", "gridava", "continuava", "proseguiva",
    "concludeva", "iniziava", "interrompeva", "osservava"
]

SPEAKER_REGEX = re.compile(
    r'\b([A-Z][a-zÀ-ÿ\'\-]+(?:\s+[A-Z][a-zÀ-ÿ\'\-]+)*?)\s+'
    r'(?:' + '|'.join(SPEECH_VERB_FORMS) + r')\b',
    re.IGNORECASE | re.DOTALL
)
MISSING_VERB_PATTERN = re.compile(r'\b([A-Za-zÀ-ÿ\'\-]+)\b')


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
        return f"<sp>{match.group(0)}</sp>"
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
        if re.match(r"^-\s*", stripped) and "<sp>" not in line:
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


def is_valid_speech_span(speech):
    """Verifica se uno span contiene abbastanza contenuto linguistico."""
    if len(speech) < MIN_SPEECH_LEN:
        return False, "too_short"
    if not re.search(r'\w', speech):
        return False, "punctuation_only"
    return True, ""


def extract_speech_segments(text, window=CONTEXT_WINDOW):
    """Estrae tutti gli span e conserva diagnostica per quelli scartati."""
    segments = []
    for span_index, match in enumerate(re.finditer(r'<sp>(.*?)</sp>', text, re.DOTALL), start=1):
        start, end = match.start(), match.end()
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        speech = match.group(1).strip()
        is_valid, skip_reason = is_valid_speech_span(speech)
        segments.append({
            "span_index": span_index,
            "speech": speech,
            "context": text[ctx_start:ctx_end],
            "context_window": window,
            "context_start": ctx_start,
            "context_end": ctx_end,
            "word_count": len(speech.split()),
            "start": start,
            "end": end,
            "is_valid": is_valid,
            "skip_reason": skip_reason,
        })
    return segments


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


# ─────────────────────────────────────────────────────────────
# NEW: Speaker Attribution & Dialogue Counting
# ─────────────────────────────────────────────────────────────
def extract_speech_with_context(text, window=CONTEXT_WINDOW):
    """Estrae segmenti <sp> con contesto circostante per l'attribuzione."""
    return [segment for segment in extract_speech_segments(text, window) if segment["is_valid"]]


def get_speaker_regex(context):
    """Attribuzione rapida tramite regex: Nome + verbo del discorso."""
    m = SPEAKER_REGEX.search(context)
    return m.group(1) if m else None


def get_speaker_regex_details(context, speech_start=None, context_start=0):
    """Restituisce speaker regex con verbo e distanza dal parlato."""
    for match in SPEAKER_REGEX.finditer(context):
        candidate = match.group(1).strip()
        verb_match = re.search(r'(?:' + '|'.join(SPEECH_VERB_FORMS) + r')\b', match.group(0), re.IGNORECASE)
        verb = verb_match.group(0) if verb_match else ""
        candidate_start = context_start + match.start(1)
        candidate_end = context_start + match.end(1)
        distance = None
        if speech_start is not None:
            if candidate_end <= speech_start:
                distance = speech_start - candidate_end
            else:
                distance = candidate_start - speech_start
        return {
            "speaker": candidate,
            "verb": verb,
            "distance": distance,
            "start": candidate_start,
            "end": candidate_end,
            "matched_text": match.group(0),
        }
    return None


def get_speaker_nlp(context):
    """Attribuzione tramite spaCy: soggetto di verbi del discorso."""
    nlp = get_nlp()
    doc = nlp(context)
    for token in doc:
        if token.lemma_.lower() in ITALIAN_VERB_LEMMAS:
            # Cerca soggetto prima o dopo il verbo
            for child in token.children:
                if child.dep_ == "nsubj" and child.ent_type_ in ("PER", "PERSON"):
                    return child.text
                if child.dep_ == "compound" and child.head.ent_type_ in ("PER", "PERSON"):
                    return f"{child.text} {child.head.text}"
            # Casi inversi: "disse Mario"
            for next_tok in doc[token.i+1:min(token.i+4, len(doc))]:
                if next_tok.ent_type_ in ("PER", "PERSON") and next_tok.pos_ in {"PROPN", "NOUN"}:
                    return next_tok.text
    return None


def get_speaker_nlp_details(context, speech_start=None, context_start=0):
    """Restituisce speaker NLP con lemma verbale e distanza dal parlato."""
    nlp = get_nlp()
    doc = nlp(context)
    for token in doc:
        if token.lemma_.lower() not in ITALIAN_VERB_LEMMAS:
            continue
        for child in token.children:
            if child.dep_ == "nsubj" and child.ent_type_ in ("PER", "PERSON"):
                distance = None
                child_start = context_start + child.idx
                child_end = child_start + len(child.text)
                if speech_start is not None:
                    if child_end <= speech_start:
                        distance = speech_start - child_end
                    else:
                        distance = child_start - speech_start
                return {
                    "speaker": child.text,
                    "verb": token.text,
                    "lemma": token.lemma_.lower(),
                    "distance": distance,
                    "start": child_start,
                    "end": child_end,
                }
            if child.dep_ == "compound" and child.head.ent_type_ in ("PER", "PERSON"):
                speaker = f"{child.text} {child.head.text}"
                child_start = context_start + child.idx
                child_end = context_start + child.head.idx + len(child.head.text)
                distance = None
                if speech_start is not None:
                    if child_end <= speech_start:
                        distance = speech_start - child_end
                    else:
                        distance = child_start - speech_start
                return {
                    "speaker": speaker,
                    "verb": token.text,
                    "lemma": token.lemma_.lower(),
                    "distance": distance,
                    "start": child_start,
                    "end": child_end,
                }
        for next_tok in doc[token.i + 1:min(token.i + 4, len(doc))]:
            if next_tok.ent_type_ in ("PER", "PERSON") and next_tok.pos_ in {"PROPN", "NOUN"}:
                next_start = context_start + next_tok.idx
                next_end = next_start + len(next_tok.text)
                distance = None
                if speech_start is not None:
                    if next_end <= speech_start:
                        distance = speech_start - next_end
                    else:
                        distance = next_start - speech_start
                return {
                    "speaker": next_tok.text,
                    "verb": token.text,
                    "lemma": token.lemma_.lower(),
                    "distance": distance,
                    "start": next_start,
                    "end": next_end,
                }
    return None


def collect_candidate_verbs(context):
    """Raccoglie verbi vicini al parlato che non sono nei lessici correnti."""
    nlp = get_nlp()
    doc = nlp(context)
    candidates = []
    for token in doc:
        if token.pos_ != "VERB":
            continue
        lemma = token.lemma_.lower()
        form = token.text.lower()
        if lemma in ITALIAN_VERB_LEMMAS or form in SPEECH_VERB_FORMS:
            continue
        candidates.append({
            "form": token.text,
            "lemma": lemma,
        })
    return candidates


def speaker_quality_flags(speaker):
    """Heuristics per individuare speaker sospetti."""
    flags = []
    tokens = speaker.split()
    if not speaker or speaker == "Sconosciuto":
        return flags
    if speaker == speaker.lower():
        flags.append("lowercase_only")
    if len(tokens) > SUSPICIOUS_SPEAKER_MAX_TOKENS:
        flags.append("too_many_tokens")
    if any(char in ",;:.!?" for char in speaker):
        flags.append("contains_punctuation")
    if any(token.lower() in PRON_3 for token in tokens):
        flags.append("contains_pronoun")
    if not re.fullmatch(r"[A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ'\-]+)*", speaker):
        flags.append("contains_non_name_chars")
    if len(tokens) == 1 and speaker[0].islower():
        flags.append("single_lowercase_token")
    return flags


def get_speaker_with_source(context, current_speaker=None):
    """Restituisce speaker e metodo usato per l'attribuzione."""
    speaker = get_speaker_regex(context)
    if speaker:
        return speaker, "regex"

    speaker = get_speaker_nlp(context)
    if speaker:
        return speaker, "nlp"

    if current_speaker:
        return current_speaker, "context"

    return "Sconosciuto", "unknown"


def attribute_speakers(segments):
    """Assegna speaker a ogni segmento con state tracking."""
    results = []
    current_speaker = None
    context_chain_length = 0
    for seg in segments:
        regex_details = get_speaker_regex_details(seg["context"], seg["start"], seg["context_start"])
        nlp_details = get_speaker_nlp_details(seg["context"], seg["start"], seg["context_start"])
        if regex_details:
            speaker = regex_details["speaker"]
            speaker_source = "regex"
            context_chain_length = 0
        elif nlp_details:
            speaker = nlp_details["speaker"]
            speaker_source = "nlp"
            context_chain_length = 0
        elif current_speaker:
            speaker = current_speaker
            speaker_source = "context"
            context_chain_length += 1
        else:
            speaker = "Sconosciuto"
            speaker_source = "unknown"
            context_chain_length = 0
        current_speaker = speaker
        seg["speaker"] = speaker
        seg["speaker_source"] = speaker_source
        seg["regex_candidate"] = regex_details["speaker"] if regex_details else ""
        seg["regex_verb"] = regex_details["verb"] if regex_details else ""
        seg["regex_distance"] = regex_details["distance"] if regex_details else ""
        seg["nlp_candidate"] = nlp_details["speaker"] if nlp_details else ""
        seg["nlp_verb"] = nlp_details["verb"] if nlp_details else ""
        seg["nlp_lemma"] = nlp_details["lemma"] if nlp_details else ""
        seg["nlp_distance"] = nlp_details["distance"] if nlp_details else ""
        seg["candidate_disagreement"] = bool(
            regex_details and nlp_details and regex_details["speaker"] != nlp_details["speaker"]
        )
        seg["attribution_distance"] = (
            regex_details["distance"] if speaker_source == "regex" and regex_details else
            nlp_details["distance"] if speaker_source == "nlp" and nlp_details else
            ""
        )
        seg["context_chain_length"] = context_chain_length if speaker_source == "context" else 0
        seg["candidate_verbs"] = collect_candidate_verbs(seg["context"])
        seg["speaker_quality_flags"] = speaker_quality_flags(speaker)
        logger.info(
            "Speaker attribution span_start=%s speaker=%s source=%s",
            seg["start"],
            speaker,
            speaker_source,
        )
        results.append(seg)
    return results


def process_text_with_speakers(tagged_text):
    """Unisce estrazione pronomi + attribuzione speaker."""
    segments = extract_speech_segments(tagged_text)
    attributed = attribute_speakers([segment for segment in segments if segment["is_valid"]])
    attributed_by_start = {segment["start"]: segment for segment in attributed}
    results = []
    for segment in segments:
        sp = segment["speech"]
        match = attributed_by_start.get(segment["start"])
        speaker = match["speaker"] if match else "Sconosciuto"
        speaker_source = match["speaker_source"] if match else "skipped"
        wc = segment["word_count"]
        question_count = sp.count("?")
        mio_mia_count = len(MIO_MIA_PATTERN.findall(sp))
        annotated, found = annotate_span(sp)
        results.append({
            "span_index": segment["span_index"],
            "original": sp,
            "annotated": annotated,
            "features": found,
            "speaker": speaker,
            "speaker_source": speaker_source,
            "word_count": wc,
            "question_count": question_count,
            "mio_mia_count": mio_mia_count,
            "is_valid_span": segment["is_valid"],
            "skip_reason": segment["skip_reason"],
            "regex_candidate": match["regex_candidate"] if match else "",
            "regex_verb": match["regex_verb"] if match else "",
            "regex_distance": match["regex_distance"] if match else "",
            "nlp_candidate": match["nlp_candidate"] if match else "",
            "nlp_verb": match["nlp_verb"] if match else "",
            "nlp_lemma": match["nlp_lemma"] if match else "",
            "nlp_distance": match["nlp_distance"] if match else "",
            "candidate_disagreement": match["candidate_disagreement"] if match else False,
            "attribution_distance": match["attribution_distance"] if match else "",
            "context_chain_length": match["context_chain_length"] if match else 0,
            "speaker_quality_flags": match["speaker_quality_flags"] if match else [],
            "candidate_verbs": match["candidate_verbs"] if match else collect_candidate_verbs(segment["context"]),
        })
    return results


# ─────────────────────────────────────────────────────────────
# CSV & Reporting Updates
# ─────────────────────────────────────────────────────────────
def write_pronoun_report(rows, csv_path):
    """Scrive CSV con pronomi + speaker + conteggio parole."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "file", "span_index", "speaker", "speaker_source", "word_count", "question_count", "mio_mia_count",
            "is_valid_span", "skip_reason", "original", "annotated", "features"
        ])
        for row in rows:
            features = "|".join(f"{tok}:{ana}" for tok, ana in row["features"])
            writer.writerow([
                row["file"], row["span_index"], row["speaker"], row["speaker_source"], row["word_count"], row["question_count"], row["mio_mia_count"],
                row["is_valid_span"], row["skip_reason"], row["original"], row["annotated"], features
            ])


def write_diagnostics_span_report(rows, csv_path):
    """Scrive diagnostica dettagliata per ogni span."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "file", "span_index", "word_count", "is_valid_span", "skip_reason",
            "speaker", "speaker_source", "context_chain_length",
            "regex_candidate", "regex_verb", "regex_distance",
            "nlp_candidate", "nlp_verb", "nlp_lemma", "nlp_distance",
            "candidate_disagreement", "attribution_distance",
            "speaker_quality_flags", "candidate_verbs", "original"
        ])
        for row in rows:
            candidate_verbs = "|".join(
                f"{item['form']}:{item['lemma']}" for item in row["candidate_verbs"]
            )
            writer.writerow([
                row["file"], row["span_index"], row["word_count"], row["is_valid_span"], row["skip_reason"],
                row["speaker"], row["speaker_source"], row["context_chain_length"],
                row["regex_candidate"], row["regex_verb"], row["regex_distance"],
                row["nlp_candidate"], row["nlp_verb"], row["nlp_lemma"], row["nlp_distance"],
                row["candidate_disagreement"], row["attribution_distance"],
                "|".join(row["speaker_quality_flags"]), candidate_verbs, row["original"]
            ])


def write_diagnostics_overview(rows, csv_path):
    """Scrive riepilogo diagnostico per file."""
    by_file = defaultdict(list)
    for row in rows:
        by_file[row["file"]].append(row)

    def source_span_count(items, source):
        return sum(1 for item in items if item["speaker_source"] == source)

    def source_word_count(items, source):
        return sum(item["word_count"] for item in items if item["speaker_source"] == source)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "file", "valid_spans", "skipped_spans", "total_words",
            "regex_spans", "regex_words", "nlp_spans", "nlp_words",
            "context_spans", "context_words", "unknown_spans", "unknown_words",
            "avg_context_chain", "max_context_chain", "candidate_disagreements"
        ])

        for file_name, items in sorted(by_file.items()):
            valid_items = [item for item in items if item["is_valid_span"]]
            context_lengths = [item["context_chain_length"] for item in valid_items if item["speaker_source"] == "context"]
            writer.writerow([
                file_name,
                len(valid_items),
                len(items) - len(valid_items),
                sum(item["word_count"] for item in valid_items),
                source_span_count(valid_items, "regex"),
                source_word_count(valid_items, "regex"),
                source_span_count(valid_items, "nlp"),
                source_word_count(valid_items, "nlp"),
                source_span_count(valid_items, "context"),
                source_word_count(valid_items, "context"),
                source_span_count(valid_items, "unknown"),
                source_word_count(valid_items, "unknown"),
                f"{sum(context_lengths)/len(context_lengths):.2f}" if context_lengths else "0.00",
                max(context_lengths) if context_lengths else 0,
                sum(1 for item in valid_items if item["candidate_disagreement"]),
            ])


def write_diagnostics_span_lengths(rows, csv_path):
    """Scrive istogramma delle lunghezze degli span e dei motivi di scarto."""
    histogram = defaultdict(lambda: {"valid": 0, "skipped": 0})
    skip_counts = defaultdict(int)
    for row in rows:
        bucket = row["word_count"] if row["word_count"] < 10 else "10+"
        key = str(bucket)
        if row["is_valid_span"]:
            histogram[key]["valid"] += 1
        else:
            histogram[key]["skipped"] += 1
            skip_counts[row["skip_reason"] or "unknown"] += 1

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["bucket", "valid_spans", "skipped_spans"])
        for bucket in sorted(histogram, key=lambda item: (item != "10+", int(item) if item.isdigit() else 10)):
            writer.writerow([bucket, histogram[bucket]["valid"], histogram[bucket]["skipped"]])
        writer.writerow([])
        writer.writerow(["skip_reason", "count"])
        for reason, count in sorted(skip_counts.items()):
            writer.writerow([reason, count])


def write_diagnostics_speaker_quality(rows, csv_path):
    """Scrive riepilogo speaker sospetti e frammentazione alias."""
    stats = defaultdict(lambda: {"spans": 0, "words": 0, "flags": set(), "files": set()})
    file_counts = defaultdict(lambda: defaultdict(int))
    for row in rows:
        if not row["is_valid_span"]:
            continue
        speaker = row["speaker"]
        stats[speaker]["spans"] += 1
        stats[speaker]["words"] += row["word_count"]
        stats[speaker]["flags"].update(row["speaker_quality_flags"])
        stats[speaker]["files"].add(row["file"])
        file_counts[row["file"]][speaker] += 1

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["speaker", "spans", "words", "flags", "file_count", "is_singleton"])
        for speaker, info in sorted(stats.items(), key=lambda item: (-item[1]["words"], item[0])):
            writer.writerow([
                speaker,
                info["spans"],
                info["words"],
                "|".join(sorted(info["flags"])),
                len(info["files"]),
                info["spans"] == 1,
            ])
        writer.writerow([])
        writer.writerow(["file", "unique_speakers", "singleton_speakers", "singleton_word_share"])
        for file_name, counts in sorted(file_counts.items()):
            singletons = {speaker for speaker, count in counts.items() if count == 1}
            total_words = sum(row["word_count"] for row in rows if row["file"] == file_name and row["is_valid_span"])
            singleton_words = sum(
                row["word_count"] for row in rows
                if row["file"] == file_name and row["speaker"] in singletons and row["is_valid_span"]
            )
            writer.writerow([
                file_name,
                len(counts),
                len(singletons),
                f"{singleton_words / total_words:.1%}" if total_words else "0.0%",
            ])


def write_diagnostics_speech_verbs(rows, csv_path):
    """Scrive frequenze dei verbi usati e candidati fuori lessico."""
    regex_hits = defaultdict(int)
    nlp_hits = defaultdict(int)
    missing_candidates = defaultdict(int)
    for row in rows:
        if row["regex_verb"]:
            regex_hits[row["regex_verb"].lower()] += 1
        if row["nlp_lemma"]:
            nlp_hits[row["nlp_lemma"]] += 1
        for candidate in row["candidate_verbs"]:
            missing_candidates[f"{candidate['form']}:{candidate['lemma']}"] += 1

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["kind", "verb", "count"])
        for verb, count in sorted(regex_hits.items(), key=lambda item: (-item[1], item[0])):
            writer.writerow(["regex_hit", verb, count])
        for lemma, count in sorted(nlp_hits.items(), key=lambda item: (-item[1], item[0])):
            writer.writerow(["nlp_hit", lemma, count])
        for candidate, count in sorted(missing_candidates.items(), key=lambda item: (-item[1], item[0])):
            writer.writerow(["missing_candidate", candidate, count])


def write_all_diagnostics(rows, output_dir):
    """Scrive tutti i report diagnostici per l'analisi speaker."""
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "span_report": diagnostics_dir / "speaker_diagnostics_spans.csv",
        "overview": diagnostics_dir / "speaker_diagnostics_overview.csv",
        "span_lengths": diagnostics_dir / "speaker_diagnostics_span_lengths.csv",
        "speaker_quality": diagnostics_dir / "speaker_diagnostics_speaker_quality.csv",
        "speech_verbs": diagnostics_dir / "speaker_diagnostics_speech_verbs.csv",
    }
    write_diagnostics_span_report(rows, paths["span_report"])
    write_diagnostics_overview(rows, paths["overview"])
    write_diagnostics_span_lengths(rows, paths["span_lengths"])
    write_diagnostics_speaker_quality(rows, paths["speaker_quality"])
    write_diagnostics_speech_verbs(rows, paths["speech_verbs"])
    return paths


def write_dialogue_summary(all_rows, summary_path):
    """Scrive riepilogo dialogo per file."""
    file_chars = defaultdict(lambda: defaultdict(lambda: {"word_count": 0, "question_count": 0, "mio_mia_count": 0}))
    
    for row in all_rows:
        if not row["is_valid_span"]:
            continue
        file_chars[row["file"]][row["speaker"]]["word_count"] += row["word_count"]
        file_chars[row["file"]][row["speaker"]]["question_count"] += row["question_count"]
        file_chars[row["file"]][row["speaker"]]["mio_mia_count"] += row["mio_mia_count"]

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "file",
            "character",
            "word_count",
            "word_percentage",
            "question_count",
            "question_percentage",
            "mio_mia_count",
            "mio_mia_percentage",
        ])
        
        # Per-file totals
        for fname, chars in sorted(file_chars.items()):
            file_total = sum(stats["word_count"] for stats in chars.values())
            question_total = sum(stats["question_count"] for stats in chars.values())
            mio_mia_total = sum(stats["mio_mia_count"] for stats in chars.values())
            for char, stats in sorted(chars.items(), key=lambda x: -x[1]["word_count"]):
                writer.writerow([
                    fname,
                    char,
                    stats["word_count"],
                    f"{stats['word_count']/file_total:.1%}" if file_total else "0.0%",
                    stats["question_count"],
                    f"{stats['question_count']/question_total:.1%}" if question_total else "0.0%",
                    stats["mio_mia_count"],
                    f"{stats['mio_mia_count']/mio_mia_total:.1%}" if mio_mia_total else "0.0%",
                ])


def annotate_text_pronouns(text):
    """Annota i pronomi all'interno di tutti gli span di discorso diretto."""
    def repl(match):
        annotated, _ = annotate_span(match.group(1))
        return f"<sp>{annotated}</sp>"
    return re.sub(r"<sp>(.*?)</sp>", repl, text, flags=re.DOTALL)


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

        # Speaker + dialogue extraction
        file_results = process_text_with_speakers(tagged)
        for item in file_results:
            item["file"] = path.name
            report_rows.append(item)

        target_path = output_dir / path.name
        target_path.write_text(annotated_text, encoding="utf-8")
        processed.append(target_path)

    report_path = output_dir / "dialogue_report.csv"
    summary_path = output_dir / "dialogue_summary.csv"
    write_pronoun_report(report_rows, report_path)
    write_dialogue_summary(report_rows, summary_path)
    diagnostics_paths = write_all_diagnostics(report_rows, output_dir)

    return processed, report_path, summary_path, diagnostics_paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    source_dir = Path(__file__).resolve().parent / "input_dir"
    target_dir = Path(__file__).resolve().parent / "output_tagged"
    print(f"Analisi file da: {source_dir}")
    print(f"Salvo output in: {target_dir}")
    processed, report_path, summary_path, diagnostics_paths = analyze_directory(source_dir, target_dir)
    print(f"Analisi completata. {len(processed)} file elaborati.")
    print(f"Report pronomi: {report_path}")
    print(f"Riepilogo dialogo: {summary_path}")
    print("Diagnostica speaker:")
    for path in diagnostics_paths.values():
        print(f"- {path}")