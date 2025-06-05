#!/usr/bin/env python3
"""
Cleans glossary.txt by removing common/generic terms and low-occurrence entries.
Helps maintain translation consistency by pruning non-essential terms.
If a "raw" subdirectory with .txt files exists, uses it for term occurrence counts.
"""

import argparse
import sys
from pathlib import Path


def load_glossary(glossary_path: Path) -> dict:
    """
    Load glossary from a text file.

    Args:
        glossary_path: Path to the glossary file (e.g., "term: definition" per line).

    Returns:
        A dictionary {term: definition}. Empty if file not found or error.
    """
    glossary = {}
    
    if not glossary_path.exists():
        print(f"Error: Glossary file not found: {glossary_path}")
        return glossary
    
    try:
        with open(glossary_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    # Split only on the first colon to handle definitions that might contain colons
                    term, definition = line.split(':', 1)
                    term = term.strip()
                    definition = definition.strip()
                    if term and definition:
                        glossary[term] = definition
    except Exception as e:
        print(f"Error reading glossary: {e}")
    
    return glossary


def save_glossary(glossary: dict, glossary_path: Path, backup: bool = True):
    """
    Save glossary dictionary to a text file.

    Args:
        glossary: Glossary {term: definition} to save.
        glossary_path: Path to the output glossary file.
        backup: If True, backup existing file to glossary_path.backup.
    """
    if backup and glossary_path.exists():
        # Create a backup, e.g., glossary.txt -> glossary.txt.backup
        backup_path = glossary_path.with_suffix(glossary_path.suffix + '.backup') # Handles .txt.backup correctly
        glossary_path.rename(backup_path)
        print(f"Created backup: {backup_path}")
    
    try:
        with open(glossary_path, 'w', encoding='utf-8') as f:
            # Save terms sorted alphabetically for consistency
            for term, definition in sorted(glossary.items()):
                f.write(f"{term}: {definition}\n")
        print(f"Saved cleaned glossary: {glossary_path}")
    except Exception as e:
        print(f"Error saving glossary: {e}")


def get_excluded_terms() -> set:
    """Get set of common terms that should be excluded from glossary."""
    return {
        # Generic titles and roles
        'magic', 'sword', 'guild', 'king', 'queen', 'lord', 'lady', 'master', 'knight',
        'warrior', 'mage', 'priest', 'merchant', 'guard', 'soldier', 'captain', 'general',
        'princess', 'prince', 'duke', 'count', 'baron', 'noble', 'commoner', 'peasant',
        'servant', 'butler', 'maid', 'chef', 'cook', 'blacksmith', 'farmer', 'hunter',
        'adventurer', 'hero', 'villain', 'enemy', 'ally', 'friend', 'student', 'teacher',
        
        # Common locations
        'inn', 'tavern', 'shop', 'market', 'street', 'road', 'path', 'forest', 'mountain',
        'river', 'lake', 'sea', 'ocean', 'village', 'town', 'city', 'kingdom', 'empire',
        'castle', 'palace', 'tower', 'wall', 'gate', 'door', 'window', 'room', 'hall',
        'church', 'temple', 'shrine', 'school', 'academy', 'library', 'hospital', 'prison',
        'house', 'home', 'building', 'bridge', 'plaza', 'square', 'park', 'garden',
        
        # Common items and objects
        'weapon', 'armor', 'shield', 'bow', 'arrow', 'spear', 'axe', 'dagger', 'staff',
        'potion', 'scroll', 'book', 'letter', 'map', 'key', 'coin', 'gold', 'silver',
        'bronze', 'copper', 'iron', 'steel', 'wood', 'stone', 'leather', 'cloth',
        'food', 'water', 'wine', 'beer', 'bread', 'meat', 'fruit', 'vegetable',
        
        # Fantasy creatures and beings
        'monster', 'demon', 'devil', 'angel', 'god', 'goddess', 'spirit', 'ghost', 'soul',
        'dragon', 'wolf', 'bear', 'eagle', 'horse', 'dog', 'cat', 'bird', 'fish',
        'orc', 'elf', 'dwarf', 'human', 'beast', 'creature', 'animal',
        
        # Elements and magic terms
        'fire', 'water', 'earth', 'air', 'wind', 'ice', 'lightning', 'light', 'dark',
        'flame', 'smoke', 'steam', 'mist', 'fog', 'rain', 'snow', 'storm', 'thunder',
        'power', 'strength', 'speed', 'skill', 'ability', 'technique', 'method', 'way',
        'spell', 'enchantment', 'curse', 'blessing', 'ritual', 'ceremony', 'prayer',
        
        # Time and measurements
        'day', 'night', 'morning', 'afternoon', 'evening', 'dawn', 'dusk', 'hour',
        'minute', 'second', 'week', 'month', 'year', 'season', 'spring', 'summer',
        'autumn', 'winter', 'today', 'tomorrow', 'yesterday', 'past', 'future',
        
        # Colors and descriptions
        'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'brown',
        'black', 'white', 'gray', 'grey', 'golden', 'silver', 'dark', 'light',
        'bright', 'dim', 'small', 'large', 'big', 'tiny', 'huge', 'long', 'short',
        
        # Common verbs and actions
        'fight', 'battle', 'war', 'peace', 'attack', 'defend', 'protect', 'save',
        'help', 'kill', 'die', 'live', 'born', 'grow', 'learn', 'teach', 'study',
        'work', 'play', 'sleep', 'eat', 'drink', 'walk', 'run', 'fly', 'swim',
        
        # Body parts and clothing
        'head', 'face', 'eye', 'eyes', 'ear', 'nose', 'mouth', 'hand', 'hands',
        'arm', 'arms', 'leg', 'legs', 'foot', 'feet', 'body', 'heart', 'mind',
        'robe', 'dress', 'shirt', 'pants', 'shoes', 'hat', 'cloak', 'cape',
        
        # Family and relationships
        'father', 'mother', 'son', 'daughter', 'brother', 'sister', 'family',
        'parent', 'child', 'children', 'husband', 'wife', 'lover', 'friend',
        
        # Numbers (in various languages)
        'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
        'first', 'second', 'third', 'fourth', 'fifth', 'hundred', 'thousand', 'million'
    }


def count_term_occurrences(novel_text: str, glossary_terms: list[str]) -> dict[str, int]:
    """
    Count occurrences of each glossary term (case-insensitive) in the novel text.
    For terms like "Name [Original]", uses "Name" for searching.

    Args:
        novel_text: Full novel text.
        glossary_terms: List of terms from the glossary.

    Returns:
        Dictionary {original term: count}.
    """
    term_counts = {}
    if not novel_text: # Handle None or empty string
        return term_counts

    novel_text_lower = novel_text.lower() # Case-insensitive search

    for term in glossary_terms:
        # Use part before "[" as base term for searching, e.g., "Name" from "Name [Original]"
        base_search_term = term.split('[', 1)[0].strip() if '[' in term else term
        base_search_term_lower = base_search_term.lower()

        count = novel_text_lower.count(base_search_term_lower)
        term_counts[term] = count

    return term_counts


def clean_glossary(glossary: dict, excluded_terms: set, term_occurrences: dict[str, int], min_occurrences: int = 1) -> tuple[dict, list[str]]:
    """
    Filter glossary based on exclusion rules and minimum occurrences.

    Args:
        glossary: Input glossary {term: definition}.
        excluded_terms: Set of common terms (lowercase) to exclude.
        term_occurrences: {term: count} from `count_term_occurrences`.
        min_occurrences: Minimum occurrences to keep a term.

    Returns:
        Tuple: (cleaned_glossary: dict, removed_terms_log: list[str])
    """
    cleaned = {}
    removed_terms_log = [] # Log of removed terms and reasons
    
    for term, definition in glossary.items():
        # Base term for checks (lowercase, no bracket content)
        base_check_term = term.split('[')[0].strip().lower() if '[' in term else term.lower()
        
        should_exclude = False
        reason = ""
        
        # Exclusion rules (applied in order):
        # 1. Common terms (from `get_excluded_terms()`).
        if base_check_term in excluded_terms:
            should_exclude = True
            reason = "common term"
        
        # 2. Generic descriptions (e.g., "a type of...").
        if not should_exclude:
            definition_lower = definition.lower()
            generic_indicators = [ # Phrases indicating a generic, non-essential term
                'a type of', 'a kind of', 'general term', 'common', 'ordinary',
                'simple', 'basic', 'regular', 'normal', 'standard', 'typical',
                'generic', 'minor character', 'side character', 'background',
                'mentioned briefly', 'appears once', 'example of'
            ]
            if any(indicator in definition_lower for indicator in generic_indicators):
                should_exclude = True
                reason = "generic description"

        # 3. Low occurrences (count < `min_occurrences`).
        if not should_exclude:
            count = term_occurrences.get(term, 0)
            if count < min_occurrences:
                should_exclude = True
                reason = f"low occurrences (found {count}, min is {min_occurrences})"
        
        # Override: Terms with original names in brackets (e.g., "Name [オリオン]") are always kept.
        # This heuristic assumes such terms are specific proper nouns important for consistency.
        if '[' in term and ']' in term: # Check for presence of brackets
            if should_exclude: # Log if it overrides a previous exclusion reason
                print(f"INFO: Keeping term '{term}' due to original name override, despite reason: {reason}")
            should_exclude = False # Ensure it's not excluded
        
        if should_exclude:
            removed_terms_log.append(f"'{term}' (Reason: {reason})")
        else:
            cleaned[term] = definition

    return cleaned, removed_terms_log


def main():
    """
    Main entry point for the glossary cleanup script.
    Script entry point. Parses CLI args, loads data, cleans glossary, saves result.
    """
    parser = argparse.ArgumentParser(
        description="Clean glossary.txt by removing common/generic/low-occurrence terms.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Shows default values in help
    )
    parser.add_argument("novel_directory",
                        help="Path to novel directory (must contain glossary.txt, optionally a 'raw' subdir).")
    parser.add_argument("--no-backup", action="store_true",
                        help="Disable backup of the original glossary.txt.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show changes without modifying glossary.txt.")
    parser.add_argument("--min-occurrences", type=int, default=1,
                        help="Minimum times a term must appear in 'raw' texts to be kept.")
    
    args = parser.parse_args()
    
    novel_dir = Path(args.novel_directory).resolve()
    if not novel_dir.is_dir():
        print(f"Error: Novel directory not found: {novel_dir}")
        sys.exit(1)

    # Load raw novel text if available for occurrence counting
    novel_text = ""
    raw_dir_path = novel_dir / "raw" # Convention: novel_directory/raw/*.txt

    if raw_dir_path.exists() and raw_dir_path.is_dir():
        raw_files = sorted(list(raw_dir_path.glob("*.txt"))) # Sorted for consistent order
        if raw_files:
            print(f"Found {len(raw_files)} .txt files in {raw_dir_path} for term counting.")
            for file_path in raw_files:
                try:
                    with file_path.open('r', encoding='utf-8') as f:
                        novel_text += f.read() + "\n" # Add newline separator
                except Exception as e:
                    print(f"Error reading raw text file {file_path}: {e}")
            if novel_text:
                print(f"Loaded {len(novel_text)} characters from raw text files.")
            else:
                print("No content loaded from raw files (all empty or read errors).")
        else:
            print(f"No .txt files found in {raw_dir_path}.")
    else:
        print(f"Raw text directory not found ({raw_dir_path}), proceeding without term occurrence data.")
    
    glossary_path = novel_dir / "glossary.txt"
    if not glossary_path.exists():
        print(f"No glossary.txt found in {novel_dir}")
        sys.exit(1)
    
    print(f"Processing glossary: {glossary_path}")
    
    # Load current glossary
    original_glossary = load_glossary(glossary_path)
    if not original_glossary:
        print("No terms found in glossary")
        sys.exit(1)
    
    print(f"Original glossary contains {len(original_glossary)} terms")

    # Count term occurrences from raw text, if available
    term_occurrences = {}
    if novel_text:
        glossary_keys = list(original_glossary.keys())
        if glossary_keys:
            term_occurrences = count_term_occurrences(novel_text, glossary_keys)
            # Display a small sample of counts for user feedback
            sample_counts = {k: term_occurrences[k] for k in list(term_occurrences)[:5] if k in term_occurrences}
            if sample_counts:
                print(f"Sample term counts: {sample_counts}")
            else:
                print("No occurrences found for sample terms or glossary is small/empty.")
        else:
            print("Glossary is empty, skipping occurrence counting.")
    else:
        # term_occurrences remains empty if no novel_text
        print("No novel text loaded, term occurrence features will be skipped (min_occurrences=0 effectively).")

    # Clean glossary
    excluded_terms_set = get_excluded_terms()
    cleaned_glossary, removed_terms_log = clean_glossary(
        original_glossary,
        excluded_terms_set,
        term_occurrences, # Pass the loaded term_occurrences
        args.min_occurrences
    )
    
    print(f"\nCleaned glossary would contain {len(cleaned_glossary)} terms.")
    if removed_terms_log:
        print(f"Terms that would be removed ({len(removed_terms_log)}):")
        for entry in removed_terms_log:
            print(f"  - {entry}")
    else:
        print("No terms identified for removal based on current criteria.")
    
    if args.dry_run:
        print("\nDry run complete. No files were modified.")
        sys.exit(0) # Exit after dry run

    # Proceed with saving if there are changes
    if len(original_glossary) == len(cleaned_glossary):
        print("\nNo changes to save. Glossary is already effectively clean or criteria didn't remove anything.")
        sys.exit(0)

    if removed_terms_log: # Only ask for confirmation if terms were actually flagged for removal
        try:
            response = input(f"\nSave changes and remove {len(removed_terms_log)} terms from glossary? (y/N): ").strip().lower()
            if response.startswith('y'):
                save_glossary(cleaned_glossary, glossary_path, backup=not args.no_backup)
                print("Glossary cleanup complete!")
            else:
                print("Cleanup cancelled by user.")
        except EOFError: # Handle non-interactive environments
            print("\nNon-interactive mode detected or no input provided. No changes saved.")
            print("Run interactively or pipe 'y' to save, e.g., 'echo \"y\" | python script.py ...'")
    else: # Should ideally be caught by the len check above, but as a fallback.
        print("\nNo terms were identified for removal. Nothing to save.")


if __name__ == "__main__":
    main()