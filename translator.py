#!/usr/bin/env python3
"""
Novel Chapter Translator CLI Tool

This script provides a command-line interface for translating novel chapters using
the Google Gemini API. It supports sequential translation with smart glossary
management, retry logic, and per-novel configuration through JSON files.

Features:
- Sequential translation of multiple .txt files for optimal glossary progression
- Configurable translation prompts per novel
- Smart glossary management with progressive learning
- Automatic retry on API failures
- Skip already translated chapters
- Per-novel API key and folder configuration

Author: Novel Translator CLI
License: MIT
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import google.api_core.exceptions
import google.generativeai as genai


# Configuration constants
MODEL_NAME = "gemini-2.5-flash-preview-05-20"  # Gemini model to use for translation
RETRY_ATTEMPTS = 3  # Number of retry attempts for failed API calls
RETRY_DELAY = 5  # Delay in seconds between retry attempts
GLOSSARY_INIT_CHAPTERS = 5  # Number of initial chapters to use for glossary generation
MAX_GLOSSARY_ENTRIES = (
    1000  # Maximum number of entries to keep in glossary (focused on key terms)
)


def log(msg: str):
    """
    Log a message with timestamp to stdout.

    Formats and prints a message with the current time in [HH:MM] format.
    Used throughout the application for consistent logging.

    Args:
        msg (str): The message to log

    Example:
        log("Starting translation process")
        # Output: [14:30] Starting translation process
    """
    timestamp = datetime.now().strftime("%H:%M")
    print(f"[{timestamp}] {msg}")


class Config:
    """
    Configuration manager for novel translation settings.

    This class handles loading configuration from config.json files and resolving
    final settings by merging CLI arguments, config file values, and defaults.

    The priority order for settings is:
    1. CLI arguments (highest priority)
    2. config.json values
    3. Built-in defaults (lowest priority)

    Attributes:
        novel_root (Path): Root directory of the novel
        cli (argparse.Namespace): Parsed CLI arguments
        config_path (Path): Path to the config.json file
        raw_config (dict): Raw configuration data from JSON file
        api_key (str): Resolved Google AI Studio API key
        base_prompt (str): Resolved translation prompt
        raw_folder (Path): Resolved path to raw chapter files
        translated_folder (Path): Resolved path for translated output
        glossary_path (Path): Path to the glossary.txt file
        glossary (dict): Current glossary terms and definitions
    """

    def __init__(self, novel_root: Path, args: argparse.Namespace):
        """
        Initialize configuration by loading and resolving all settings.

        Args:
            novel_root (Path): Path to the novel's root directory
            args (argparse.Namespace): Parsed command-line arguments
        """
        self.novel_root = novel_root
        self.cli = args
        self._load_config_file()
        self._resolve_api_key()
        self._resolve_base_prompt()
        self._resolve_folders()
        self._setup_glossary()

    def _load_config_file(self):
        """
        Load configuration from config.json file in the novel directory.

        Attempts to load and parse the config.json file. If the file doesn't exist
        or cannot be parsed, falls back to empty configuration and logs warnings.
        Sets self.raw_config with the loaded JSON data or empty dict.
        """
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
        """
        Resolve the Google AI Studio API key from CLI args or config file.

        Priority order:
        1. CLI argument --api_key
        2. "api_key" field in config.json

        Exits the program if no API key is found, as it's required for translation.
        Sets self.api_key with the resolved API key string.
        """
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
        """
        Resolve the base translation prompt from config file, CLI args, or default.

        Priority order:
        1. "base_prompt" field in config.json (highest priority)
        2. CLI argument --base_prompt
        3. Built-in default prompt (lowest priority)

        The base prompt is sent to the Gemini API before each chapter text
        to instruct how the translation should be performed.
        Sets self.base_prompt with the resolved prompt string.
        """
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
        """
        Resolve the raw and translated folder paths from various sources.

        For both raw_folder and translated_folder:
        Priority order:
        1. CLI arguments --raw_folder / --translated_folder
        2. "raw_folder" / "translated_folder" fields in config.json
        3. Built-in defaults: "raw" and "translated"

        CLI paths can be absolute or relative to current working directory.
        Config paths are always relative to the novel root directory.

        Sets self.raw_folder and self.translated_folder as resolved Path objects.
        """
        # Resolve raw folder path
        if self.cli.raw_folder:
            raw = Path(self.cli.raw_folder)
            log(f"Using raw_folder from CLI: {raw}")
        else:
            raw_rel = self.raw_config.get("raw_folder", "raw")
            raw = self.novel_root / raw_rel
            log(f"Using raw_folder from config/default: {raw}")
        self.raw_folder = raw.resolve()

        # Resolve translated folder path
        if self.cli.translated_folder:
            tl = Path(self.cli.translated_folder)
            log(f"Using translated_folder from CLI: {tl}")
        else:
            tl_rel = self.raw_config.get("translated_folder", "translated")
            tl = self.novel_root / tl_rel
            log(f"Using translated_folder from config/default: {tl}")
        self.translated_folder = tl.resolve()

    def _setup_glossary(self):
        """
        Set up glossary path and load existing glossary if available.

        Initializes the glossary system by:
        1. Setting the glossary file path (glossary.txt in novel root)
        2. Loading existing glossary from file if it exists
        3. Initializing empty glossary dict if file doesn't exist

        Sets self.glossary_path and self.glossary attributes.
        """
        self.glossary_path = self.novel_root / "glossary.txt"
        self.glossary = self._load_glossary()

        if self.glossary:
            log(f"Loaded glossary with {len(self.glossary)} entries")
        else:
            log("No existing glossary found - will generate from initial chapters")

    def _load_glossary(self) -> dict:
        """
        Load glossary entries from glossary.txt file.

        Returns:
            dict: Dictionary mapping terms to their definitions/descriptions.
                 Empty dict if file doesn't exist or cannot be parsed.
        """
        if not self.glossary_path.exists():
            return {}

        try:
            glossary = {}
            content = self.glossary_path.read_text(encoding="utf-8")

            for line in content.strip().split("\n"):
                if line.strip() and ":" in line:
                    term, definition = line.split(":", 1)
                    glossary[term.strip()] = definition.strip()

            return glossary
        except Exception as e:
            log(f"Warning: Error loading glossary: {e}")
            return {}

    def save_glossary(self):
        """
        Save current glossary to glossary.txt file.

        Writes the glossary dictionary to file in a simple format:
        term: definition

        Preserves original order and limits to MAX_GLOSSARY_ENTRIES.
        """
        try:
            # Limit entries if needed (keep first entries, not sorted)
            items = list(self.glossary.items())
            if len(items) > MAX_GLOSSARY_ENTRIES:
                items = items[:MAX_GLOSSARY_ENTRIES]
                self.glossary = dict(items)

            # Write to file in current order
            lines = [f"{term}: {definition}" for term, definition in items]
            content = "\n".join(lines) + "\n"
            self.glossary_path.write_text(content, encoding="utf-8")

            log(f"Saved glossary with {len(items)} entries")
        except Exception as e:
            log(f"Warning: Error saving glossary: {e}")

    def get_glossary_text(self) -> str:
        """
        Get formatted glossary text for inclusion in translation prompts.

        Returns:
            str: Formatted glossary text ready for AI prompt inclusion.
                 Empty string if no glossary entries exist.
        """
        if not self.glossary:
            return ""

        lines = ["CRITICAL TERMS GLOSSARY (maintain exact consistency):"]
        for term, definition in self.glossary.items():
            lines.append(f"- {term}: {definition}")
        lines.append(
            "\nIMPORTANT: Use these exact name/term translations consistently. Do not change or translate names that appear in this glossary."
        )
        lines.append("")  # Empty line after glossary

        return "\n".join(lines)


def generate_glossary_from_text(
    text: str, api_key: str, existing_glossary: dict = None
) -> dict:
    """
    Generate glossary entries from text using Gemini API.

    Analyzes the provided text to extract ONLY the most critical names and terms
    that need consistent translation. Focuses on proper nouns and unique concepts
    that would confuse readers if translated inconsistently.

    Args:
        text (str): The chapter text to analyze for glossary terms
        api_key (str): Google AI Studio API key for authentication
        existing_glossary (dict, optional): Current glossary to avoid duplicates

    Returns:
        dict: Dictionary of new terms and their definitions/descriptions

    Raises:
        RuntimeError: If glossary generation fails after retries
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    existing_terms = list(existing_glossary.keys()) if existing_glossary else []
    existing_text = (
        f"\n\nExisting glossary terms (don't repeat these): {', '.join(existing_terms)}"
        if existing_terms
        else ""
    )

    prompt = f"""Analyze this novel text and identify ONLY the most critical proper nouns and unique terms that MUST be translated consistently. Be VERY selective - include only:

1. **Character names** - Main characters, important side characters (not generic titles like "guard" or "merchant")
2. **Place names** - Specific cities, kingdoms, regions, landmarks (not generic terms like "forest" or "mountain")
3. **Unique magical/fantasy terms** - Special abilities, systems, concepts unique to this world (not common words)
4. **Important organizations** - Named guilds, orders, factions (not generic terms like "army")
5. **Significant artifacts/items** - Named weapons, magical items, important objects

CRITICAL: For each term, if the original non-English name appears in the text, include it in brackets.

Format your response exactly like this:
EnglishName [OriginalName]: Brief context for translation consistency
AnotherTerm: Brief context (if no original name visible)

Be extremely selective. Only include terms that would cause confusion if translated inconsistently. Skip common fantasy terms, generic titles, and ordinary objects.{existing_text}

TEXT TO ANALYZE:
{text}"""

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = model.generate_content(prompt)
            result_text = response.text.strip()

            # Parse the response into a dictionary
            glossary = {}
            for line in result_text.split("\n"):
                if line.strip() and ":" in line:
                    term, definition = line.split(":", 1)
                    term = term.strip()
                    definition = definition.strip()
                    if term and definition:
                        glossary[term] = definition

            return glossary

        except google.api_core.exceptions.InternalServerError as e:
            log(f"Glossary generation attempt {attempt}/{RETRY_ATTEMPTS} failed: {e}")
            if attempt < RETRY_ATTEMPTS:
                log(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
        except Exception as e:
            log(f"Unexpected error generating glossary: {e}")
            break

    log("Failed to generate glossary after multiple attempts.")
    raise RuntimeError("Glossary generation failed")


def legacy_update_glossary_from_text(
    text: str, api_key: str, current_glossary: dict
) -> dict:
    """
    Legacy function for updating glossary - kept for fallback purposes.

    NOTE: This function is now replaced by the structured output approach
    in translate_and_extract_terms() which combines translation and glossary
    extraction in a single API call for better efficiency.

    Args:
        text (str): New chapter text to analyze
        api_key (str): Google AI Studio API key for authentication
        current_glossary (dict): Current glossary dictionary

    Returns:
        dict: New critical terms to add to the glossary
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODEL_NAME)

        existing_terms = list(current_glossary.keys())
        existing_text = (
            f"\n\nExisting glossary terms (don't repeat): {', '.join(existing_terms)}"
            if existing_terms
            else ""
        )

        prompt = f"""Analyze this new chapter and identify ONLY new critical terms that are missing from the existing glossary and absolutely need consistent translation. Be EXTREMELY selective - only add:

1. **New major character names** that will appear frequently
2. **New important place names** that are central to the story
3. **New unique magical/fantasy concepts** that are story-specific
4. **New significant organizations/factions** with proper names

CRITICAL: Include original language names in brackets if visible in the text.

Skip minor characters, common terms, or anything already covered by existing glossary.

Format exactly like this:
NewTerm [OriginalName]: Brief context
AnotherNewTerm: Brief context

Be conservative - when in doubt, DON'T include it.{existing_text}

TEXT TO ANALYZE:
{text}"""

        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # Parse the response into a dictionary
        new_terms = {}
        for line in result_text.split("\n"):
            if line.strip() and ":" in line:
                term, definition = line.split(":", 1)
                term = term.strip()
                definition = definition.strip()
                if term and definition:
                    new_terms[term] = definition

        # Filter out terms that already exist (case-insensitive and partial matching)
        existing_lower = {k.lower(): k for k in current_glossary.keys()}
        filtered_terms = {}

        for term, definition in new_terms.items():
            # Check if term or its base form already exists
            term_lower = term.lower()
            base_term = (
                term.split("[")[0].strip().lower() if "[" in term else term_lower
            )

            if (
                term_lower not in existing_lower
                and base_term not in existing_lower
                and not any(
                    base_term in existing.lower() for existing in existing_lower
                )
            ):
                filtered_terms[term] = definition

        if filtered_terms:
            log(f"Found {len(filtered_terms)} new critical glossary terms")

        return filtered_terms

    except Exception as e:
        log(f"Warning: Failed to update glossary: {e}")
        return {}


def translate_and_extract_terms(
    text: str,
    api_key: str,
    base_prompt: str,
    glossary_text: str = "",
    existing_glossary: dict = None,
) -> tuple[str, dict]:
    """
    Translate text and extract new glossary terms using structured output in a single API call.

    This function handles both translation and glossary extraction by:
    1. Configuring the Gemini API with the provided API key
    2. Creating a generative model with structured output schema
    3. Combining translation and glossary extraction in one request
    4. Making API calls with retry logic for reliability
    5. Returning both translated text and new glossary terms

    Args:
        text (str): The raw chapter text to translate
        api_key (str): Google AI Studio API key for authentication
        base_prompt (str): Instructions for how to translate (tone, style, etc.)
        glossary_text (str, optional): Formatted glossary for translation consistency
        existing_glossary (dict, optional): Current glossary to avoid duplicates

    Returns:
        tuple[str, dict]: (translated_text, new_glossary_terms)

    Raises:
        RuntimeError: If all retry attempts fail or unexpected errors occur
    """
    genai.configure(api_key=api_key)

    # Define the structured output schema
    schema = {
        "type": "object",
        "properties": {
            "translation": {
                "type": "string",
                "description": "The complete translated text in English",
            },
            "new_glossary_terms": {
                "type": "array",
                "description": "New critical terms found in this chapter that should be added to glossary",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "The term name, with original language in brackets if available",
                        },
                        "definition": {
                            "type": "string",
                            "description": "Brief context or description for the term",
                        },
                    },
                    "required": ["term", "definition"],
                },
            },
        },
        "required": ["translation", "new_glossary_terms"],
    }

    model = genai.GenerativeModel(
        MODEL_NAME,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json", response_schema=schema
        ),
    )

    # Build the combined prompt
    existing_terms = list(existing_glossary.keys()) if existing_glossary else []
    existing_terms_text = (
        f"\n\nExisting glossary terms (don't repeat): {', '.join(existing_terms)}"
        if existing_terms
        else ""
    )

    if glossary_text:
        prompt = f"""{base_prompt}

{glossary_text}

ADDITIONAL TASK: After translating, identify any NEW critical terms in the original text that should be added to the glossary. Be extremely selective - only include:
1. New major character names that will appear frequently
2. New important place names central to the story
3. New unique magical/fantasy concepts specific to this story
4. New significant organizations/factions with proper names

Include original language names in brackets if visible. Format new terms as an array of objects with "term" and "definition" fields.{existing_terms_text}

TEXT TO TRANSLATE:
{text}"""
    else:
        prompt = f"""{base_prompt}

ADDITIONAL TASK: After translating, identify any critical terms in the original text that should be in a glossary for translation consistency. Be extremely selective - only include:
1. Major character names that will appear frequently
2. Important place names central to the story
3. Unique magical/fantasy concepts specific to this story
4. Significant organizations/factions with proper names

Include original language names in brackets if visible. Format terms as an array of objects with "term" and "definition" fields.{existing_terms_text}

TEXT TO TRANSLATE:
{text}"""

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = model.generate_content(prompt)
            result = json.loads(response.text)

            translation = result.get("translation", "")
            new_terms_array = result.get("new_glossary_terms", [])

            # Convert array format to dictionary and filter existing terms
            new_terms = {}
            if existing_glossary:
                existing_lower = {k.lower(): k for k in existing_glossary.keys()}

                for item in new_terms_array:
                    term = item.get("term", "").strip()
                    definition = item.get("definition", "").strip()

                    if term and definition:
                        term_lower = term.lower()
                        base_term = (
                            term.split("[")[0].strip().lower()
                            if "[" in term
                            else term_lower
                        )

                        if (
                            term_lower not in existing_lower
                            and base_term not in existing_lower
                            and not any(
                                base_term in existing.lower()
                                for existing in existing_lower
                            )
                        ):
                            new_terms[term] = definition
            else:
                # No existing glossary, add all terms
                for item in new_terms_array:
                    term = item.get("term", "").strip()
                    definition = item.get("definition", "").strip()
                    if term and definition:
                        new_terms[term] = definition

            return translation, new_terms

        except json.JSONDecodeError as e:
            log(f"Failed to parse JSON response on attempt {attempt}: {e}")
            if attempt < RETRY_ATTEMPTS:
                log(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
        except google.api_core.exceptions.InternalServerError as e:
            log(f"Attempt {attempt}/{RETRY_ATTEMPTS} failed: {e}")
            if attempt < RETRY_ATTEMPTS:
                log(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
        except Exception as e:
            log(f"Unexpected error: {e}")
            break

    log("Failed to translate and extract terms after multiple attempts.")
    raise RuntimeError("Translation and glossary extraction failed")


def parse_args() -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Sets up the argument parser with all available CLI options and returns
    the parsed arguments. This function defines the command-line interface
    for the translation tool.

    Returns:
        argparse.Namespace: Parsed command-line arguments containing:
            - novel_directory: Required path to novel root directory
            - api_key: Optional Google AI Studio API key
            - raw_folder: Optional path to raw chapter files
            - translated_folder: Optional path for translated output
            - base_prompt: Optional translation instruction prompt

    Note:
        All optional arguments can override corresponding values in config.json.
        The novel_directory argument is required and should contain config.json
        and the chapter folders.
    """
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
    parser.add_argument(
        "--regenerate_glossary",
        action="store_true",
        help="Regenerate glossary from scratch using initial chapters.",
    )
    parser.add_argument(
        "--no_glossary",
        action="store_true",
        help="Disable glossary usage for this translation session.",
    )
    return parser.parse_args()


def main():
    """
    Main entry point for the novel translation CLI tool.

    This function orchestrates the entire translation process:
    1. Parse command-line arguments and validate novel directory
    2. Load and resolve configuration settings
    3. Validate the raw chapters folder exists
    4. Create the translated output folder if needed
    5. Generate or load glossary for translation consistency
    6. Process all .txt files sequentially for optimal glossary progression
    7. Update glossary after each chapter with new terms
    8. Save translated content to the output folder

    Sequential processing ensures each chapter benefits from glossary updates
    made during translation of previous chapters, maintaining consistency.

    Error Handling:
    - Exits if novel directory or raw folder doesn't exist
    - Logs and continues if individual translations fail
    - Creates output directory automatically if missing

    File Processing:
    - Processes .txt files in alphabetical order
    - Preserves original filenames in translated output
    - Uses UTF-8 encoding for all file operations
    - Skips files that already exist in translated folder
    """
    # Parse command-line arguments and validate novel directory
    args = parse_args()
    novel_root = Path(args.novel_directory).resolve()
    if not novel_root.is_dir():
        log(f"Error: Novel directory not found: {novel_root}")
        sys.exit(1)

    # Load and resolve all configuration settings
    cfg = Config(novel_root, args)

    # Validate that the raw chapters folder exists
    if not cfg.raw_folder.is_dir():
        log(f"Error: Raw folder not found: {cfg.raw_folder}")
        sys.exit(1)

    # Create the translated output folder if it doesn't exist
    cfg.translated_folder.mkdir(parents=True, exist_ok=True)
    log(f"Translations will be saved to: {cfg.translated_folder}")

    # Handle glossary initialization and regeneration
    if args.regenerate_glossary or (not cfg.glossary and not args.no_glossary):
        log("Generating initial glossary from first chapters...")
        try:
            generate_initial_glossary(cfg)
        except Exception as e:
            log(f"Warning: Failed to generate glossary: {e}")

    # Process all .txt files in the raw folder sequentially for proper glossary progression
    txt_files = sorted(cfg.raw_folder.glob("*.txt"))
    if not txt_files:
        log("No .txt files found in raw folder")
        return

    log(f"Found {len(txt_files)} chapter files to process")

    for txt_file in txt_files:
        dest_file = cfg.translated_folder / txt_file.name

        # Skip files that have already been translated
        if dest_file.exists():
            log(f"Skipping already translated: {txt_file.name}")
            continue

        try:
            # Read the raw chapter content
            content = txt_file.read_text(encoding="utf-8")
            log(f"Translating: {txt_file.name}")

            # Get current glossary text for this translation
            glossary_text = "" if args.no_glossary else cfg.get_glossary_text()

            # Translate the chapter and extract new glossary terms in one call
            translated_content, new_terms = translate_and_extract_terms(
                content,
                cfg.api_key,
                cfg.base_prompt,
                glossary_text,
                cfg.glossary if not args.no_glossary else None,
            )

            # Save the translated result
            dest_file.write_text(translated_content, encoding="utf-8")
            log(f"Saved translation: {dest_file.name}")

            # Update glossary with new terms found during translation (if not disabled)
            if not args.no_glossary and new_terms:
                cfg.glossary.update(new_terms)
                cfg.save_glossary()
                log(
                    f"Updated glossary with {len(new_terms)} new terms from {txt_file.name}"
                )

        except Exception as e:
            # Log errors but continue processing other files
            log(f"Error translating {txt_file.name}: {e}")
            continue

    # Save final glossary state
    if not args.no_glossary and cfg.glossary:
        cfg.save_glossary()
        log(f"Translation complete. Final glossary contains {len(cfg.glossary)} terms.")


def generate_initial_glossary(cfg: Config):
    """
    Generate initial glossary from the first few chapters of the novel.

    Analyzes the first GLOSSARY_INIT_CHAPTERS chapter files to create
    an initial glossary of critical terms for translation consistency.

    Args:
        cfg (Config): Configuration object containing paths and settings

    Raises:
        RuntimeError: If glossary generation fails
    """
    # Get first few chapter files for glossary generation
    txt_files = sorted(cfg.raw_folder.glob("*.txt"))
    if not txt_files:
        log("No chapter files found for glossary generation")
        return

    init_files = txt_files[:GLOSSARY_INIT_CHAPTERS]
    combined_text = ""

    for txt_file in init_files:
        try:
            chapter_content = txt_file.read_text(encoding="utf-8")
            combined_text += f"\n\n--- {txt_file.name} ---\n{chapter_content}"
        except Exception as e:
            log(f"Warning: Could not read {txt_file.name} for glossary: {e}")

    if not combined_text.strip():
        log("No content available for glossary generation")
        return

    log(f"Generating glossary from {len(init_files)} initial chapters...")

    # Generate and save initial glossary
    initial_glossary = generate_glossary_from_text(
        combined_text, cfg.api_key, cfg.glossary
    )

    if initial_glossary:
        cfg.glossary.update(initial_glossary)
        cfg.save_glossary()
        log(f"Generated initial glossary with {len(initial_glossary)} terms")
    else:
        log("Warning: No glossary terms generated from initial chapters")


if __name__ == "__main__":
    """
    Entry point when script is run directly.

    Handles graceful shutdown on Ctrl+C interruption and ensures the main
    function is only called when the script is executed directly (not imported).
    """
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user. Exiting.")
        sys.exit(0)
