#!/usr/bin/env python3

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import google.api_core.exceptions
import google.generativeai as genai


# Constants
MODEL_NAME = "gemini-2.5-flash-preview-05-20"
MAX_CONCURRENT_TRANSLATIONS = 5
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds


def log(msg: str):
    """Log a message with [HH:MM] timestamp."""
    timestamp = datetime.now().strftime("%H:%M")
    print(f"[{timestamp}] {msg}")


class Config:
    """Holds resolved configuration values."""

    def __init__(self, novel_root: Path, args: argparse.Namespace):
        self.novel_root = novel_root
        self.cli = args
        self._load_config_file()
        self._resolve_api_key()
        self._resolve_base_prompt()
        self._resolve_folders()

    def _load_config_file(self):
        self.config_path = self.novel_root / "config.json"
        self.raw_config = {}
        if self.config_path.exists():
            try:
                with self.config_path.open(encoding="utf-8") as f:
                    self.raw_config = json.load(f)
                log(f"Loaded configuration from {self.config_path}")
            except json.JSONDecodeError:
                log(f"Warning: Could not parse {self.config_path}; ignoring.")
            except Exception as e:
                log(f"Warning: Error reading {self.config_path}: {e}; ignoring.")
        else:
            log(f"No config.json at {self.config_path}; using defaults.")

    def _resolve_api_key(self):
        if self.cli.api_key:
            self.api_key = self.cli.api_key
            log("Using API key from CLI argument.")
        else:
            self.api_key = self.raw_config.get("api_key")
            if self.api_key:
                log("Using API key from config file.")
        if not self.api_key:
            log("Error: API key not provided via CLI or config.")
            sys.exit(1)

    def _resolve_base_prompt(self):
        if self.raw_config.get("base_prompt"):
            self.base_prompt = self.raw_config["base_prompt"]
            log(f"Using base_prompt from config: '{self.base_prompt}'")
        elif self.cli.base_prompt:
            self.base_prompt = self.cli.base_prompt
            log(f"Using base_prompt from CLI/default: '{self.base_prompt}'")
        else:
            self.base_prompt = "Translate the following text to English:"
            log(f"Using default base_prompt: '{self.base_prompt}'")

    def _resolve_folders(self):
        # Raw folder
        if self.cli.raw_folder:
            raw = Path(self.cli.raw_folder)
            log(f"Using raw_folder from CLI: {raw}")
        else:
            raw_rel = self.raw_config.get("raw_folder", "raw")
            raw = self.novel_root / raw_rel
            log(f"Using raw_folder from config/default: {raw}")
        self.raw_folder = raw.resolve()
        # Translated folder
        if self.cli.translated_folder:
            tl = Path(self.cli.translated_folder)
            log(f"Using translated_folder from CLI: {tl}")
        else:
            tl_rel = self.raw_config.get("translated_folder", "translated")
            tl = self.novel_root / tl_rel
            log(f"Using translated_folder from config/default: {tl}")
        self.translated_folder = tl.resolve()


def translate_text(text: str, api_key: str, base_prompt: str) -> str:
    """Call Gemini API to translate text with retry logic."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"{base_prompt}\n\n{text}"

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = model.generate_content(prompt)
            return response.text
        except google.api_core.exceptions.InternalServerError as e:
            log(f"Attempt {attempt}/{RETRY_ATTEMPTS} failed: {e}")
            if attempt < RETRY_ATTEMPTS:
                log(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
        except Exception as e:
            log(f"Unexpected error: {e}")
            break
    log("Failed to translate after multiple attempts.")
    raise RuntimeError("Translation failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate novel chapters using Gemini API."
    )
    parser.add_argument(
        "novel_directory",
        help="Path to novel root directory containing config.json and chapters.",
    )
    parser.add_argument(
        "--api_key", help="Google AI Studio API Key (overrides config)."
    )
    parser.add_argument(
        "--raw_folder",
        help="Path to raw chapter files (overrides config; default '<novel>/raw').",
    )
    parser.add_argument(
        "--translated_folder",
        help="Where to save translations (overrides config; default '<novel>/translated').",
    )
    parser.add_argument(
        "--base_prompt",
        help="Base prompt for translation (overrides config).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    novel_root = Path(args.novel_directory).resolve()
    if not novel_root.is_dir():
        log(f"Error: Novel directory not found: {novel_root}")
        sys.exit(1)

    cfg = Config(novel_root, args)

    if not cfg.raw_folder.is_dir():
        log(f"Error: Raw folder not found: {cfg.raw_folder}")
        sys.exit(1)

    cfg.translated_folder.mkdir(parents=True, exist_ok=True)
    log(f"Translations will be saved to: {cfg.translated_folder}")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TRANSLATIONS) as executor:
        futures = {}
        for txt_file in cfg.raw_folder.glob("*.txt"):
            dest_file = cfg.translated_folder / txt_file.name
            if dest_file.exists():
                log(f"Skipping already translated: {txt_file.name}")
                continue
            content = txt_file.read_text(encoding="utf-8")
            log(f"Queueing for translation: {txt_file.name}")
            future = executor.submit(
                translate_text, content, cfg.api_key, cfg.base_prompt
            )
            futures[future] = dest_file

        for future in as_completed(futures):
            dest_path = futures[future]
            try:
                result = future.result()
                dest_path.write_text(result, encoding="utf-8")
                log(f"Saved translation: {dest_path.name}")
            except Exception as e:
                log(f"Error translating {dest_path.name}: {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user. Exiting.")
        sys.exit(0)
