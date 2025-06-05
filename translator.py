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
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
GLOSSARY_INIT_CHAPTERS = 5
MAX_GLOSSARY_ENTRIES = 1000
MAX_NEW_TERMS_PER_CHAPTER = 10
MAX_NEW_TERMS_PER_CHAPTER_STRICT = 1

# Provider configurations
PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash-preview-05-20",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1/",
        "default_model": "gpt-4.1-nano-2025-04-14",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1/",
        "default_model": "claude-sonnet-4-20250514",
    },
    "other": {
        "base_url": None,  # Must be provided in config
        "default_model": None,  # Must be provided in config
    },
}

# Default configuration
DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-2.5-flash-preview-05-20"



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


class ApiConfig:
    """
    Manages API configuration for the translation provider.

    Attributes:
        api_key: The API key for the translation service.
        provider_name: The name of the translation provider (e.g., "openai", "gemini").
        model: The specific model to use for translation.
        base_url: The base URL for the provider's API.
    """
    def __init__(self, cli_args: argparse.Namespace, file_config: Dict):
        """
        Initializes ApiConfig by resolving API key, provider, and model.

        Args:
            cli_args: Parsed command-line arguments.
            file_config: Configuration loaded from the config file.
        """
        self.api_key: Optional[str] = None
        self.provider_name: str = DEFAULT_PROVIDER
        self.model: Optional[str] = None
        self.base_url: Optional[str] = None
        self._resolve_api_key(cli_args, file_config)
        self._resolve_provider_and_model(file_config)

    def _resolve_api_key(self, cli_args: argparse.Namespace, file_config: Dict) -> None:
        """
        Resolves the API key from command-line arguments or the config file.
        The command-line argument takes precedence. Exits if no key is found.

        Args:
            cli_args: Parsed command-line arguments.
            file_config: Configuration loaded from the config file.
        """
        self.api_key = cli_args.api_key or file_config.get("api_key")
        if not self.api_key:
            log("Error: API key required. Provide via --api_key or config.json")
            sys.exit(1)

    def _resolve_provider_and_model(self, file_config: Dict) -> None:
        """
        Resolves the translation provider, model, and base URL.
        Uses defaults if not specified in the config file.
        Handles special configuration for "other" provider.

        Args:
            file_config: Configuration loaded from the config file.
        """
        self.provider_name = file_config.get("provider", DEFAULT_PROVIDER).lower()

        if self.provider_name not in PROVIDERS:
            log(
                f"Error: Unknown provider '{self.provider_name}'. Available providers: {list(PROVIDERS.keys())}"
            )
            sys.exit(1)

        provider_config = PROVIDERS[self.provider_name]

        # Handle "other" provider which requires custom base_url and model from config
        if self.provider_name == "other":
            self.base_url = file_config.get("base_url")
            self.model = file_config.get("model")

            if not self.base_url:
                log("Error: 'other' provider requires 'base_url' in config.json")
                sys.exit(1)
            if not self.model:
                log("Error: 'other' provider requires 'model' in config.json")
                sys.exit(1)
        else:
            # For predefined providers, get model from config or use provider's default
            self.model = file_config.get("model", provider_config["default_model"])
            self.base_url = provider_config["base_url"]

        log(f"Using provider: {self.provider_name}, model: {self.model}")


