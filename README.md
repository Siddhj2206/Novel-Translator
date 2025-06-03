# Novel Translator CLI

This Python script provides a command-line interface (CLI) to translate novel chapters using the Google Gemini API. It supports novel-specific configurations, allowing for different base prompts, chapter folder locations, and API keys for each novel.

## Features

- **Sequential Translation:** Translates multiple chapter files (`.txt`) from a specified raw chapters folder in order for optimal glossary progression.
- **Smart Glossary Management:** Creates and maintains a `glossary.txt` file with critical proper nouns and unique terms for consistent translation.
- **Configurable per Novel:** Uses a `config.json` file within each novel's directory to manage:
  - `base_prompt`: The specific prompt to guide the Gemini API for translation (e.g., tone, style).
  - `raw_folder`: Relative path to the folder containing raw chapter files.
  - `translated_folder`: Relative path to the folder where English translated chapters will be saved.
  - `api_key`: Your Google AI Studio API Key.
- **CLI Overrides:** Allows overriding `config.json` settings using command-line arguments.
- **Incremental Translation:** Skips chapters that have already been translated and exist in the translated folder.
- **Progressive Glossary Updates:** Automatically updates the glossary with new critical terms found in each chapter, ensuring later chapters benefit from earlier discoveries.
- **Organized Output:** Saves translated chapters with the same filename as the raw chapter in the designated translated folder.

## Prerequisites

- Python 3.x
- pip (Python package installer)
- A Google AI Studio API Key with access to the Gemini API.

## Setup

1.  **Place the Script:**
    Ensure `translator.py` and `requirements.txt` are in your desired project directory.

2.  **Install Dependencies:**
    Open your terminal or command prompt, navigate to the directory containing `requirements.txt`, and run:
    ```bash
    pip install -r requirements.txt
    ```

## Novel Directory Structure

For each novel you want to translate, you should set up a directory structure like this:

```
YourNovelName/
├── config.json
├── glossary.txt  <-- Automatically generated and maintained
├── raw_chapters/  <-- Or whatever you name it in config.json or CLI
│   ├── chapter1.txt
│   ├── chapter2.txt
│   └── ...
└── translated_chapters/ <-- Or whatever you name it in config.json or CLI
    ├── chapter1.txt
    ├── chapter2.txt
    └── ...
```

