# Changelog

## [v3.5] - 2025-05-09
### Added
- `--use-mtime-fallback`: builds full timestamp from file modification time when only time (e.g., 21:15:00) is detected
- Raw OCR dumps saved to `ocr_dumps/` for inspection and debugging
- Frame offset included in `timestamp_map.csv` output

### Fixed
- Avoids counting multiple partial time matches per file (cleaner stats)
- Better handling of files that had OCR near-success

### Improved
- Logging clarity during frame sampling and fallback logic
- Summary accuracy in `wyze_rename.log`

