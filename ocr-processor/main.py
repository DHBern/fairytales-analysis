# main.py
import argparse
import os
import glob
import shutil
from pathlib import Path
from config import INPUT_DIR, OUTPUT_DIR, PDF_DIR
import sys
from ocr_processor import ocr_image
from evaluate_ocr import merge_collections, evaluate_all
from pdf_converter import convert_pdfs


OCR_PROCESSOR_DIR = Path(__file__).resolve().parent
DEFAULT_GT_DIR = OCR_PROCESSOR_DIR / "gt"
DEFAULT_REPORT_CSV = OCR_PROCESSOR_DIR / "reports" / "cer.csv"


def clear_directory(dir_path):
    """Clear all contents of a directory."""
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)


def process_images(input_dir, output_dir):
    clear_directory(output_dir)

    image_extensions = [".jpg", ".jpeg", ".png", ".tiff", ".webp"]
    image_paths = []
    for ext in image_extensions:
        image_paths.extend(glob.glob(os.path.join(input_dir, f"*{ext}")))

    if not image_paths:
        print(f"No images found in {input_dir}.")
        return []

    print(f"Processing {len(image_paths)} images...")
    output_files = []

    for image_path in image_paths:
        try:
            filename = Path(image_path).stem
            output_path = os.path.join(output_dir, f"{filename}.txt")

            text = ocr_image(image_path)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)

            output_files.append(output_path)
            print(f"Done: {filename} → {output_path}")
        except Exception as e:
            print(f"Failed: {image_path} → {e}")

    return output_files


def main():
    parser = argparse.ArgumentParser(description="OCR + merge + CER evaluation workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser("convert", help="Convert PDF files to JPEG images")
    convert.add_argument("--input", default=PDF_DIR, help="Directory containing PDF files")
    convert.add_argument("--output", default=INPUT_DIR, help="Directory for output JPEG images")
    convert.add_argument("--dpi", type=int, default=300, help="Resolution for PDF conversion (default 300)")

    proc = sub.add_parser("ocr", help="Run OCR on images")
    proc.add_argument("--input", default=INPUT_DIR, help="Directory containing input images")
    proc.add_argument("--output", default=OUTPUT_DIR, help="Directory for OCR output text files")

    merge = sub.add_parser("merge", help="Merge OCR text files with common stem")
    merge.add_argument("--inputs", default=OUTPUT_DIR, help="Directory containing OCR text files")
    merge.add_argument("--output", default=os.path.join(OUTPUT_DIR, "merged"), help="Directory for merged text files")

    evaluate = sub.add_parser("evaluate", help="Evaluate OCR merged text against ground truth")
    evaluate.add_argument("--merged", default=os.path.join(OUTPUT_DIR, "merged"), help="Merged OCR output directory")
    evaluate.add_argument("--manual", default=str(DEFAULT_GT_DIR), help="Ground truth text directory")
    evaluate.add_argument("--csv", default=str(DEFAULT_REPORT_CSV), help="CER report CSV path")


#    all_cmd = sub.add_parser("all", help="Run full pipeline: OCR → merge → evaluate")
#    all_cmd.add_argument("--input", default=INPUT_DIR, help="Directory containing input images")
#    all_cmd.add_argument("--output", default=OUTPUT_DIR, help="Directory for OCR output text files")
#    all_cmd.add_argument("--merged", default=os.path.join(OUTPUT_DIR, "merged"), help="Directory for merged text files")
#    all_cmd.add_argument("--manual", default="gt", help="Ground truth text directory")
#    all_cmd.add_argument("--csv", default="reports/cer.csv", help="CER report CSV path")

    args = parser.parse_args()

    # Always resolve all paths to absolute paths
    def abspath(path):
        return os.path.abspath(os.path.expanduser(path))

    if args.command == "convert":
        convert_pdfs(abspath(args.input), abspath(args.output), dpi=args.dpi)
    elif args.command == "ocr":
        process_images(abspath(args.input), abspath(args.output))
    elif args.command == "merge":
        merge_collections(abspath(args.inputs), abspath(args.output))
    elif args.command == "evaluate":
        evaluate_all(abspath(args.merged), abspath(args.manual), output_csv=abspath(args.csv))
    elif args.command == "all":
        print("Step 1: OCR processing...")
        process_images(abspath(args.input), abspath(args.output))
        print("\nStep 2: Merging outputs...")
        merge_collections(abspath(args.output), abspath(args.merged))
        print("\nStep 3: Evaluating CER...")
        evaluate_all(abspath(args.merged), abspath(args.manual), output_csv=abspath(args.csv))
        print(f"\nPipeline complete. Report: {args.csv}")


if __name__ == "__main__":
    main()
