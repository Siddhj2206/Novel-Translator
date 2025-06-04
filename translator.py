#!/usr/bin/env python3
"""
Novel Translator
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openai import OpenAI


# Configuration constants
MODEL_NAME = "gemini-2.5-flash-preview-05-20"
PROVIDER_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
GLOSSARY_INIT_CHAPTERS = 5
MAX_GLOSSARY_ENTRIES = 1000
MAX_NEW_TERMS_PER_CHAPTER = 10
MAX_NEW_TERMS_PER_CHAPTER_STRICT = 1

# Common terms to exclude from glossary
EXCLUDED_TERMS = {
    # Basic fantasy terms
    "magic",
    "sword",
    "guild",
    "king",
    "queen",
    "lord",
    "lady",
    "master",
    "knight",
    "warrior",
    "mage",
    "priest",
    "merchant",
    "guard",
    "soldier",
    "captain",
    "general",
    "princess",
    "prince",
    "duke",
    "count",
    "baron",
    "noble",
    "commoner",
    "peasant",
    # Places and structures
    "inn",
    "tavern",
    "shop",
    "market",
    "street",
    "road",
    "path",
    "forest",
    "mountain",
    "river",
    "lake",
    "sea",
    "ocean",
    "village",
    "town",
    "city",
    "kingdom",
    "empire",
    "castle",
    "palace",
    "tower",
    "wall",
    "gate",
    "door",
    "window",
    "room",
    "hall",
    "church",
    "temple",
    "shrine",
    "school",
    "academy",
    "library",
    "hospital",
    "prison",
    # Items and equipment
    "weapon",
    "armor",
    "shield",
    "bow",
    "arrow",
    "spear",
    "axe",
    "dagger",
    "staff",
    "potion",
    "scroll",
    "book",
    "letter",
    "map",
    "key",
    "coin",
    "gold",
    "silver",
    # Creatures and concepts
    "monster",
    "demon",
    "devil",
    "angel",
    "god",
    "goddess",
    "spirit",
    "ghost",
    "soul",
    "fire",
    "water",
    "earth",
    "air",
    "wind",
    "ice",
    "lightning",
    "light",
    "dark",
    "power",
    "strength",
    "speed",
    "skill",
    "ability",
    "technique",
    "method",
    "way",
}

# JSON schema for structured output
TRANSLATION_SCHEMA = {
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


def log(msg: str) -> None:
    """Log a message with timestamp to stdout."""
    timestamp = datetime.now().strftime("%H:%M")
    print(f"[{timestamp}] {msg}")


class Config:
    """Configuration manager for novel translation settings."""

    def __init__(self, novel_root: Path, args: argparse.Namespace):
        """Initialize configuration by loading and resolving all settings."""
        self.novel_root = novel_root
        self.cli = args
        self._load_config_file()
        self._resolve_api_key()
        self._resolve_base_prompt()
        self._resolve_folders()
        self._setup_glossary()

    def _load_config_file(self) -> None:
        """Load configuration from config.json if it exists."""
        self.config_path = self.novel_root / "config.json"
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.file = json.load(f)
                log(f"Loaded config from {self.config_path}")
            except json.JSONDecodeError as e:
                log(f"Error reading config file: {e}")
                sys.exit(1)
        else:
            self.file = {}
            log("No config.json found, using defaults and CLI arguments")

    def _resolve_api_key(self) -> None:
        """Resolve API key from CLI args or config file."""
        self.api_key = self.cli.api_key or self.file.get("api_key")
        if not self.api_key:
            log("Error: API key required. Provide via --api_key or config.json")
            sys.exit(1)

    def _resolve_base_prompt(self) -> None:
        """Resolve base prompt from CLI args or config file."""
        default_prompt = (
            "Translate this novel chapter from Japanese to natural, fluent English."
        )
        self.base_prompt = self.cli.base_prompt or self.file.get(
            "base_prompt", default_prompt
        )

    def _resolve_folders(self) -> None:
        """Resolve input and output folder paths."""
        self.raw_folder = Path(
            self.cli.raw_folder or self.file.get("raw_folder", "raw")
        )
        self.translated_folder = Path(
            self.cli.translated_folder
            or self.file.get("translated_folder", "translated")
        )

        # Make paths absolute relative to novel root
        if not self.raw_folder.is_absolute():
            self.raw_folder = self.novel_root / self.raw_folder
        if not self.translated_folder.is_absolute():
            self.translated_folder = self.novel_root / self.translated_folder

        # Validate raw folder exists
        if not self.raw_folder.exists():
            log(f"Error: Raw folder '{self.raw_folder}' does not exist")
            sys.exit(1)

        # Create translated folder if it doesn't exist
        self.translated_folder.mkdir(parents=True, exist_ok=True)

    def _setup_glossary(self) -> None:
        """Setup glossary configuration and paths."""
        self.use_glossary = not self.cli.no_glossary
        self.glossary_path = self.novel_root / "glossary.txt"

        if self.use_glossary:
            self._load_glossary()

    def _load_glossary(self) -> None:
        """Load existing glossary from file."""
        self.glossary = {}
        if self.glossary_path.exists():
            try:
                with open(self.glossary_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and ":" in line:
                            term, definition = line.split(":", 1)
                            self.glossary[term.strip()] = definition.strip()
                log(f"Loaded {len(self.glossary)} terms from glossary")
            except Exception as e:
                log(f"Error loading glossary: {e}")
                self.glossary = {}
        else:
            log("No existing glossary found")

    def save_glossary(self) -> None:
        """Save glossary to file."""
        if not self.use_glossary:
            return

        try:
            # Limit glossary size
            if len(self.glossary) > MAX_GLOSSARY_ENTRIES:
                # Keep most recent entries (simple strategy)
                items = list(self.glossary.items())[-MAX_GLOSSARY_ENTRIES:]
                self.glossary = dict(items)
                log(f"Trimmed glossary to {MAX_GLOSSARY_ENTRIES} entries")

            with open(self.glossary_path, "w", encoding="utf-8") as f:
                for term, definition in self.glossary.items():
                    f.write(f"{term}: {definition}\n")
            log(f"Saved glossary with {len(self.glossary)} terms")
        except Exception as e:
            log(f"Error saving glossary: {e}")

    def get_glossary_text(self) -> str:
        """Get formatted glossary text for prompts."""
        if not self.use_glossary or not self.glossary:
            return ""

        glossary_lines = [
            f"{term}: {definition}" for term, definition in self.glossary.items()
        ]
        return "GLOSSARY (use these consistent translations):\n" + "\n".join(
            glossary_lines
        )


def create_openai_client(api_key: str) -> OpenAI:
    """Create and return an OpenAI client configured for Gemini."""
    return OpenAI(api_key=api_key, base_url=PROVIDER_BASE_URL)


def build_translation_prompt(
    base_prompt: str,
    text: str,
    glossary_text: str = "",
    existing_terms: Optional[List[str]] = None,
    strict_mode: bool = False,
) -> str:
    """Build the complete translation prompt."""
    max_terms = 1 if strict_mode else "0-1"
    existing_terms_text = ""

    if existing_terms:
        existing_terms_text = (
            f"\n\nExisting glossary terms (don't repeat): {', '.join(existing_terms)}"
        )

    glossary_section = f"\n\n{glossary_text}" if glossary_text else ""

    return f"""{base_prompt}{glossary_section}

