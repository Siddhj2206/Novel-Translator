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
   pip install -r requirements.txt
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
python translator.py /path/to/YourNovel

# With custom API key
python translator.py /path/to/YourNovel --api_key YOUR_KEY

# Regenerate glossary
python translator.py /path/to/YourNovel --regenerate_glossary

# Disable glossary
python translator.py /path/to/YourNovel --no_glossary
```

## Arguments

- `novel_directory` - Path to novel root directory
- `--api_key` - Override API key from config
- `--raw_folder` - Override raw chapters folder
- `--translated_folder` - Override output folder
- `--base_prompt` - Override translation prompt
- `--regenerate_glossary` - Rebuild glossary from scratch
- `--no_glossary` - Disable glossary usage

## Glossary

The tool automatically creates a `glossary.txt` file with critical terms for translation:

- **Auto-generated** from first 5 chapters
- **Progressive updates** as new terms are discovered
- **Preserves original names** in brackets: `Akira [明]: Main character`
- **Focused on essentials**: Character names, places, unique concepts

Use `--regenerate_glossary` to rebuild or `--no_glossary` to disable.

**Note:**
The glossary may get bloated over time as gemini likes to add everything to it even though it has been told to only add the essentials. It is advised to clean up the glossary.txt file from time to time.