- **`YourNovelName/`**: This is the main directory for your novel. You will point the script to this directory.
- **`config.json`**: Configuration file for this specific novel.
- **`glossary.txt`**: Automatically generated file containing critical character names, places, and unique terms for consistent translation.
- **`raw_chapters/`**: Contains the raw chapter text files.
- **`translated_chapters/`**: The script will create this folder (if it doesn't exist) and save the translated English chapters here.

## `config.json` File

Create a `config.json` file in the root of each novel's directory (`YourNovelName/config.json`).

**Example `config.json`:**

```json
{
  "base_prompt": "Translate the following fantasy novel chapter into colloquial English, maintaining a sense of suspense and adventure.",
  "raw_folder": "raw",
  "translated_folder": "tl",
  "api_key": "YOUR_GOOGLE_AI_STUDIO_API_KEY_HERE"
}
```

**Fields:**

- `"base_prompt"` (string, optional): The instruction given to the Gemini model before the chapter text. If omitted, the CLI default is used.
- `"raw_folder"` (string, optional): Relative path from the novel directory to the folder containing raw chapters. Defaults to `"raw"` if omitted.
- `"translated_folder"` (string, optional): Relative path from the novel directory to the folder where translated chapters will be saved. Defaults to `"translated"` if omitted.
- `"api_key"` (string, optional): Your Google AI Studio API Key. The script will error if no API key is found via config or CLI.

## Usage

Run the script from your terminal, providing the path to the novel's root directory.

**Basic Usage (using `config.json` for API key and other settings):**

```bash
python translator.py /path/to/YourNovelName
```

**Overriding `config.json` settings with CLI arguments:**

```bash
# Override API key
python translator.py /path/to/YourNovelName --api_key YOUR_OTHER_API_KEY

# Override base prompt
python translator.py /path/to/YourNovelName --base_prompt "Translate this formally."

# Override raw and translated folder paths
python translator.py /path/to/YourNovelName --raw_folder source_files --translated_folder output_files

# Combine overrides
python translator.py /path/to/YourNovelName --api_key YOUR_KEY --base_prompt "New prompt" --raw_folder chapters_kr --translated_folder chapters_en
```

**Glossary Management:**

```bash
# Regenerate glossary from scratch using initial chapters
python translator.py /path/to/YourNovelName --regenerate_glossary

# Disable glossary usage for this translation session
python translator.py /path/to/YourNovelName --no_glossary
```

## Command-Line Arguments

```
usage: translator.py [-h] [--api_key API_KEY] [--raw_folder RAW_FOLDER]
                     [--translated_folder TRANSLATED_FOLDER]
                     [--base_prompt BASE_PROMPT] [--regenerate_glossary]
                     [--no_glossary]
                     novel_directory

Translate novel chapters using Gemini API.

positional arguments:
  novel_directory       Path to the novel's root directory (e.g., ./MyNovel).
                        This directory should contain your config.json and
                        chapter folders.

options:
  -h, --help            show this help message and exit
  --api_key API_KEY     Google AI Studio API Key. Overrides 'api_key' in
                        novel's config.json if present.
  --raw_folder RAW_FOLDER
                        Path to the folder containing raw chapter files.
                        Overrides config and defaults to
                        '<novel_directory>/raw'.
  --translated_folder TRANSLATED_FOLDER
                        Path to the folder where translated chapters will be
                        stored. Overrides config and defaults to
                        '<novel_directory>/translated'.
  --base_prompt BASE_PROMPT
                        Base prompt for translation. Is overridden by
                        'base_prompt' in novel's config.json if present.
                        (default: Translate the following text to English:)
  --regenerate_glossary
                        Regenerate glossary from scratch using initial chapters.
  --no_glossary         Disable glossary usage for this translation session.
```

## How it Works

1.  The script parses command-line arguments.
2.  It locates the `novel_directory` and attempts to load `config.json`.
3.  It resolves the final settings (API key, base prompt, raw folder path, translated folder path) by prioritizing CLI arguments, then `config.json` values, and finally internal defaults.
4.  It checks if the raw folder exists.
5.  It creates the translated folder if it doesn't exist.
6.  **Glossary Management:** It loads or generates a glossary of important terms from the first few chapters.
7.  It processes each `.txt` file in the raw folder sequentially (in alphabetical order).
8.  For each file, it checks if a corresponding translated file already exists in the translated folder.
    - If yes, it skips the file.
    - If no, it reads the raw text, sends it to the Gemini API with the current glossary, base prompt, and API key, and saves the translated response to a new file in the translated folder.
9.  **Progressive Glossary Updates:** After each successful translation, it analyzes the chapter for new terms, updates the glossary, and uses the enhanced glossary for subsequent chapters.

## Glossary Feature

The translator automatically maintains a `glossary.txt` file that contains only the most critical proper nouns, character names, places, and unique concepts specific to your novel. The glossary is designed to be selective and focused, containing only terms that would cause confusion if translated inconsistently.

### How the Glossary Works:

- **Initial Generation:** When first run, the tool analyzes the first 3 chapters to create a selective initial glossary
- **Progressive Learning:** Chapters are processed sequentially, so each chapter benefits from terms discovered in all previous chapters
- **Conservative Updates:** As new chapters are processed, only new critical terms are added to prevent glossary bloat
- **Translation Integration:** The current glossary (including all updates from previous chapters) is included in every translation request
- **Smart Filtering:** Prevents duplicate entries and maintains focus on essential terms (max 50 entries)
- **Original Language Support:** Includes original language names in brackets when available (e.g., "Hero [Yūsha]: Main protagonist")

### What Gets Added to the Glossary:

**INCLUDED (Critical Terms Only):**
- Main character names and important side characters
- Specific place names (cities, kingdoms, regions)
- Unique magical/fantasy concepts specific to the story
- Named organizations, guilds, or factions
- Important artifacts, weapons, or magical items

**NOT INCLUDED (To Keep Focused):**
- Generic titles (guard, merchant, king)
- Common fantasy terms (magic, sword, dragon)
- Ordinary objects or locations
- Minor characters mentioned briefly

### Glossary Format:

The glossary is stored as a simple text file with entries like:
```
Kazuki [和希]: Main protagonist, former office worker
Aethermancy [エーテル術]: Unique magic system using life energy
Kingdom of Valdris [ヴァルドリス王国]: The northern kingdom where story begins
Shadow Guild [影の組合]: Secret organization of information brokers
```

### Managing the Glossary:

- Use `--regenerate_glossary` to rebuild the glossary from scratch using the first 3 chapters
- Use `--no_glossary` to translate without using the glossary (faster but less consistent)
- The glossary file can be manually edited if needed - follow the format: `Term [Original]: Description`
- Terms are automatically sorted alphabetically and limited to 50 most important entries
- The system processes chapters sequentially to ensure optimal glossary progression throughout the novel
- The system is conservative about adding new terms to prevent glossary bloat
