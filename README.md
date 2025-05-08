# wyze_renamer
# Wyze Video Timestamp Renamer


A Python script that uses FFmpeg, OpenCV, and Tesseract OCR to extract timestamps from Wyze video clips and rename the files accordingly.

## Features

- Extracts timestamp from the first visible overlay in the video.
- Samples multiple frames (configurable via `--frame-depth`) for better OCR accuracy.
- Automatically corrects malformed OCR years (e.g. 5025 → 2025).
- Logs everything and tracks failed attempts.
- Generates `.csv` mapping and `.bak` file for failed OCRs.

## Requirements

- Python 3.8+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and available in your PATH.
- FFmpeg installed and available in your PATH.

## Install

```bash
python3 -m venv wyze_env
source wyze_env/bin/activate
pip install -r requirements.txt

