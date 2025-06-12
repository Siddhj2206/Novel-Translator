# Book Translator

This script provides a command-line interface for translating book chapters using different AI providers. It supports translation with glossary management, retry logic, and per-book configuration through config files.

## Features

- **Glossary:** Automatically maintains character names, places, and unique terms
- **Format Preservation:** Keeps paragraph structure and dialogue formatting
- **Per-Book Config:** Separate settings for each book via `config.json`
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
YourBook/
├── config.json           # Book configuration
├── glossary.txt          # Auto-generated terms (optional)
├── raw/                  # Raw chapter files (.md, .txt)
└── translated/           # Output folder
```

## Configuration

Create `config.json` in your book directory:

```json
{
  "api_key": "YOUR_API_KEY_HERE",
  "provider": "gemini",
  "model": "gemini-2.5-flash-preview-05-20",
  "base_prompt": "Translate this fantasy book chapter to natural English.",
  "raw_folder": "raw",
  "translated_folder": "tl"
}
```

### Configuration Options

- **`provider`** (optional): AI provider to use
  - `"gemini"` (default) - Uses Google's Gemini models
  - `"openai"` - Uses OpenAI's GPT models
  - `"anthropic"` - Uses Anthropic's Claude models
  - `"other"` - Custom provider (requires `base_url` and `model` in config)
- **`model`** (optional): Specific model to use. If not specified, uses provider's default:
  - Gemini: `gemini-2.5-flash-preview-05-20`
  - OpenAI: `gpt-4.1-nano-2025-04-14`
  - Anthropic: `claude-sonnet-4-20250514`
  - Other: Required when using `"other"` provider
- **`api_key`**: Your API key for the selected provider
- **`base_url`** (required for "other" provider): Custom API endpoint URL
- **`base_prompt`**: Custom translation prompt
- **`raw_folder`**: Folder containing raw chapter files
- **`translated_folder`**: Output folder for translations

**Note:** Base URLs are built into the program for standard providers - you only need to specify the provider name. For custom endpoints, use the "other" provider with your own `base_url`.

## Usage

```bash
# Basic usage
uv run translator.py /path/to/YourBook

# With custom API key
uv run translator.py /path/to/YourBook --api_key YOUR_KEY

# Regenerate glossary
uv run translator.py /path/to/YourBook --regenerate_glossary

# Disable glossary
uv run translator.py /path/to/YourBook --no_glossary

# Skip glossary review prompt
uv run translator.py /path/to/YourBook --skip_glossary_review

# Use strict glossary filtering (max 1 new term per chapter)
uv run translator.py /path/to/YourBook --strict_glossary
```

## Arguments

- `book_directory` - Path to book root directory
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

- **Strict limits** on new terms per chapter (2 by default, 1 with `--strict_glossary`)
- **Smart prioritization** based on term frequency and original language names
- **Enhanced prompts** that strongly discourage unnecessary additions

### Cleaning Existing Glossaries

If you have an existing bloated glossary, use the cleanup utility:

```bash
# Preview what would be removed
uv run cleanup_glossary.py /path/to/YourBook --dry-run

# Clean the glossary (creates backup automatically)
uv run cleanup_glossary.py /path/to/YourBook

# Clean without creating backup
uv run cleanup_glossary.py /path/to/YourBook --no-backup
```

The cleanup tool removes:
- Terms with generic descriptions
- Low-value entries that don't need translation consistency
- Preserves terms with original language names in brackets

**Note:**
Use `--strict_glossary` for more aggressive filtering if needed (max 1 new term per chapter instead of 2).
