#!/usr/bin/env python3
"""
Glossary Cleanup Utility

This script helps clean up bloated glossary.txt files by removing common terms
that don't need to be in the glossary for translation consistency.
"""

import argparse
import sys
from pathlib import Path


def load_glossary(glossary_path: Path) -> dict:
    """
    Load glossary from a text file into a dictionary.

    Args:
        glossary_path: Path to the glossary file.
                       Each line should be in "term: definition" format.

    Returns:
        A dictionary of glossary terms {term: definition}.
        Returns an empty dictionary if the file is not found or on error.
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
    Save the glossary dictionary back to a text file.

    Args:
        glossary: The dictionary of glossary terms to save.
        glossary_path: Path to the glossary file.
        backup: If True, creates a backup of the existing file before overwriting.
    """
    if backup and glossary_path.exists():
        # Create a backup file, e.g., glossary.txt -> glossary.txt.backup
        backup_path = glossary_path.with_suffix('.txt.backup')
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


def clean_glossary(glossary: dict, excluded_terms: set, min_occurrences: int = 1) -> tuple[dict, list[str]]:
    """
    Clean glossary by removing common terms and entries with generic descriptions.

    Args:
        glossary: The input glossary dictionary {term: definition}.
        excluded_terms: A set of common terms (lowercase) to exclude.
        min_occurrences: Minimum occurrences to keep a term.
                         NOTE: This parameter is parsed from CLI but NOT YET IMPLEMENTED
                         in the current filtering logic of this function.

    Returns:
        A tuple containing:
            - cleaned_glossary (dict): The glossary after removing unwanted terms.
            - removed_terms (list): A list of strings describing removed terms and reasons.
    """
    cleaned = {}
    removed_terms_log = [] # Log of terms removed and why

    # NOTE: The 'min_occurrences' parameter is parsed from CLI arguments but is not
    # currently used in this function's filtering logic. Future implementation could use it.
    
    for term, definition in glossary.items():
        # Extract base term (lowercase, without brackets) for exclusion checks
        # e.g., "Example Term [Original]" -> "example term"
        base_term = term.split('[')[0].strip().lower() if '[' in term else term.lower()
        
        should_exclude = False
        reason = ""
        
        # Rule 1: Check against the hardcoded list of common excluded terms
        if base_term in excluded_terms:
            should_exclude = True
            reason = "common term"
        
        # Rule 2: Check for generic descriptions that often indicate non-essential terms
        definition_lower = definition.lower()
        generic_indicators = [
            'a type of', 'a kind of', 'general term', 'common', 'ordinary',
            'simple', 'basic', 'regular', 'normal', 'standard', 'typical',
            'generic', 'minor character', 'side character', 'background',
            'mentioned briefly', 'appears once', 'example of'
        ]
        if not should_exclude and any(indicator in definition_lower for indicator in generic_indicators):
            should_exclude = True
            reason = "generic description"
        
        # Rule 3: Override - Always keep terms that have an original language name in brackets
        # This is a heuristic assuming such terms are specific and important proper nouns.
        if '[' in term and ']' in term:
            if should_exclude: # If it was marked for exclusion, log that it's being kept
                print(f"INFO: Keeping term '{term}' due to original name override, despite reason: {reason}")
            should_exclude = False
        
        if should_exclude:
            removed_terms_log.append(f"'{term}' (Reason: {reason})")
        else:
            cleaned[term] = definition

    return cleaned, removed_terms_log


def main():
    """
    Main entry point for the glossary cleanup script.
    Parses arguments, loads glossary, cleans it, and saves the result.
    """
    parser = argparse.ArgumentParser(description="Clean up bloated glossary files")
    parser.add_argument("novel_directory", help="Path to novel directory containing glossary.txt")
    parser.add_argument("--no-backup", action="store_true", help="Don't create backup file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without making changes")
    parser.add_argument("--min-occurrences", type=int, default=1, help="Minimum occurrences to keep term (not implemented yet)")
    
    args = parser.parse_args()
    
    novel_dir = Path(args.novel_directory).resolve()
    if not novel_dir.is_dir():
        print(f"Error: Novel directory not found: {novel_dir}")
        sys.exit(1)
    
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
    
    # Clean glossary
    excluded_terms_set = get_excluded_terms()
    cleaned_glossary, removed_terms_log = clean_glossary(
        original_glossary,
        excluded_terms_set,
        args.min_occurrences # Pass min_occurrences, though it's noted as unused in clean_glossary
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
    else:
        # Proceed with saving if there are changes and user confirms
        if len(original_glossary) == len(cleaned_glossary):
            print("\nNo changes to save. Glossary is already effectively clean or criteria didn't remove anything.")
            sys.exit(0)

        if removed_terms_log: # Only ask for confirmation if terms were actually flagged for removal
            response = input(f"\nSave changes and remove {len(removed_terms_log)} terms from glossary? (y/N): ").strip().lower()
            if response.startswith('y'):
                save_glossary(cleaned_glossary, glossary_path, backup=not args.no_backup)
                print("Glossary cleanup complete!")
            else:
                print("Cleanup cancelled by user.")
        else: # Should ideally be caught by the len check above, but as a fallback.
            print("\nNo terms were identified for removal. Nothing to save.")


if __name__ == "__main__":
    main()