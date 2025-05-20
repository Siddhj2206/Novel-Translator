import google.generativeai as genai
import os
import argparse
import json
import time
import google.api_core.exceptions
import sys
from datetime import datetime
import concurrent.futures  # Added for concurrency


# Helper function for timestamped print
def print_ts(message):
    """Prints a message prepended with a [HH:MM] timestamp."""
    current_time = datetime.now().strftime("%H:%M")
    print(f"[{current_time}] {message}")


def translate_text(text, api_key, base_prompt, max_retries=3, delay_seconds=5):
    """Translates text using the Gemini API with retry logic."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
    prompt = f"{base_prompt}\n\n{text}"

    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except google.api_core.exceptions.InternalServerError as e:
            print_ts(
                f"Attempt {attempt + 1} of {max_retries} failed with Internal Server Error: {e}"
            )
            if attempt < max_retries - 1:
                print_ts(f"Retrying in {delay_seconds} seconds...")
                time.sleep(delay_seconds)
            else:
                print_ts("All retry attempts failed.")
                raise
        except Exception as e:
            print_ts(f"An unexpected error occurred during translation: {e}")
            raise
    # The following line is unreachable if an exception is always raised on failure, as intended.
    # return "Error: Translation failed after multiple retries."


def main():
    try:
        MAX_CONCURRENT_TRANSLATIONS = (
            2  # Configurable number of concurrent translations
        )

        parser = argparse.ArgumentParser(
            description="Translate novel chapters using Gemini API."
        )
        parser.add_argument(
            "novel_directory",
            help="Path to the novel's root directory (e.g., ./MyNovel). This directory should contain your config.json and chapter folders.",
        )
        parser.add_argument(
            "--api_key",
            help="Google AI Studio API Key. Overrides 'api_key' in novel's config.json if present.",
        )  # Made optional
        parser.add_argument(
            "--raw_folder",
            help="Path to the folder containing raw chapter files. Overrides config and defaults to '<novel_directory>/raw'.",
        )
        parser.add_argument(
            "--translated_folder",
            help="Path to the folder where translated chapters will be stored. Overrides config and defaults to '<novel_directory>/translated'.",
        )
        parser.add_argument(
            "--base_prompt",
            default="Translate the following Korean text to English:",
            help="Base prompt for translation. Is overridden by 'base_prompt' in novel's config.json if present.",
        )

        args = parser.parse_args()

        novel_root_path = os.path.abspath(args.novel_directory)
        config_filepath = os.path.join(novel_root_path, "config.json")

        # Default names for chapter folders (relative to novel_root_path)
        default_raw_folder_name = "raw"
        default_translated_folder_name = "translated"

        # Initialize variables for resolved paths and prompt
        # Start with CLI arg (which has a default)
        final_base_prompt = args.base_prompt
        final_raw_folder_path = None
        final_translated_folder_path = None
        final_api_key = args.api_key  # Initialize with CLI arg

        # Values from config file
        config_base_prompt = None
        config_raw_folder_relative_path = None
        config_translated_folder_relative_path = None
        config_api_key = None  # Added for config API key

        if os.path.exists(config_filepath):
            try:
                with open(config_filepath, "r", encoding="utf-8") as f:
                    config = json.load(f)
                config_base_prompt = config.get("base_prompt")
                config_raw_folder_relative_path = config.get("raw_folder")
                config_translated_folder_relative_path = config.get("translated_folder")
                # Get API key from config
                config_api_key = config.get("api_key")
                print_ts(f"Loaded configuration from {config_filepath}")
            except json.JSONDecodeError:
                print_ts(
                    f"Error: Could not decode {config_filepath}. Using defaults or CLI arguments."
                )
            except Exception as e:
                print_ts(
                    f"Error reading {config_filepath}: {e}. Using defaults or CLI arguments."
                )
        else:
            print_ts(
                f"No config.json found at {config_filepath}. Using defaults or CLI arguments."
            )

        # Determine final api_key
        if args.api_key:  # CLI argument for api_key takes highest precedence
            final_api_key = args.api_key
            print_ts("Using API key from CLI argument.")
        elif config_api_key:  # Then config file
            final_api_key = config_api_key
            print_ts("Using API key from config file.")

        if not final_api_key:
            print_ts(
                "Error: API Key not found. Please provide it via CLI argument (--api_key) or in the config.json file."
            )
            return

        # Determine final base_prompt
        if config_base_prompt is not None:
            final_base_prompt = config_base_prompt
            print_ts(f"Using base_prompt from config: '{final_base_prompt}'")
        else:
            print_ts(f"Using base_prompt from CLI/default: '{final_base_prompt}'")

        # Determine final raw_folder_path
        if args.raw_folder:  # CLI argument for raw_folder takes highest precedence
            final_raw_folder_path = os.path.abspath(args.raw_folder)
            print_ts(f"Using raw_folder from CLI argument: {final_raw_folder_path}")
        elif config_raw_folder_relative_path:  # Then config file
            final_raw_folder_path = os.path.join(
                novel_root_path, config_raw_folder_relative_path
            )
            print_ts(f"Using raw_folder from config: {final_raw_folder_path}")
        else:  # Then default
            final_raw_folder_path = os.path.join(
                novel_root_path, default_raw_folder_name
            )
            print_ts(f"Using default raw_folder: {final_raw_folder_path}")

        # Determine final translated_folder_path
        if (
            args.translated_folder
        ):  # CLI argument for translated_folder takes highest precedence
            final_translated_folder_path = os.path.abspath(args.translated_folder)
            print_ts(
                f"Using translated_folder from CLI argument: {final_translated_folder_path}"
            )
        elif config_translated_folder_relative_path:  # Then config file
            final_translated_folder_path = os.path.join(
                novel_root_path, config_translated_folder_relative_path
            )
            print_ts(
                f"Using translated_folder from config: {final_translated_folder_path}"
            )
        else:  # Then default
            final_translated_folder_path = os.path.join(
                novel_root_path, default_translated_folder_name
            )
            print_ts(f"Using default translated_folder: {final_translated_folder_path}")

        # Ensure paths are absolute
        final_raw_folder_path = os.path.abspath(final_raw_folder_path)
        final_translated_folder_path = os.path.abspath(final_translated_folder_path)

        if not os.path.isdir(final_raw_folder_path):
            print_ts(
                f"Error: Raw folder not found at {final_raw_folder_path}. Please create it and add your chapter files."
            )
            return

        # Create output folder if it doesn't exist
        if not os.path.exists(final_translated_folder_path):
            os.makedirs(final_translated_folder_path)
            print_ts(f"Created translated folder: {final_translated_folder_path}")

        # Use ThreadPoolExecutor for concurrent translations
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_TRANSLATIONS
        ) as executor:
            future_to_chapter_info = {}

            for filename in os.listdir(final_raw_folder_path):
                if filename.endswith(".txt"):
                    raw_filepath = os.path.join(final_raw_folder_path, filename)
                    translated_filepath = os.path.join(
                        final_translated_folder_path, filename
                    )

                    if os.path.exists(translated_filepath):
                        print_ts(f"Chapter {filename} already translated. Skipping.")
                        continue

                    with open(raw_filepath, "r", encoding="utf-8") as f:
                        raw_text = f.read()

                    print_ts(f"Submitting {filename} for translation...")
                    future = executor.submit(
                        translate_text, raw_text, final_api_key, final_base_prompt
                    )
                    future_to_chapter_info[future] = (filename, translated_filepath)

            for future in concurrent.futures.as_completed(future_to_chapter_info):
                filename, translated_filepath = future_to_chapter_info[future]
                try:
                    translated_text = future.result()  # Get the translation result
                    with open(translated_filepath, "w", encoding="utf-8") as f:
                        f.write(translated_text)
                    print_ts(
                        f"Saved translated chapter {filename} to {translated_filepath}"
                    )
                except Exception as e:
                    print_ts(
                        f"Could not translate {filename}: {e}. Skipping file creation for this chapter."
                    )

    except KeyboardInterrupt:
        print_ts("\nTranslation process interrupted by user. Exiting gracefully.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)


if __name__ == "__main__":
    main()
