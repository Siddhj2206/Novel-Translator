#!/usr/bin/env python3
"""
Novel Translator

This script provides a command-line interface for translating novel chapters using
Gemini. It supports translation with  glossary management, retry logic, and
per-novel configuration through config files.
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
MODEL_NAME = "gemini-2.5-flash-preview-05-20"
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
GLOSSARY_INIT_CHAPTERS = 5
MAX_GLOSSARY_ENTRIES = 1000
MAX_NEW_TERMS_PER_CHAPTER = 10
MAX_NEW_TERMS_PER_CHAPTER_STRICT = 10


def log(msg: str):
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

    def _load_config_file(self):
        """Load configuration from config.json file in the novel directory."""
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
        """Resolve the Google AI Studio API key from CLI args or config file."""
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
        """Resolve the base translation prompt from config file, CLI args, or default."""
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
        """Resolve the raw and translated folder paths from various sources."""
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
        """Set up glossary path and load existing glossary if available."""
        self.glossary_path = self.novel_root / "glossary.txt"
        self.glossary = self._load_glossary()

        if self.glossary:
            log(f"Loaded glossary with {len(self.glossary)} entries")
        else:
            log("No existing glossary found - will generate from initial chapters")

    def _load_glossary(self) -> dict:
        """Load glossary entries from glossary.txt file."""
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
        """Save current glossary to glossary.txt file."""
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
        """Get formatted glossary text for inclusion in translation prompts."""
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
    """Generate glossary entries from text using Gemini API."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

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


def translate_and_extract_terms(
    text: str,
    api_key: str,
    base_prompt: str,
    glossary_text: str = "",
    existing_glossary: dict = None,
    strict_mode: bool = False,
) -> tuple[str, dict]:
    """Translate text and extract new glossary terms using structured output in a single API call."""
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

Aim for 0-1 new terms maximum per chapter. When uncertain, DON'T add it. Include original language names in brackets if visible. Format new terms as an array of objects with "term" and "definition" fields.{existing_terms_text}

TEXT TO TRANSLATE:
{text}"""
    else:
        prompt = f"""{base_prompt}

FORMATTING REQUIREMENTS:
- Preserve the original paragraph structure and line breaks
- Maintain proper spacing between paragraphs
- Keep dialogue formatting intact
- Do NOT merge paragraphs into one large block of text

ADDITIONAL TASK: After translating, identify any absolutely essential terms that must be in a glossary. Be EXTREMELY restrictive - only include terms that meet ALL criteria:
1. Has a specific non-English name requiring consistent translation
2. Will definitely appear again (main characters/major locations only)
3. Would cause significant reader confusion if translated inconsistently

INCLUDE ONLY:
- Main character names (not side characters)
- Major location names (primary settings only)
- Core story concepts with specific names (only if central to plot)

EXCLUDE:
- Any character mentioned briefly
- Generic titles or common terms
- Minor locations
- Anything without a specific original non-English name
- Terms that can be translated normally

Aim for 0-1 terms maximum for the entire chapter. When uncertain, DON'T add it. Include original language names in brackets if visible. Format terms as an array of objects with "term" and "definition" fields.{existing_terms_text}