class PathConfig:
    """
    Manages file and directory paths for the translation process.

    Attributes:
        novel_root: The root directory of the novel.
        config_file: Path to the 'config.json' file.
        glossary_file: Path to the 'glossary.txt' file.
        raw_dir: Directory containing raw chapter files.
        translated_dir: Directory to save translated chapter files.
    """
    def __init__(self, novel_root: Path, cli_args: argparse.Namespace, file_config: Dict):
        """
        Initializes PathConfig by resolving various file and directory paths.

        Args:
            novel_root: The root directory of the novel.
            cli_args: Parsed command-line arguments.
            file_config: Configuration loaded from the config file.
        """
        self.novel_root: Path = novel_root
        self.config_file: Path = self.novel_root / "config.json"
        self.glossary_file: Path = self.novel_root / "glossary.txt"

        self.raw_dir: Path = self._resolve_path(
            cli_args.raw_folder, file_config.get("raw_folder"), "raw"
        )
        self.translated_dir: Path = self._resolve_path(
            cli_args.translated_folder,
            file_config.get("translated_folder"),
            "translated",
        )

        self._validate_paths()

    def _resolve_path(
        self, cli_path: Optional[str], config_path: Optional[str], default_name: str
    ) -> Path:
        """
        Resolves a path from CLI arguments, config file, or a default name.
        CLI arguments take precedence, then config file, then default.
        Paths are made absolute relative to the novel root if not already absolute.

        Args:
            cli_path: Path from command-line arguments (optional).
            config_path: Path from config file (optional).
            default_name: Default path name if not provided elsewhere.

        Returns:
            The resolved absolute Path object.
        """
        # Determine path string: CLI > config > default
        path_str = cli_path or config_path or default_name
        path = Path(path_str)
        # Make path absolute if it's relative
        if not path.is_absolute():
            path = self.novel_root / path
        return path

    def _validate_paths(self) -> None:
        """
        Validates that the raw directory exists and creates the translated directory
        if it doesn't already exist. Exits if raw directory is not found.
        """
        if not self.raw_dir.exists():
            log(f"Error: Raw folder '{self.raw_dir}' does not exist")
            sys.exit(1)
        self.translated_dir.mkdir(parents=True, exist_ok=True)


class GlossaryConfig:
    """
    Manages glossary settings, loading, saving, and formatting for prompts.

    Attributes:
        enabled: Boolean indicating if glossary usage is enabled.
        path: Path to the glossary file.
        terms: A dictionary holding the glossary terms {term: definition}.
    """
    def __init__(self, cli_args: argparse.Namespace, glossary_file_path: Path):
        """
        Initializes GlossaryConfig, determining if glossary is enabled and loading it.

        Args:
            cli_args: Parsed command-line arguments.
            glossary_file_path: The path to the glossary file.
        """
        self.enabled: bool = not cli_args.no_glossary
        self.path: Path = glossary_file_path
        self.terms: Dict[str, str] = {}

        if self.enabled:
            self._load()

    def _load(self) -> None:
        """
        Loads glossary terms from the file specified by `self.path`.
        Each line in the file is expected to be in "term: definition" format.
        """
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and ":" in line:  # Ensure line is not empty and contains a colon
                            term, definition = line.split(":", 1)  # Split only on the first colon
                            self.terms[term.strip()] = definition.strip()
                log(f"Loaded {len(self.terms)} terms from glossary: {self.path}")
            except Exception as e:
                log(f"Error loading glossary: {e}")
                self.terms = {}  # Reset to empty glossary on error
        else:
            log(f"No existing glossary found at {self.path}")

    def save(self) -> None:
        """
        Saves the current glossary terms to file.
        If the number of terms exceeds `MAX_GLOSSARY_ENTRIES`, it trims the
        glossary, keeping the most recent entries (based on insertion order here).
        """
        if not self.enabled:
            return

        try:
            # Trim glossary if it exceeds the maximum allowed size
            if len(self.terms) > MAX_GLOSSARY_ENTRIES:
                # This is a simple FIFO trimming strategy if dictionary is ordered (Python 3.7+)
                # For older Python, or for more robust "recency", a different tracking mechanism would be needed.
                items = list(self.terms.items())[-MAX_GLOSSARY_ENTRIES:]
                self.terms = dict(items)
                log(f"Trimmed glossary to {MAX_GLOSSARY_ENTRIES} entries")

            with open(self.path, "w", encoding="utf-8") as f:
                for term, definition in self.terms.items():
                    f.write(f"{term}: {definition}\n")
            log(f"Saved glossary with {len(self.terms)} terms to {self.path}")
        except Exception as e:
            log(f"Error saving glossary: {e}")

    def get_text_for_prompt(self) -> str:
        """Get formatted glossary text for prompts."""
        if not self.enabled or not self.terms:
            return ""

        glossary_lines = [
            f"{term}: {definition}" for term, definition in self.terms.items()
        ]
        return "GLOSSARY (use these consistent translations):\n" + "\n".join(
            glossary_lines
        )


