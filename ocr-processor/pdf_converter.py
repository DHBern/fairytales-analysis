import os
import glob
import shutil
from pathlib import Path
from pdf2image import convert_from_path


def clear_directory(dir_path):
    """Clear all contents of a directory."""
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)


def convert_pdfs(pdf_dir, image_dir, dpi=300):
    """
    Convert PDF files to JPEG images.

    Args:
        pdf_dir (str): Directory containing PDF files
        image_dir (str): Directory to save JPEG images
        dpi (int): Resolution for conversion (default 300)
    """
    clear_directory(image_dir)

    pdf_paths = glob.glob(os.path.join(pdf_dir, "*.pdf"))

    if not pdf_paths:
        print(f"No PDF files found in {pdf_dir}.")
        return []

    print(f"Converting {len(pdf_paths)} PDF files to JPEG...")

    converted_files = []

    for pdf_path in pdf_paths:
        try:
            pdf_name = Path(pdf_path).stem
            print(f"Converting {pdf_name}.pdf...")

            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=dpi, fmt='jpeg')

            # Save each page as JPEG
            for i, image in enumerate(images, start=1):
                image_filename = f"{pdf_name}-{i}.jpg"
                image_path = os.path.join(image_dir, image_filename)
                image.save(image_path, 'JPEG')
                converted_files.append(image_path)
                print(f"  Saved: {image_filename}")

        except Exception as e:
            print(f"Failed to convert {pdf_path}: {e}")

    print(f"Conversion complete. {len(converted_files)} images created.")
    return converted_files


if __name__ == "__main__":
    # For testing
    convert_pdfs("pdfs", "images")