import argparse
import difflib
import os
import re
import shutil
from pathlib import Path


OCR_PROCESSOR_DIR = Path(__file__).resolve().parent
DEFAULT_GT_DIR = OCR_PROCESSOR_DIR / "gt"
DEFAULT_REPORT_CSV = OCR_PROCESSOR_DIR / "reports" / "cer.csv"


def clear_directory(dir_path):
    """Clear all contents of a directory."""
    print(f"[LOG] Clearing and creating directory: {dir_path}")
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)


def collect_txt_files(base_dir):
    base_path = Path(base_dir)
    if not base_path.exists():
        raise FileNotFoundError(f"Directory does not exist: {base_dir}")
    return sorted([p for p in base_path.rglob("*.txt") if p.is_file()])


def merge_text_files(paths, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    merged = []
    for p in paths:
        text = p.read_text(encoding="utf-8", errors="replace")
        merged.append(text.strip())

    merged_text = "\n\n".join(merged).strip() + "\n"
    output_path.write_text(merged_text, encoding="utf-8")
    return output_path


def levenshtein_distance(a, b):
    # character-level Levenshtein distance
    if a == b:
        return 0
    if len(a) == 0:
        return len(b)
    if len(b) == 0:
        return len(a)

    prev_row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        row = [i]
        for j, cb in enumerate(b, start=1):
            insertions = prev_row[j] + 1
            deletions = row[j - 1] + 1
            substitutions = prev_row[j - 1] + (ca != cb)
            row.append(min(insertions, deletions, substitutions))
        prev_row = row
    return prev_row[-1]


def character_error_rate(hypothesis, reference):
    ref = reference.replace("\r\n", "\n")
    hyp = hypothesis.replace("\r\n", "\n")

    ref = ref.strip()
    hyp = hyp.strip()

    if len(ref) == 0:
        if len(hyp) == 0:
            return 0.0
        return 100.0

    distance = levenshtein_distance(hyp, ref)
    return distance / len(ref) * 100


def normalize_stem(stem):
    """Group stems like name-1, name_2, name-3 into name."""
    m = re.match(r"^(.*?)(?:[-_]\d+)+$", stem)
    if m:
        return m.group(1)
    return stem


def merge_collections(inputs_dir, merged_dir):
    clear_directory(merged_dir)
    files = collect_txt_files(inputs_dir)
    print(f"[LOG] Found {len(files)} .txt files in {inputs_dir}")
    groups = {}

    def extract_page_number(path):
        # Match -N or _N at end of stem, return int(N), else 0
        m = re.search(r"[-_](\d+)$", path.stem)
        return int(m.group(1)) if m else 0

    for f in files:
        stem = normalize_stem(f.stem)
        groups.setdefault(stem, []).append(f)

    output_paths = []
    for stem, paths in sorted(groups.items()):
        # Sort paths by page number
        paths_sorted = sorted(paths, key=extract_page_number)
        merged_file = Path(merged_dir) / f"{stem}.txt"
        merge_text_files(paths_sorted, merged_file)
        output_paths.append(merged_file)
        print(f"Merged {len(paths_sorted)} file(s) into {merged_file}")

    return output_paths


def evaluate_all(merged_dir, manual_dir, output_csv=None):
    if output_csv:
        clear_directory(str(Path(output_csv).parent))
    merged_files = collect_txt_files(merged_dir)
    results = []
    detailed_output = []
    skipped_files = []

    for merged_path in merged_files:
        manual_path = Path(manual_dir) / merged_path.name
        if not manual_path.exists():
            print(f"Skipping {merged_path}: manual file not found at {manual_path}")
            skipped_files.append((merged_path.name, str(manual_path)))
            continue

        hyp = merged_path.read_text(encoding="utf-8", errors="replace")
        ref = manual_path.read_text(encoding="utf-8", errors="replace")

        distance = levenshtein_distance(hyp, ref)
        cer = character_error_rate(hyp, ref)
        results.append((merged_path.name, cer, len(ref), len(hyp)))
        print(f"{merged_path.name}: CER={cer:.2f}% (distance={distance}, ref_len={len(ref)}, hyp_len={len(hyp)})")

        # Collect detailed output
        detailed_output.append(f"=== {merged_path.name} ===")
        detailed_output.append(f"CER: {cer:.2f}% (distance={distance}, ref_len={len(ref)}, hyp_len={len(hyp)})")
        detailed_output.append(f"Reference preview: {ref[:200]}{'...' if len(ref) > 200 else ''}")
        detailed_output.append(f"Hypothesis preview: {hyp[:200]}{'...' if len(hyp) > 200 else ''}")
        
        # Show differences
        matcher = difflib.SequenceMatcher(None, ref, hyp)
        count = 0
        max_diffs = 50
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal' and count < max_diffs:
                ref_part = ref[i1:i2][:100]
                hyp_part = hyp[j1:j2][:100]
                detailed_output.append(f"  {tag.upper()}: ref='{ref_part}' hyp='{hyp_part}'")
                count += 1
            elif count >= max_diffs:
                detailed_output.append(f"  ... (stopped after {max_diffs} differences)")
                break
        detailed_output.append("")

    if not results:
        print(
            f"No comparable OCR/manual file pairs found in {merged_dir} against {manual_dir}. "
            f"Skipped {len(skipped_files)} file(s)."
        )
    else:
        print(f"Evaluated {len(results)} file(s); skipped {len(skipped_files)} file(s).")

    if output_csv:
        output_csv_path = Path(output_csv)
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_csv, "w", encoding="utf-8") as f:
            f.write("file,cer_percent,reference_len,hypothesis_len\n")
            for name, cer, ref_len, hyp_len in results:
                f.write(f"{name},{cer:.2f},{ref_len},{hyp_len}\n")
        print(f"Wrote report to {output_csv}")

        # Write detailed output to file
        detailed_file = output_csv_path.parent / "evaluation_detailed.txt"
        with open(detailed_file, "w", encoding="utf-8") as f:
            f.write("\n".join(detailed_output))
        print(f"Wrote detailed differences to {detailed_file}")

    return results


def main():
    parser = argparse.ArgumentParser(description="OCR merge + CER evaluation")
    sub = parser.add_subparsers(dest="command", required=True)

    merge_parser = sub.add_parser("merge", help="Merge all same-stem .txt files from inputs into merged outputs")
    merge_parser.add_argument("--inputs", default="outputs", help="Root folder where txt files are located")
    merge_parser.add_argument("--output", default="outputs/merged", help="Where merged files are written")

    eval_parser = sub.add_parser("evaluate", help="Evaluate CER between merged output and manual references")
    eval_parser.add_argument("--merged", default="outputs/merged", help="Folder with merged OCR outputs")
    eval_parser.add_argument("--manual", default=str(DEFAULT_GT_DIR), help="Folder with manual corrected text files")
    eval_parser.add_argument("--csv", default=str(DEFAULT_REPORT_CSV), help="CSV report output path")

    args = parser.parse_args()

    if args.command == "merge":
        merge_collections(args.inputs, args.output)
    elif args.command == "evaluate":
        evaluate_all(args.merged, args.manual, output_csv=args.csv)


if __name__ == "__main__":
    main()
