# Novel Translator

This script provides a command-line interface for translating novel chapters using different AI providers. It supports translation with glossary management, retry logic, and per-novel configuration through config files.

## Features

- **Glossary:** Automatically maintains character names, places, and unique terms
- **Format Preservation:** Keeps paragraph structure and dialogue formatting
- **Per-Novel Config:** Separate settings for each novel via `config.json`
- **Skip Existing:** Only translates new chapters

## Setup

1. **Install Dependencies:**
   ```bash
   uv sync
   ```

2. **Get an API Key**
   - **Gemini (default):** Get a Google AI Studio API key
   - **OpenAI:** Get an OpenAI API key
   - **Anthropic:** Get an Anthropic API key

## Directory Structure

```
YourNovel/
├── config.json           # Novel configuration
├── glossary.txt          # Auto-generated terms (optional)
├── raw/                  # Raw chapter files (.txt)
└── translated/           # Default output folder (auto-created, can be changed in config.json, e.g., to "tl")
```

## Configuration

Create `config.json` in your novel directory:

```json
{
  "api_key": "YOUR_API_KEY_HERE",
  "provider": "gemini",
  "model": "gemini-2.5-flash-preview-05-20",
  "base_prompt": "Translate this fantasy novel chapter to natural English.",
  "raw_folder": "raw",
  "translated_folder": "translated"
}
```

### Configuration Options

- **`api_key`**: Your API key for the selected provider. This is **required** either in the config file or via the `--api_key` argument.
- **`provider`** (optional): AI provider to use. Defaults to `"gemini"`.
  - `"gemini"`: Google's Gemini models.
  - `"openai"`: OpenAI's GPT models.
  - `"anthropic"`: Anthropic's Claude models.
  - `"other"`: Custom provider (requires `base_url` and `model` to be set in this config file).
- **`model`** (optional): Specific model to use. If not specified, uses the provider's default model.
  - For `"other"` provider, this field is required.
- **`base_url`** (required for "other" provider): Custom API endpoint URL when `provider` is `"other"`.
- **`base_prompt`** (optional): Custom base prompt for translation. Defaults to "Translate this novel chapter from Japanese to natural, fluent English."
- **`raw_folder`** (optional): Folder containing raw chapter files. Defaults to `raw`.
- **`translated_folder`** (optional): Output folder for translations. Defaults to `translated`.

**Default Models by Provider:**

| Provider  | Default Model                   |
|-----------|---------------------------------|
| Gemini    | `gemini-2.5-flash-preview-05-20`|
| OpenAI    | `gpt-4.1-nano-2025-04-14`        |
| Anthropic | `claude-sonnet-4-20250514`      |

**Note:** For standard providers (Gemini, OpenAI, Anthropic), their base URLs are pre-configured. You only need to specify your `api_key` and optionally a specific `model`. If you use `provider: "other"`, you must also provide `base_url` and `model`.

## Usage

```bash
# Basic usage
uv run translator.py /path/to/YourNovel

# With custom API key
uv run translator.py /path/to/YourNovel --api_key YOUR_KEY

# Regenerate glossary
uv run translator.py /path/to/YourNovel --regenerate_glossary

# Disable glossary
uv run translator.py /path/to/YourNovel --no_glossary

# Skip glossary review prompt
uv run translator.py /path/to/YourNovel --skip_glossary_review

# Use strict glossary filtering (max 1 new term per chapter)
uv run translator.py /path/to/YourNovel --strict_glossary
```

## Arguments

- `novel_directory` - Path to novel root directory
- `--api_key` - Override API key from config
- `--raw_folder` - Override raw chapters folder
- `--translated_folder` - Override output folder
- `--base_prompt` - Override translation prompt
- `--regenerate_glossary` - Rebuild glossary from scratch
- `--no_glossary` - Disable glossary usage
- `--skip_glossary_review` - Skip user confirmation after generating initial glossary
- `--strict_glossary` - Use stricter glossary filtering (max 1 new term per chapter)

## Glossary

The tool automatically creates a `glossary.txt` file with critical terms for translation:

- **Auto-generated** from first 5 chapters
- **Progressive updates** as new terms are discovered
- **Preserves original names** in brackets: `Akira [明]: Main character`
- **Focused on essentials**: Character names, places, unique concepts

Use `--regenerate_glossary` to rebuild, `--no_glossary` to disable, or `--skip_glossary_review` to bypass the review prompt.

## Glossary Management

The translation script (`translator.py`) includes several mechanisms for managing the glossary:

- **Initial Generation:** When a glossary is first created (or regenerated using `--regenerate_glossary`), it's built from the content of the first few chapters (defined by `GLOSSARY_INIT_CHAPTERS`, default: 5).
- **Term Extraction During Translation:** For each subsequent chapter, the AI attempts to extract new, essential glossary terms.
    - By default, it can add up to `MAX_NEW_TERMS_PER_CHAPTER` (default: 10) new terms.
    - If the `--strict_glossary` flag is used, this limit is reduced to `MAX_NEW_TERMS_PER_CHAPTER_STRICT` (default: 1).
- **Filtering New Terms:**
    - Suggested new terms are filtered to prevent duplicates (case-insensitive and checks base term if original language is provided like `Term [Original]`).
    - The number of new terms added per chapter is capped by the limits mentioned above.
- **Glossary Size Limit:** The total number of entries in the glossary is capped at `MAX_GLOSSARY_ENTRIES` (default: 1000). If it exceeds this, older entries are removed.
- **Prompt Engineering:** The prompts used for translation and term extraction are designed to be highly restrictive, instructing the AI to only include truly essential terms (main characters, major locations, core concepts).

### Cleaning Existing Glossaries

If you have an existing bloated glossary, use the cleanup utility:

```bash
# Preview what would be removed
uv run cleanup_glossary.py /path/to/YourNovel --dry-run

# Clean the glossary (creates backup automatically)
uv run cleanup_glossary.py /path/to/YourNovel

# Clean without creating backup
uv run cleanup_glossary.py /path/to/YourNovel --no-backup

# Specify minimum occurrences (Note: this feature is not fully implemented in the script's logic yet)
uv run cleanup_glossary.py /path/to/YourNovel --min-occurrences 3
```

**`cleanup_glossary.py` Arguments:**

- `novel_directory`: Path to the novel directory containing `glossary.txt`.
- `--no-backup`: (Flag) Prevents the creation of a backup file (`glossary.txt.backup`).
- `--dry-run`: (Flag) Shows which terms would be removed without actually modifying the glossary file.
- `--min-occurrences <N>`: (Integer, default: 1) Sets a minimum number of occurrences for a term to be kept. *Currently, this argument is parsed but not yet implemented in the exclusion logic of the script.*

The cleanup tool removes:
- Terms with generic descriptions
- Low-value entries that don't need translation consistency
- Preserves terms with original language names in brackets

**Note on `translator.py`'s `--strict_glossary` flag:**
This flag makes the AI and the filtering logic much stricter about adding new terms during translation, limiting new additions to typically 0-1 per chapter. It internally uses the `MAX_NEW_TERMS_PER_CHAPTER_STRICT` constant.
