# Novel Translator

This script provides a command-line interface for translating novel chapters using Gemini. It supports translation with glossary management, retry logic, and per-novel configuration through config files.

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

2. **Get a Google AI Studio API Key**

## Directory Structure

```
YourNovel/
├── config.json           # Novel configuration
├── glossary.txt          # Auto-generated terms (optional)
├── raw/                  # Raw chapter files (.txt)
└── tl/                   # Output folder (auto-created)
```

## Configuration

Create `config.json` in your novel directory:

```json
{
  "base_prompt": "Translate this fantasy novel chapter to natural English.",
  "raw_folder": "raw",
  "translated_folder": "tl",
  "api_key": "YOUR_GOOGLE_AI_STUDIO_API_KEY"
}
```

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

The translator has been improved to be much more restrictive about adding terms to the glossary:

- **Automatic filtering** of common fantasy terms (sword, magic, king, etc.)
- **Strict limits** on new terms per chapter (2 by default, 1 with `--strict_glossary`)
- **Smart prioritization** based on term frequency and original language names
- **Enhanced prompts** that strongly discourage unnecessary additions

### Cleaning Existing Glossaries

If you have an existing bloated glossary, use the cleanup utility:

```bash
# Preview what would be removed
uv run cleanup_glossary.py /path/to/YourNovel --dry-run

# Clean the glossary (creates backup automatically)
uv run cleanup_glossary.py /path/to/YourNovel

# Clean without creating backup
uv run cleanup_glossary.py /path/to/YourNovel --no-backup
```

The cleanup tool removes:
- Common fantasy terms (weapons, titles, generic locations)
- Terms with generic descriptions
- Low-value entries that don't need translation consistency
- Preserves terms with original language names in brackets

**Note:**
With the improved filtering, Gemini should now add far fewer unnecessary terms. Use `--strict_glossary` for even more aggressive filtering if needed.
