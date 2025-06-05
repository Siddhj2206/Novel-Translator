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
    """Load glossary from file into a dictionary."""
    glossary = {}
    
    if not glossary_path.exists():
        print(f"Error: Glossary file not found: {glossary_path}")
        return glossary
    
    try:
        with open(glossary_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    term, definition = line.split(':', 1)
                    term = term.strip()
                    definition = definition.strip()
                    if term and definition:
                        glossary[term] = definition
    except Exception as e:
        print(f"Error reading glossary: {e}")
    
    return glossary


def save_glossary(glossary: dict, glossary_path: Path, backup: bool = True):
    """Save cleaned glossary back to file."""
    if backup and glossary_path.exists():
        backup_path = glossary_path.with_suffix('.txt.backup')
        glossary_path.rename(backup_path)
        print(f"Created backup: {backup_path}")
    
    try:
        with open(glossary_path, 'w', encoding='utf-8') as f:
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


def clean_glossary(glossary: dict, excluded_terms: set, min_occurrences: int = 1) -> dict:
    """Clean glossary by removing common terms and low-value entries."""
    cleaned = {}
    removed_terms = []
    
    for term, definition in glossary.items():
        # Extract base term (without brackets)
        base_term = term.split('[')[0].strip().lower() if '[' in term else term.lower()
        
        # Check if term should be excluded
        should_exclude = False
        
        # Check against excluded terms list
        if base_term in excluded_terms:
            should_exclude = True
            removed_terms.append(f"{term} (common term)")
        
        # Check for generic descriptions that suggest non-essential terms
        definition_lower = definition.lower()
        generic_indicators = [
            'a type of', 'a kind of', 'general term', 'common', 'ordinary',
            'simple', 'basic', 'regular', 'normal', 'standard', 'typical',
            'generic', 'minor character', 'side character', 'background',
            'mentioned briefly', 'appears once'
        ]
        
        if any(indicator in definition_lower for indicator in generic_indicators):
            should_exclude = True
            removed_terms.append(f"{term} (generic description)")
        
        # Keep terms with original language names (they're usually important)
        if '[' in term and ']' in term:
            should_exclude = False
        
        # Keep if not excluded
        if not should_exclude:
            cleaned[term] = definition
    
    return cleaned, removed_terms


def main():
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
    excluded_terms = get_excluded_terms()
    cleaned_glossary, removed_terms = clean_glossary(original_glossary, excluded_terms, args.min_occurrences)
    
    print(f"Cleaned glossary contains {len(cleaned_glossary)} terms")
    print(f"Removed {len(removed_terms)} terms:")
    
    # Show what would be removed
    for removed in removed_terms:
        print(f"  - {removed}")
    
    if args.dry_run:
        print("\nDry run complete. No files were modified.")
    else:
        if len(removed_terms) > 0:
            response = input(f"\nRemove {len(removed_terms)} terms from glossary? (y/N): ")
            if response.lower().startswith('y'):
                save_glossary(cleaned_glossary, glossary_path, backup=not args.no_backup)
                print("Glossary cleanup complete!")
            else:
                print("Cleanup cancelled.")
        else:
            print("No terms to remove. Glossary is already clean!")


if __name__ == "__main__":
    main()