TEXT TO TRANSLATE:
{text}"""

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = model.generate_content(prompt)
            result = json.loads(response.text)

            translation = result.get("translation", "")
            new_terms_array = result.get("new_glossary_terms", [])

            # Post-process translation to ensure proper formatting
            translation = post_process_translation(translation)

            # Convert array format to dictionary and filter existing terms
            new_terms = {}
            filtered_terms = []

            # Common terms to exclude from glossary
            excluded_terms = {
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

                        # Check if term is in excluded list
                        if base_term in excluded_terms:
                            continue

                        if (
                            term_lower not in existing_lower
                            and base_term not in existing_lower
                            and not any(
                                base_term in existing.lower()
                                for existing in existing_lower
                            )
                        ):
                            filtered_terms.append((term, definition))
            else:
                # No existing glossary, consider all terms
                for item in new_terms_array:
                    term = item.get("term", "").strip()
                    definition = item.get("definition", "").strip()
                    if term and definition:
                        base_term = (
                            term.split("[")[0].strip().lower()
                            if "[" in term
                            else term.lower()
                        )

                        # Check if term is in excluded list
                        if base_term not in excluded_terms:
                            filtered_terms.append((term, definition))

            # Limit number of new terms per chapter based on mode
            max_terms = (
                MAX_NEW_TERMS_PER_CHAPTER_STRICT
                if strict_mode
                else MAX_NEW_TERMS_PER_CHAPTER
            )
            for term, definition in filtered_terms[:max_terms]:
                new_terms[term] = definition

            if len(filtered_terms) > max_terms:
                log(
                    f"Limited new glossary terms to {max_terms} out of {len(filtered_terms)} suggested terms"
                )

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
        import re

        # Add line breaks after sentences that are followed by capital letters
        result = re.sub(r"([.!?])\s+([A-Z])", r"\1\n\n\2", result)
        # Add breaks after dialogue patterns
        result = re.sub(r'([.!?]")\s+([A-Z])', r"\1\n\n\2", result)

    return result


def parse_args() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
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


def main():
    """Main entry point for the novel translation CLI tool."""
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
            generate_initial_glossary(cfg, args.skip_glossary_review)
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
            content = txt_file.read_text(encoding="utf-8")
            log(f"Translating: {txt_file.name}")

            glossary_text = "" if args.no_glossary else cfg.get_glossary_text()

            translated_content, new_terms = translate_and_extract_terms(
                content,
                cfg.api_key,
                cfg.base_prompt,
                glossary_text,
                cfg.glossary if not args.no_glossary else None,
                args.strict_glossary,
            )

            dest_file.write_text(translated_content, encoding="utf-8")
            log(f"Saved translation: {dest_file.name}")

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


def generate_initial_glossary(cfg: Config, skip_review: bool = False):
    """Generate initial glossary from the first few chapters of the novel."""
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

    initial_glossary = generate_glossary_from_text(
        combined_text, cfg.api_key, cfg.glossary
    )

    if initial_glossary:
        # Apply stricter filtering to initial glossary
        filtered_glossary = {}

        # Sort by frequency of occurrence in text for better prioritization
        text_lower = combined_text.lower()
        term_scores = []

        for term, definition in initial_glossary.items():
            # Extract base term (without brackets)
            base_term = term.split("[")[0].strip() if "[" in term else term

            # Count occurrences of the term
            count = text_lower.count(base_term.lower())

            # Score based on occurrence count and whether it has original name
            has_original = "[" in term
            score = count * (2 if has_original else 1)

            term_scores.append((term, definition, count, score))

        # Sort by score and take only the most important terms
        term_scores.sort(key=lambda x: x[3], reverse=True)

        # Limit initial glossary size more aggressively
        max_initial_terms = min(20, len(term_scores))  # Cap at 20 terms

        # Common terms to exclude from glossary
        excluded_terms = {
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

        for term, definition, count, score in term_scores[:max_initial_terms]:
            base_term = (
                term.split("[")[0].strip().lower() if "[" in term else term.lower()
            )

            # Only include terms that appear multiple times or have clear original names
            # and are not in the excluded list
            if (count >= 2 or "[" in term) and base_term not in excluded_terms:
                filtered_glossary[term] = definition

        cfg.glossary.update(filtered_glossary)
        cfg.save_glossary()

        if len(filtered_glossary) < len(initial_glossary):
            log(
                f"Filtered initial glossary from {len(initial_glossary)} to {len(filtered_glossary)} essential terms"
            )
        log(f"Generated initial glossary with {len(initial_glossary)} terms")

        # Display the generated glossary for user review
        print("\n" + "=" * 60)
        print("INITIAL GLOSSARY GENERATED")
        print("=" * 60)
        print(f"Glossary saved to: {cfg.glossary_path}")
        print(f"Total terms: {len(initial_glossary)}")
        print("\nGenerated terms:")
        for term, definition in initial_glossary.items():
            print(f"  {term}: {definition}")

        print("\n" + "=" * 60)
        print("Please review the glossary file and make any necessary corrections.")
        print("You can edit the glossary file directly to fix any naming errors.")
        print("=" * 60)

        # Wait for user confirmation unless skipped
        if not skip_review:
            while True:
                user_input = (
                    input("\nProceed with translation using this glossary? (y/n): ")
                    .strip()
                    .lower()
                )
                if user_input in ["y", "yes"]:
                    log("Proceeding with translation...")
                    # Reload glossary in case user made manual edits
                    cfg.glossary = cfg._load_glossary()
                    log(f"Reloaded glossary with {len(cfg.glossary)} terms")
                    break
                elif user_input in ["n", "no"]:
                    print(
                        "Translation cancelled. Please edit the glossary file and run again."
                    )
                    sys.exit(0)
                else:
                    print("Please enter 'y' for yes or 'n' for no.")
        else:
            log("Skipping glossary review (--skip_glossary_review flag used)")

    else:
        log("Warning: No glossary terms generated from initial chapters")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user. Exiting.")
        sys.exit(0)