class PromptConfig:
    """
    Manages the base prompt used for translations.

    Attributes:
        base_text: The base prompt string.
    """
    def __init__(self, cli_args: argparse.Namespace, file_config: Dict):
        """
        Initializes PromptConfig by resolving the base prompt text.

        Args:
            cli_args: Parsed command-line arguments.
            file_config: Configuration loaded from the config file.
        """
        default_prompt = (
            "Translate this novel chapter from Japanese to natural, fluent English."
        )
        self.base_text: str = cli_args.base_prompt or file_config.get(
            "base_prompt", default_prompt
        )
        log(f"Using base prompt: \"{self.base_text[:100]}...\"")


class Config:
    """
    Main configuration orchestrator for novel translation settings.

    This class loads configuration from a file and command-line arguments,
    then initializes specialized configuration objects for API, paths,
    glossary, and prompts.

    Attributes:
        novel_root: The root directory of the novel being translated.
        cli_args: Parsed command-line arguments.
        file_config: Configuration loaded from 'config.json'.
        api: ApiConfig instance for API related settings.
        paths: PathConfig instance for managing file/directory paths.
        glossary: GlossaryConfig instance for glossary management.
        prompt: PromptConfig instance for managing translation prompts.
    """

    def __init__(self, novel_root: Path, args: argparse.Namespace):
        """
        Initializes the main Config object.

        This involves storing the novel root path and CLI arguments, loading
        the `config.json` file, and then instantiating the specialized
        configuration objects (`ApiConfig`, `PathConfig`, `GlossaryConfig`, `PromptConfig`).

        Args:
            novel_root: The root directory of the novel.
            args: Parsed command-line arguments from `argparse`.
        """
        self.novel_root = novel_root
        self.cli_args = args  # Store original cli_args
        self.file_config: Dict = self._load_config_file()

        # Initialize specialized config objects, passing necessary parts of cli_args and file_config
        self.api = ApiConfig(self.cli_args, self.file_config)
        self.paths = PathConfig(self.novel_root, self.cli_args, self.file_config)
        self.glossary = GlossaryConfig(self.cli_args, self.paths.glossary_file)
        self.prompt = PromptConfig(self.cli_args, self.file_config)

    def _load_config_file(self) -> Dict:
        """
        Loads the main configuration from `config.json` located in the novel's root directory.

        Returns:
            A dictionary containing the configuration data if the file is found and valid.
            Returns an empty dictionary if the file is not found (defaults will apply).
            Exits the program if the file is found but contains invalid JSON.
        """
        config_file_path = self.novel_root / "config.json"
        if config_file_path.exists():
            try:
                with open(config_file_path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                log(f"Loaded config from {config_file_path}")
                return file_data
            except json.JSONDecodeError as e:
                log(f"Error reading config file: {e}") # Log the specific JSON error
                sys.exit(1)
        else:
            log("No config.json found, using defaults and CLI arguments")
            return {} # Return empty dict if no config file, allowing defaults/CLI to take over

    # The main Config class now delegates detailed configuration management
    # to specialized classes like ApiConfig, PathConfig, GlossaryConfig, and PromptConfig.
    # Methods for resolving specific settings have been moved into those respective classes.
    # Access to configuration values should be done via these sub-objects,
    # e.g., config.api.model, config.paths.raw_dir, config.glossary.terms.


def create_openai_client(api_config: ApiConfig) -> OpenAI:
    """
    Creates and returns an OpenAI API client.

    Args:
        api_config: An ApiConfig object containing the API key and base URL.

    Returns:
        An instance of the OpenAI client.
    """
    return OpenAI(api_key=api_config.api_key, base_url=api_config.base_url)


def build_translation_prompt(
    prompt_config: PromptConfig,
    text: str,
    glossary_text: str = "",
    existing_terms: Optional[List[str]] = None,
    strict_mode: bool = False,
) -> str:
    """
    Builds the complete prompt for the translation API call.

    Args:
        prompt_config: A PromptConfig object containing the base prompt text.
        text: The chapter text to be translated.
        glossary_text: Formatted string of glossary terms to be included in the prompt.
        existing_terms: A list of terms already in the glossary, to inform the AI.
        strict_mode: Boolean indicating if stricter term extraction rules should apply.

    Returns:
        The fully constructed prompt string.
    """
    # Determine the target number of new glossary terms for the prompt's instructions
    max_terms = MAX_NEW_TERMS_PER_CHAPTER_STRICT if strict_mode else MAX_NEW_TERMS_PER_CHAPTER
    # Note: The prompt asks for "0-1" or a similar small number for strict_mode,
    # but the actual constant MAX_NEW_TERMS_PER_CHAPTER_STRICT is 1.
    # The prompt text "Aim for {max_terms_text} new terms..." will be adjusted.
    # Using the actual constant `max_terms` (e.g. 1 or 10) directly might be better in the prompt.
    # For now, keeping the "0-1" text for strict as per original structure.
    max_terms_text = "0-1" if strict_mode else f"0-{MAX_NEW_TERMS_PER_CHAPTER}"


    existing_terms_text = ""

    if existing_terms:
        existing_terms_text = (
            f"\n\nExisting glossary terms (don't repeat): {', '.join(existing_terms)}"
        )

    glossary_section = f"\n\n{glossary_text}" if glossary_text else ""

    # Construct the main prompt
    # Using prompt_config.base_text instead of a separate base_prompt argument
    return f"""{prompt_config.base_text}{glossary_section}

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

Aim for {max_terms_text} new terms maximum per chapter. When uncertain, DON'T add it. Include original language names in brackets if visible. Format new terms as an array of objects with "term" and "definition" fields.{existing_terms_text}

TEXT TO TRANSLATE:
{text}"""


def filter_new_terms(
    new_terms_array: List[Dict[str, str]],
    existing_glossary: Optional[Dict[str, str]] = None,
    strict_mode: bool = False,
) -> List[Tuple[str, str]]:
    """
    Filters and validates new glossary terms suggested by the AI.

    Args:
        new_terms_array: A list of dictionaries, where each dictionary
                         represents a new term with "term" and "definition" keys.
        existing_glossary: A dictionary of existing glossary terms to check against.
        strict_mode: Boolean indicating if stricter filtering (fewer new terms) should apply.

    Returns:
        A list of tuples, where each tuple is a (term, definition) pair for
        filtered and validated new glossary terms.
    """
    filtered_terms = []
    existing_lower = {}

    if existing_glossary:
        # Create a lowercase version of existing terms for case-insensitive comparison
        existing_lower = {k.lower(): k for k in existing_glossary.keys()}

    for item in new_terms_array:
        term = item.get("term", "").strip()
        definition = item.get("definition", "").strip()

        # Skip if term or definition is empty
        if not term or not definition:
            continue

        term_lower = term.lower()
        # Extract base term (e.g., "Akira" from "Akira [明]") for broader duplicate checking
        base_term = term.split("[")[0].strip().lower() if "[" in term else term_lower

        # Check if the new term (or its base form) already exists in the glossary
        if existing_glossary:
            if (
                term_lower in existing_lower or  # Exact match (case-insensitive)
                base_term in existing_lower or  # Base term match (case-insensitive)
                any(base_term in existing.lower() for existing in existing_lower) # Check if base_term is part of any existing term
            ):
                continue  # Skip if term already exists

        filtered_terms.append((term, definition))

    # Apply limit on the number of new terms to be added per chapter
    max_new_terms_allowed = (
        MAX_NEW_TERMS_PER_CHAPTER_STRICT if strict_mode else MAX_NEW_TERMS_PER_CHAPTER
    )
    return filtered_terms[:max_new_terms_allowed]


def translate_and_extract_terms(
    text: str,
    config: "Config", # Main config still passed for now
    # base_prompt: str, # Replaced by config.prompt
    glossary_text: str = "", # This comes from config.glossary.get_text_for_prompt()
    existing_glossary_terms: Optional[Dict[str, str]] = None, # From config.glossary.terms
    strict_mode: bool = False,
) -> Tuple[str, Dict[str, str]]:
    """
    Translates text and extracts new glossary terms using an AI model.

    This function handles constructing the prompt, making the API call (with retries),
    parsing the structured JSON response, post-processing the translation,
    and filtering the extracted glossary terms.

    Args:
        text: The raw text of the chapter to translate.
        config: The main Config object containing all configurations.
        glossary_text: Pre-formatted glossary string to include in the prompt.
        existing_glossary_terms: A dictionary of current glossary terms.
        strict_mode: If True, applies stricter rules for new term extraction.

    Returns:
        A tuple containing:
            - The translated text (str).
            - A dictionary of new glossary terms {term: definition} (Dict[str, str]).

    Raises:
        RuntimeError: If translation and term extraction fail after multiple retry attempts.
    """
    client = create_openai_client(config.api)
    existing_terms_list = list(existing_glossary_terms.keys()) if existing_glossary_terms else []

    # Build the prompt for the AI
    prompt = build_translation_prompt(
        prompt_config=config.prompt,
        text=text,
        glossary_text=glossary_text,
        existing_terms=existing_terms_list,
        strict_mode=strict_mode
    )

    # Retry loop for API calls
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            # Make the API call
            response = client.chat.completions.create(
                model=config.api.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={  # Request structured JSON output
                    "type": "json_schema",
                    "json_schema": {
                        "name": "translation_response",
                        "schema": TRANSLATION_SCHEMA,
                    },
                },
            )

            # Parse the JSON response
            result = json.loads(response.choices[0].message.content)
            translation = result.get("translation", "")
            new_terms_array = result.get("new_glossary_terms", [])

            # Ensure translation has reasonable formatting
            translation = post_process_translation(translation)

            # Filter and validate the new terms suggested by the AI
            # Note: existing_glossary_terms is passed to filter_new_terms, not existing_terms_list
            filtered_new_terms_list = filter_new_terms(
                new_terms_array, existing_glossary_terms, strict_mode
            )
            new_terms_dict = dict(filtered_new_terms_list)

            if len(new_terms_array) > len(filtered_new_terms_list):
                log(
                    f"Filtered glossary terms: {len(filtered_new_terms_list)} out of {len(new_terms_array)} suggested"
                )

            return translation, new_terms_dict

        except json.JSONDecodeError as e:
            log(f"Failed to parse JSON response on attempt {attempt}: {e}")
            if attempt < RETRY_ATTEMPTS:
                log(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
        except Exception as e:
            # Handle server errors with retries, other exceptions break immediately
            if "InternalServerError" in str(e) or "500" in str(e): # Basic check for server-side issues
                log(f"Attempt {attempt}/{RETRY_ATTEMPTS} failed with server error: {e}")
                if attempt < RETRY_ATTEMPTS:
                    log(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
            else:
                log(f"Unexpected error: {e}")
                break # Non-retryable error

    log("Failed to translate and extract terms after multiple attempts.")
    raise RuntimeError("Translation and glossary extraction failed")


def post_process_translation(text: str) -> str:
    """
    Post-processes translated text to improve formatting and paragraph structure.

    This includes stripping extra whitespace, ensuring consistent paragraph breaks,
    and attempting to structure text that might have been returned as a single block.

    Args:
        text: The translated text from the AI.

    Returns:
        The post-processed translated text.
    """
    if not text or not text.strip(): # Handle empty or whitespace-only input
        return text

    # Process lines: strip whitespace from each line, preserve intentional empty lines for paragraph breaks
    lines = text.split("\n")
    processed_lines = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line:
            processed_lines.append(stripped_line)
        else:
            # Keep empty lines if they were not just whitespace, or if previous line was not empty
            if not processed_lines or processed_lines[-1]: # Add "" if it's a real break
                 processed_lines.append("")


    result = "\n".join(processed_lines)

    # Normalize multiple newlines to a maximum of two (one empty line)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")

    result = result.strip() # Remove leading/trailing whitespace from the whole text

    # Heuristic: If the text is long and has no newlines, it might be a single block.
    # Try to split it based on common dialogue or sentence ending patterns.
    if "\n" not in result and len(result) > 500: # Threshold to avoid over-processing short texts
        # Attempt to split after dialogue ending with a quote, followed by an uppercase letter (potential new speaker/paragraph)
        result = re.sub(r'("[^"]*")\s+([A-Z])', r"\1\n\n\2", result)
        # Attempt to split after a sentence ending with a period, followed by an uppercase letter (potential new paragraph)
        result = re.sub(r"(\w\.)\s+([A-Z][a-z])", r"\1\n\n\2", result)

    return result


def get_chapter_files(raw_folder: Path) -> List[Path]:
    """
    Gets a naturally sorted list of chapter files ('.txt', '.md') from the raw folder.

    Args:
        raw_folder: The Path object representing the folder containing raw chapter files.

    Returns:
        A list of Path objects for chapter files, sorted naturally.
    """
    chapter_files = []
    # Supported extensions
    for ext in ["*.txt", "*.md"]:
        chapter_files.extend(raw_folder.glob(ext))

    # Natural sort key function to handle numbers in filenames correctly (e.g., chapter_10 after chapter_2)
    def natural_sort_key(path: Path):
        # Extract numbers from the filename stem
        numbers = re.findall(r"\d+", path.stem)
        if numbers:
            # Convert numeric parts to integers for correct sorting
            return [int(num) if num.isdigit() else num for num in numbers]
        return [path.stem] # Fallback to stem if no numbers

    return sorted(chapter_files, key=natural_sort_key)


def generate_initial_glossary(config: Config) -> None:
    """
    Generates an initial glossary from the first few chapters of the novel.

    The number of chapters used is defined by `GLOSSARY_INIT_CHAPTERS`.
    The generated terms are saved to the glossary file and can be reviewed by the user.

    Args:
        config: The main Config object.
    """
    if not config.glossary.enabled:
        return

    chapter_files = get_chapter_files(config.paths.raw_dir)
    if not chapter_files:
        log("No chapter files found for glossary generation")
        return

    # Select the first N chapters for initial glossary generation
    init_files = chapter_files[:GLOSSARY_INIT_CHAPTERS]
    log(f"Generating initial glossary from {len(init_files)} chapters...")

    # Combine the text of these initial chapters
    combined_text = ""
    for chapter_file in init_files:
        try:
            with open(chapter_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content: # Ensure content is not just whitespace
                    combined_text += f"\n\n{content}" # Add separator for readability
        except Exception as e:
            log(f"Error reading {chapter_file.name} for glossary generation: {e}")

    if not combined_text.strip():
        log("No content found in initial chapters for glossary generation.")
        return

    try:
        # Call AI to generate glossary terms from the combined text
        new_terms_dict = generate_glossary_from_text(
            text=combined_text,
            api_config=config.api,
            prompt_config=config.prompt, # Although not directly used by current generate_glossary prompt, passed for consistency
            existing_glossary=config.glossary.terms # Pass current terms to avoid duplicates
        )

        if new_terms_dict:
            config.glossary.terms.update(new_terms_dict) # Add new terms to GlossaryConfig
            config.glossary.save() # Save updated glossary
            log(f"Generated {len(new_terms_dict)} initial glossary terms.")

            # Allow user to review and confirm the generated glossary
            if not config.cli_args.skip_glossary_review:
                print("\nGenerated glossary terms for review:")
                for term, definition in new_terms_dict.items():
                    print(f"  {term}: {definition}")

                response = input("\nContinue with this glossary? (y/N): ").strip().lower()
                if response not in ["y", "yes", ""]:
                    log("Glossary generation cancelled by user. Exiting.")
                    sys.exit(0)
        else:
            log("No glossary terms were generated from the initial chapters.")
    except Exception as e:
        log(f"Error during initial glossary generation: {e}")


def generate_glossary_from_text(
    text: str,
    api_config: ApiConfig,
    prompt_config: PromptConfig, # Parameter kept for future consistency, not directly used in this prompt
    existing_glossary: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Generates glossary terms from a given block of text using an AI model.

    This function is typically used for generating the initial glossary.

    Args:
        text: The text to analyze for glossary terms.
        api_config: ApiConfig object for API client setup.
        prompt_config: PromptConfig object (currently unused in this specific function's prompt construction but included for future consistency).
        existing_glossary: A dictionary of existing terms to avoid suggesting duplicates.

    Returns:
        A dictionary of new glossary terms {term: definition}.

    Raises:
        RuntimeError: If glossary generation fails after multiple retry attempts.
    """
    client = create_openai_client(api_config)
    existing_terms_list = list(existing_glossary.keys()) if existing_glossary else []
    existing_text_prompt_segment = (
        f"\n\nExisting glossary terms (don't repeat these): {', '.join(existing_terms_list)}"
        if existing_terms_list
        else ""
    )

    # This prompt is specifically for initial glossary generation from a block of text
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

    # Retry loop for API call
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=api_config.model,
                messages=[{"role": "user", "content": prompt}]
            )
            result_text = response.choices[0].message.content.strip()

            # Parse the AI's response (expected to be lines of "term: definition")
            generated_terms = {}
            for line in result_text.split("\n"):
                line = line.strip()
                if line and ":" in line:
                    term, definition = line.split(":", 1)
                    term = term.strip()
                    definition = definition.strip()
                    if term and definition: # Ensure both term and definition are non-empty
                        generated_terms[term] = definition

            return generated_terms

        except Exception as e:
            if "InternalServerError" in str(e) or "500" in str(e): # Basic check for server-side issues
                log(
                    f"Glossary generation attempt {attempt}/{RETRY_ATTEMPTS} failed with server error: {e}"
                )
                if attempt < RETRY_ATTEMPTS:
                    log(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
            else:
                log(f"Unexpected error generating glossary: {e}")
                break # Non-retryable error

    log("Failed to generate glossary after multiple attempts.")
    raise RuntimeError("Glossary generation failed")


def parse_args() -> argparse.Namespace:
    """
    Parses command-line arguments for the translator script.

    Returns:
        An argparse.Namespace object containing the parsed arguments.
    """
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
        help="API key for the selected provider (overrides config).",
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
    """
    Main entry point for the novel translator script.

    Handles argument parsing, configuration loading, glossary management,
    and iterates through chapter files to translate them.
    """
    args = parse_args()

    # Validate novel directory existence
    if not args.novel_directory.exists():
        log(f"Error: Novel directory '{args.novel_directory}' does not exist.")
        sys.exit(1)

    # Initialize configuration from CLI args and config file
    config = Config(args.novel_directory, args)

    # Handle glossary regeneration if requested
    if args.regenerate_glossary:
        if config.paths.glossary_file.exists():
            try:
                config.paths.glossary_file.unlink() # Delete existing glossary file
                log("Deleted existing glossary for regeneration.")
            except OSError as e:
                log(f"Error deleting glossary file for regeneration: {e}")
        config.glossary.terms = {} # Reset terms in memory

    # Generate initial glossary if it's enabled but missing or regeneration is forced
    if config.glossary.enabled and (not config.glossary.terms or args.regenerate_glossary):
        generate_initial_glossary(config)

    # Get list of chapter files to translate
    chapter_files = get_chapter_files(config.paths.raw_dir)
    if not chapter_files:
        log(f"No chapter files found in '{config.paths.raw_dir}'.")
        sys.exit(1)

    log(f"Found {len(chapter_files)} chapter files to process.")

    translated_count = 0
    # Main loop: Iterate through each chapter file
    for chapter_file in chapter_files:
        output_filename = f"{chapter_file.stem}.txt" # Use original stem for output, with .txt extension
        output_file_path = config.paths.translated_dir / output_filename

        # Skip if chapter has already been translated
        if output_file_path.exists():
            log(f"Skipping '{chapter_file.name}': already translated as '{output_filename}'.")
            continue

        log(f"Translating '{chapter_file.name}'...")

        try:
            # Read chapter content
            with open(chapter_file, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                log(f"Skipping empty file: '{chapter_file.name}'.")
                continue

            # Prepare glossary text for the prompt
            glossary_prompt_text = config.glossary.get_text_for_prompt()

            # Perform translation and extract new glossary terms
            translation, new_terms_dict = translate_and_extract_terms(
                text=content,
                config=config,
                glossary_text=glossary_prompt_text,
                existing_glossary_terms=config.glossary.terms,
                strict_mode=args.strict_glossary, # Pass strict_glossary flag from CLI args
            )

            # Update glossary with new terms if any were found
            if new_terms_dict:
                config.glossary.terms.update(new_terms_dict)
                config.glossary.save() # Save glossary after updating
                log(f"Added {len(new_terms_dict)} new terms to glossary for '{chapter_file.name}'.")

            # Save the translated chapter
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(translation)

            log(f"Saved translation to '{output_filename}'.")
            translated_count += 1

        except Exception as e: # Catch broad exceptions during individual chapter processing
            log(f"Error translating '{chapter_file.name}': {e}")
            # Optionally, decide if this error should stop the whole process or just skip the chapter
            continue # Continue with the next chapter

    log(f"Translation complete: {translated_count} chapter(s) translated.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user. Exiting.")
        sys.exit(0)