FORMATTING REQUIREMENTS:
- Preserve the original paragraph structure and line breaks
- Maintain proper spacing between paragraphs
- Keep dialogue formatting intact
- Do NOT merge paragraphs into one large block of text

ADDITIONAL TASK: After translating, identify any NEW absolutely essential terms that must be added to the glossary. Be EXTREMELY restrictive - only include terms that meet ALL criteria:
1. Has a specific non-English name requiring consistent translation
2. Will definitely appear again (main characters/major locations only)
3. Would cause significant reader confusion if translated inconsistently

INCLUDE ONLY:
- New main character names (not side characters)
- New major location names (primary settings only)
- New core story concepts with specific names (only if central to plot)

EXCLUDE:
- Any character mentioned briefly or in passing
- Generic titles or common terms
- Minor locations
- Anything without a specific original non-English name
- Terms that can be translated normally

Aim for {max_terms} new terms maximum per chapter. When uncertain, DON'T add it. Include original language names in brackets if visible. Format new terms as an array of objects with "term" and "definition" fields.{existing_terms_text}

TEXT TO TRANSLATE:
{text}"""


def filter_new_terms(
    new_terms_array: List[Dict[str, str]],
    existing_glossary: Optional[Dict[str, str]] = None,
    strict_mode: bool = False,
) -> List[Tuple[str, str]]:
    """Filter and validate new glossary terms."""
    filtered_terms = []
    existing_lower = {}

    if existing_glossary:
        existing_lower = {k.lower(): k for k in existing_glossary.keys()}

    for item in new_terms_array:
        term = item.get("term", "").strip()
        definition = item.get("definition", "").strip()

        if not term or not definition:
            continue

        term_lower = term.lower()
        base_term = term.split("[")[0].strip().lower() if "[" in term else term_lower

        # Check if term is in excluded list
        if base_term in EXCLUDED_TERMS:
            continue

        # Check if term already exists
        if existing_glossary:
            if (
                term_lower in existing_lower
                or base_term in existing_lower
                or any(base_term in existing.lower() for existing in existing_lower)
            ):
                continue

        filtered_terms.append((term, definition))

    # Limit number of new terms per chapter
    max_terms = (
        MAX_NEW_TERMS_PER_CHAPTER_STRICT if strict_mode else MAX_NEW_TERMS_PER_CHAPTER
    )
    return filtered_terms[:max_terms]


def translate_and_extract_terms(
    text: str,
    api_key: str,
    base_prompt: str,
    glossary_text: str = "",
    existing_glossary: Optional[Dict[str, str]] = None,
    strict_mode: bool = False,
) -> Tuple[str, Dict[str, str]]:
    """Translate text and extract new glossary terms using structured output in a single API call."""
    client = create_openai_client(api_key)
    existing_terms = list(existing_glossary.keys()) if existing_glossary else []
    prompt = build_translation_prompt(
        base_prompt, text, glossary_text, existing_terms, strict_mode
    )

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "translation_response",
                        "schema": TRANSLATION_SCHEMA,
                    },
                },
            )

            result = json.loads(response.choices[0].message.content)
            translation = result.get("translation", "")
            new_terms_array = result.get("new_glossary_terms", [])

            # Post-process translation to ensure proper formatting
            translation = post_process_translation(translation)

            # Filter and convert new terms
            filtered_terms = filter_new_terms(
                new_terms_array, existing_glossary, strict_mode
            )
            new_terms = dict(filtered_terms)

            if len(new_terms_array) > len(filtered_terms):
                log(
                    f"Filtered glossary terms: {len(filtered_terms)} out of {len(new_terms_array)} suggested"
                )

            return translation, new_terms

        except json.JSONDecodeError as e:
            log(f"Failed to parse JSON response on attempt {attempt}: {e}")
            if attempt < RETRY_ATTEMPTS:
                log(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
        except Exception as e:
            if "InternalServerError" in str(e) or "500" in str(e):
                log(f"Attempt {attempt}/{RETRY_ATTEMPTS} failed: {e}")
                if attempt < RETRY_ATTEMPTS:
                    log(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
            else:
                log(f"Unexpected error: {e}")
                break

    log("Failed to translate and extract terms after multiple attempts.")
    raise RuntimeError("Translation and glossary extraction failed")


def generate_glossary_from_text(
    text: str, api_key: str, existing_glossary: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Generate glossary entries from text"""
    client = create_openai_client(api_key)
    existing_terms = list(existing_glossary.keys()) if existing_glossary else []
    existing_text = (
        f"\n\nExisting glossary terms (don't repeat these): {', '.join(existing_terms)}"
        if existing_terms
        else ""
    )

    prompt = f"""Analyze this novel text and identify ONLY the absolute most essential proper nouns that MUST appear in a glossary. Be EXTREMELY restrictive - only include terms that meet ALL these criteria:

1. The term appears multiple times OR is clearly a main character/location
2. The term has a specific non-English name that needs consistent translation
3. Mistranslating this term would significantly confuse readers

INCLUDE ONLY:
- **Main character names** (protagonists, major recurring characters only)
- **Major location names** (primary settings, important cities/kingdoms only)
- **Core unique concepts** (only if they're central plot elements with specific names)

EXCLUDE EVERYTHING ELSE including:
- Side characters mentioned once or twice
- Generic titles (lord, king, master, etc.)
- Common fantasy terms (magic, sword, guild, etc.)
- Minor locations or places mentioned in passing
- Descriptive terms that can be translated normally
- Any term that doesn't have a specific non-English original name

CRITICAL: For each term, if the original non-English name appears in the text, include it in brackets.

Format your response exactly like this:
EnglishName [OriginalName]: Brief context for translation consistency
AnotherTerm: Brief context (if no original name visible)

Only add 1-3 terms maximum per chapter unless there are truly many main characters introduced. When in doubt, DON'T add it.{existing_text}

TEXT TO ANALYZE:
{text}"""

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME, messages=[{"role": "user", "content": prompt}]
            )
            result_text = response.choices[0].message.content.strip()

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

        except Exception as e:
            if "InternalServerError" in str(e) or "500" in str(e):
                log(
                    f"Glossary generation attempt {attempt}/{RETRY_ATTEMPTS} failed: {e}"
                )
                if attempt < RETRY_ATTEMPTS:
                    log(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
            else:
                log(f"Unexpected error generating glossary: {e}")
                break

    log("Failed to generate glossary after multiple attempts.")
    raise RuntimeError("Glossary generation failed")


def post_process_translation(text: str) -> str:
    """Post-process translated text to ensure proper formatting and paragraph structure."""
    if not text or not text.strip():
        return text

    # Split into lines and process
    lines = text.split("\n")
    processed_lines = []

    for line in lines:
        line = line.strip()
        if line:
            processed_lines.append(line)
        else:
            # Preserve empty lines for paragraph breaks
            processed_lines.append("")

    # Join lines back together
    result = "\n".join(processed_lines)

    # Ensure we don't have too many consecutive empty lines
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")

    # Ensure the text doesn't start or end with excessive whitespace
    result = result.strip()

    # If the result appears to be one massive paragraph (no line breaks),
    # try to add some structure based on sentence patterns
    if "\n" not in result and len(result) > 500:
        # Split on common dialogue patterns
        result = re.sub(r'("[^"]*")\s+([A-Z])', r"\1\n\n\2", result)
        # Split on paragraph indicators
        result = re.sub(r"(\w\.)\s+([A-Z][a-z])", r"\1\n\n\2", result)

    return result


def get_chapter_files(raw_folder: Path) -> List[Path]:
    """Get sorted list of chapter files from raw folder."""
    chapter_files = []
    for ext in ["*.txt", "*.md"]:
        chapter_files.extend(raw_folder.glob(ext))

    # Sort files naturally (handle numbers correctly)
    def natural_sort_key(path):
        numbers = re.findall(r"\d+", path.stem)
        return (
            [int(num) if num.isdigit() else num for num in numbers]
            if numbers
            else [path.stem]
        )

    return sorted(chapter_files, key=natural_sort_key)


def generate_initial_glossary(config: Config) -> None:
    """Generate initial glossary from first few chapters."""
    if not config.use_glossary:
        return

    chapter_files = get_chapter_files(config.raw_folder)
    if not chapter_files:
        log("No chapter files found for glossary generation")
        return

    # Use first N chapters for glossary generation
    init_files = chapter_files[:GLOSSARY_INIT_CHAPTERS]
    log(f"Generating initial glossary from {len(init_files)} chapters...")

    combined_text = ""
    for chapter_file in init_files:
        try:
            with open(chapter_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    combined_text += f"\n\n{content}"
        except Exception as e:
            log(f"Error reading {chapter_file}: {e}")

    if not combined_text.strip():
        log("No content found in initial chapters")
        return

    try:
        new_glossary = generate_glossary_from_text(combined_text, config.api_key)
        config.glossary.update(new_glossary)

        if new_glossary:
            log(f"Generated {len(new_glossary)} initial glossary terms")
            config.save_glossary()

            # Show glossary to user for review unless skipped
            if not config.cli.skip_glossary_review:
                print("\nGenerated glossary terms:")
                for term, definition in new_glossary.items():
                    print(f"  {term}: {definition}")

                response = (
                    input("\nContinue with this glossary? (y/n): ").strip().lower()
                )
                if response not in ["y", "yes", ""]:
                    log("Glossary generation cancelled by user")
                    sys.exit(0)
        else:
            log("No glossary terms generated from initial chapters")
    except Exception as e:
        log(f"Error generating initial glossary: {e}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Translate novel chapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "novel_directory",
        type=Path,
        help="Path to novel root directory containing config.json and chapters.",
    )

    parser.add_argument(
        "--api_key",
        help="Google AI Studio API Key (overrides config).",
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

    parser.add_argument(
        "--skip_glossary_review",
        action="store_true",
        help="Skip user confirmation after generating initial glossary.",
    )

    parser.add_argument(
        "--strict_glossary",
        action="store_true",
        help="Use stricter glossary filtering (max 1 new term per chapter).",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for the translator."""
    args = parse_args()

    # Validate novel directory
    if not args.novel_directory.exists():
        log(f"Error: Novel directory '{args.novel_directory}' does not exist")
        sys.exit(1)

    # Initialize configuration
    config = Config(args.novel_directory, args)

    # Handle glossary regeneration
    if args.regenerate_glossary:
        if config.glossary_path.exists():
            config.glossary_path.unlink()
            log("Deleted existing glossary")
        config.glossary = {}

    # Generate initial glossary if needed
    if config.use_glossary and (not config.glossary or args.regenerate_glossary):
        generate_initial_glossary(config)

    # Get list of chapter files to translate
    chapter_files = get_chapter_files(config.raw_folder)
    if not chapter_files:
        log(f"No chapter files found in '{config.raw_folder}'")
        sys.exit(1)

    log(f"Found {len(chapter_files)} chapter files")

    # Translate chapters
    translated_count = 0
    for chapter_file in chapter_files:
        output_file = config.translated_folder / f"{chapter_file.stem}.txt"

        # Skip if already translated
        if output_file.exists():
            log(f"Skipping {chapter_file.name} (already translated)")
            continue

        log(f"Translating {chapter_file.name}...")

        try:
            # Read chapter content
            with open(chapter_file, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                log(f"Skipping empty file: {chapter_file.name}")
                continue

            # Translate chapter
            glossary_text = config.get_glossary_text()
            translation, new_terms = translate_and_extract_terms(
                content,
                config.api_key,
                config.base_prompt,
                glossary_text,
                config.glossary,
                args.strict_glossary,
            )

            # Update glossary with new terms
            if new_terms:
                config.glossary.update(new_terms)
                config.save_glossary()
                log(f"Added {len(new_terms)} new terms to glossary")

            # Save translation
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(translation)

            log(f"Saved translation to {output_file.name}")
            translated_count += 1

        except Exception as e:
            log(f"Error translating {chapter_file.name}: {e}")
            continue

    log(f"Translation complete: {translated_count} chapters translated")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user. Exiting.")
        sys.exit(0)
