import os
import re
import subprocess
import argparse
import logging
import csv
import cv2
from pathlib import Path

# Constants
TESSERACT_CMD = 'tesseract'
TESSERACT_TIMEOUT = 10
FFMPEG_TIMEOUT = 10
BAK_LOG = "failed_ocr.bak"
CSV_LOG = "timestamp_map.csv"
FAILED_FRAME_DIR = "failed_frames"

# Counters
results = {
    "examined": 0,
    "renamed": 0,
    "failed": 0,
    "corrected_year": 0,
    "partial_time_only": 0
}

# Prepare logs and folders
os.makedirs(FAILED_FRAME_DIR, exist_ok=True)
open(BAK_LOG, 'w').close()
open(CSV_LOG, 'w').close()

def preprocess_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        logging.error(f"Failed to load image: {image_path}")
        return image_path

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    cropped = gray[int(height * 0.85):, int(width * 0.6):]
    resized = cv2.resize(cropped, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    _, thresh = cv2.threshold(resized, 128, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    denoised = cv2.fastNlMeansDenoising(thresh, None, 30, 7, 21)

    processed_path = str(image_path).replace(".jpg", "_processed.jpg")
    cv2.imwrite(processed_path, denoised)
    return processed_path

def extract_timestamp(image_path, fallback_name=None):
    processed_path = preprocess_image(image_path)

    try:
        os.remove('output.txt')
    except FileNotFoundError:
        pass

    try:
        subprocess.run(
            [TESSERACT_CMD, processed_path, 'output', '-c', 'tessedit_char_whitelist=0123456789:- ', '--psm', '6'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=TESSERACT_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        logging.error(f"Tesseract timed out on {processed_path}")
        return None

    try:
        with open('output.txt', 'r') as f:
            text = f.read().strip()
        logging.debug(f"OCR output: {repr(text)}")
        text = re.sub(r'[\r\n]+', ' ', text)

        match = re.search(r'(\d{4})[-/: ]?(\d{2})[-/: ]?(\d{2})[ :T]?(\d{2})[: ]?(\d{2})[: ]?(\d{2})', text)
        if match:
            year = int(match.group(1))
            if 1980 <= year <= 2100:
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)} {match.group(4)}:{match.group(5)}:{match.group(6)}"
            elif match.group(1).endswith("025"):
                corrected = f"2025-{match.group(2)}-{match.group(3)} {match.group(4)}:{match.group(5)}:{match.group(6)}"
                results["corrected_year"] += 1
                logging.warning(f"Corrected unrealistic year {year} to 2025")
                return corrected
            else:
                logging.warning(f"Unrealistic year in OCR: {year}")

        time_only = re.search(r'(\d{2})[: ]?(\d{2})[: ]?(\d{2})', text)
        if time_only:
            results["partial_time_only"] += 1
            logging.warning("Only time found, no date: " + time_only.group(0))
    except Exception as e:
        logging.error(f"OCR processing failed: {e}")

    if fallback_name:
        failed_path = os.path.join(FAILED_FRAME_DIR, f"{fallback_name}.jpg")
        try:
            os.rename(processed_path, failed_path)
        except Exception:
            pass

    return None

def extract_frame(video_path, output_path, offset):
    try:
        subprocess.run(
            ['ffmpeg', '-ss', str(offset), '-i', str(video_path), '-frames:v', '1', str(output_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=FFMPEG_TIMEOUT
        )
        return True
    except subprocess.TimeoutExpired:
        logging.error(f"FFmpeg timed out extracting frame at {offset}s from {video_path}")
        return False

def rename_video(video_path, dry_run=False, frame_depth=1.5):
    results["examined"] += 1
    video_path = Path(video_path)

    frame_offsets = [round(x * 0.5, 1) for x in range(int(frame_depth / 0.5) + 1)]

    for offset in frame_offsets:
        frame_path = video_path.parent / f'frame_{int(offset*10)}.jpg'
        if not extract_frame(video_path, frame_path, offset):
            continue

        timestamp = extract_timestamp(frame_path, fallback_name=video_path.stem)
        frame_path.unlink(missing_ok=True)

        if timestamp:
            formatted = timestamp.replace(':', '-').replace(' ', '_')
            new_path = video_path.with_name(f"{formatted}{video_path.suffix}")

            with open(CSV_LOG, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([str(video_path), timestamp, f"{offset:.1f}s"])

            if dry_run:
                logging.info(f"[DRY-RUN] Would rename to: {new_path.name} (frame at {offset:.1f}s)")
            else:
                try:
                    os.rename(video_path, new_path)
                    logging.info(f"Renamed: {video_path.name} -> {new_path.name} (frame at {offset:.1f}s)")
                    results["renamed"] += 1
                except Exception as e:
                    logging.error(f"Rename failed: {e}")
                    results["failed"] += 1
            return

    logging.warning(f"Failed to find timestamp for {video_path}")
    with open(BAK_LOG, 'a') as bakfile:
        bakfile.write(str(video_path) + '\n')
    results["failed"] += 1

def process_directory(start_path, dry_run=False, frame_depth=1.5):
    logging.info(f"Scanning folder: {start_path}")
    for root, _, files in os.walk(start_path):
        for file in files:
            if file.lower().endswith(".mp4"):
                rename_video(os.path.join(root, file), dry_run=dry_run, frame_depth=frame_depth)

    logging.info("---------- SUMMARY ----------")
    logging.info(f"Total files examined: {results['examined']}")
    logging.info(f"Successfully renamed: {results['renamed']}")
    logging.info(f"Failed to extract timestamp: {results['failed']}")
    logging.info(f"Timestamps with corrected years: {results['corrected_year']}")
    logging.info(f"Timestamps with only time (no date): {results['partial_time_only']}")

def setup_logging(verbose: bool):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("wyze_rename.log", mode='a')
        ]
    )

def main():
    parser = argparse.ArgumentParser(description="Wyze Video Timestamp Renamer v3.4 (Deep Frame Sampling)")
    parser.add_argument("start_path", help="Directory to scan")
    parser.add_argument("--dry-run", action="store_true", help="Simulate file renaming")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--frame-depth", type=float, default=1.5, help="Max seconds into video to sample frames (default: 1.5)")
    args = parser.parse_args()

    setup_logging(args.verbose)
    process_directory(args.start_path, dry_run=args.dry_run, frame_depth=args.frame_depth)

if __name__ == "__main__":
    main()

