import unittest
from cleanup_glossary import count_term_occurrences, clean_glossary, get_excluded_terms

class TestCountTermOccurrences(unittest.TestCase):
    def test_simple_count(self):
        text = "hello world hello"
        terms = ["hello", "world"]
        expected = {"hello": 2, "world": 1}
        self.assertEqual(count_term_occurrences(text, terms), expected)

    def test_case_insensitive_count(self):
        text = "Hello world hELLo"
        terms = ["hello", "world"]
        expected = {"hello": 2, "world": 1}
        self.assertEqual(count_term_occurrences(text, terms), expected)

    def test_term_with_original_tag(self):
        text = "The Item is special. Another item."
        terms = ["Item [Original]", "item"]
        # Base term for "Item [Original]" is "Item", lowercased to "item".
        # Novel text "The Item is special. Another item." lowercased is "the item is special. another item.".
        # "item" appears 2 times.
        expected = {"Item [Original]": 2, "item": 2}
        self.assertEqual(count_term_occurrences(text, terms), expected)

    def test_term_with_original_tag_mixed_case(self):
        text = "The item is special. Another ITEM."
        terms = ["Item [Original]", "item"]
        expected = {"Item [Original]": 2, "item": 2}
        self.assertEqual(count_term_occurrences(text, terms), expected)

    def test_term_not_found(self):
        text = "hello world"
        terms = ["missing"]
        expected = {"missing": 0}
        self.assertEqual(count_term_occurrences(text, terms), expected)

    def test_empty_novel_text(self):
        text = ""
        terms = ["hello", "world"]
        # Function returns an empty dict if novel_text is empty
        expected = {}
        self.assertEqual(count_term_occurrences(text, terms), expected)

    def test_none_novel_text(self):
        text = None
        terms = ["hello", "world"]
        expected = {} # Function returns empty dict if text is None
        self.assertEqual(count_term_occurrences(text, terms), expected)

    def test_empty_glossary_list(self):
        text = "hello world"
        terms = []
        expected = {}
        self.assertEqual(count_term_occurrences(text, terms), expected)

    def test_mixed_conditions(self):
        text = "Apple pie is good. apple crumble is also good. Banana bread. No Orange."
        terms = ["Apple", "apple", "Banana [Fruit]", "Orange", "Missing"]
        # text = "Apple pie is good. apple crumble is also good. Banana bread. No Orange."
        # novel_text_lower = "apple pie is good. apple crumble is also good. banana bread. no orange."
        # "Apple" (base "apple") -> count of "apple" in novel_text_lower is 2.
        # "apple" (base "apple") -> count of "apple" in novel_text_lower is 2.
        # "Banana [Fruit]" (base "banana") -> count of "banana" is 1.
        # "Orange" (base "orange") -> count of "orange" is 1.
        # "Missing" (base "missing") -> count of "missing" is 0.
        expected = {"Apple": 2, "apple": 2, "Banana [Fruit]": 1, "Orange": 1, "Missing": 0}
        self.assertEqual(count_term_occurrences(text, terms), expected)


class TestCleanGlossary(unittest.TestCase):
    def setUp(self):
        self.glossary = {
            "Apple": "A red fruit",
            "Banana": "A yellow fruit",
            "CommonWord": "A common term",  # 'commonword' will be in excluded_terms
            "Special Item [Original]": "A very special item, usually rare",
            "LowCountItem": "A rare item indeed",
            "Generic Item": "This is a type of item",
            "Another Common [Original]": "A common thing, but tagged",
            "Generic Desc [Original]": "a kind of special thing"
        }
        # Using a simplified set for predictable testing
        self.excluded_terms = {'commonword', 'another common'}
        # For more comprehensive testing, one might use:
        # self.full_excluded_terms = get_excluded_terms()

    def test_remove_below_min_occurrences(self):
        term_occurrences = {
            "Apple": 5, "Banana": 1, "LowCountItem": 0,
            "Special Item [Original]": 1, "CommonWord": 10, "Generic Item": 5
        }
        # min_occurrences = 2, Banana (1) and LowCountItem (0) should be removed
        cleaned, removed = clean_glossary(self.glossary, self.excluded_terms, term_occurrences, min_occurrences=2)

        self.assertIn("Apple", cleaned)
        self.assertNotIn("Banana", cleaned)
        self.assertNotIn("LowCountItem", cleaned)

        removed_log_str = "".join(removed)
        self.assertIn("'Banana' (Reason: low occurrences (found 1, min is 2))", removed_log_str)
        self.assertIn("'LowCountItem' (Reason: low occurrences (found 0, min is 2))", removed_log_str)

    def test_keep_above_min_occurrences(self):
        # Provide counts for all terms in self.glossary to avoid unintentional low occurrence removal
        term_occurrences = {
            "Apple": 2,
            "Banana": 3,
            "CommonWord": 10, # Will be removed as common term
            "Special Item [Original]": 5, # Kept (override if any issue)
            "LowCountItem": 3, # Kept (above min_occ)
            "Generic Item": 10, # Will be removed as generic desc
            "Another Common [Original]": 5, # Kept (override common)
            "Generic Desc [Original]": 5 # Kept (override generic)
        }
        min_occ = 2
        cleaned, removed = clean_glossary(self.glossary, self.excluded_terms, term_occurrences, min_occurrences=min_occ)

        self.assertIn("Apple", cleaned) # Count 2, min 2
        self.assertIn("Banana", cleaned) # Count 3, min 2
        self.assertNotIn("CommonWord", cleaned) # Removed as common
        self.assertIn("Special Item [Original]", cleaned) # Count 5, min 2
        self.assertIn("LowCountItem", cleaned) # Count 3, min 2
        self.assertNotIn("Generic Item", cleaned) # Removed as generic
        self.assertIn("Another Common [Original]", cleaned) # Override common
        self.assertIn("Generic Desc [Original]", cleaned) # Override generic

        # Expected removed: CommonWord, Generic Item
        self.assertEqual(len(removed), 2)
        removed_log_str = "".join(removed)
        self.assertIn("'CommonWord' (Reason: common term)", removed_log_str)
        self.assertIn("'Generic Item' (Reason: generic description)", removed_log_str)


    def test_min_occurrences_with_common_term_exclusion(self):
        # CommonWord count is high (10), but 'commonword' is in self.excluded_terms
        # Ensure other items are not accidentally removed by low occurrence
        term_occurrences = {
            "CommonWord": 10, "Apple": 5, "Banana": 5,
            "Special Item [Original]": 5, "LowCountItem": 5, "Generic Item": 5,
            "Another Common [Original]": 5, "Generic Desc [Original]": 5
        }
        cleaned, removed = clean_glossary(self.glossary, self.excluded_terms, term_occurrences, min_occurrences=2)

        self.assertNotIn("CommonWord", cleaned)
        self.assertIn("Apple", cleaned)
        self.assertIn("'CommonWord' (Reason: common term)", "".join(removed))

    def test_min_occurrences_with_generic_description(self):
        # Generic Item count is high (5), but has a generic description
        term_occurrences = {
            "Generic Item": 5, "Apple": 5, "Banana": 5,
            "CommonWord": 10, "Special Item [Original]": 5, "LowCountItem": 5,
            "Another Common [Original]": 5, "Generic Desc [Original]": 5
        }
        cleaned, removed = clean_glossary(self.glossary, self.excluded_terms, term_occurrences, min_occurrences=2)

        self.assertNotIn("Generic Item", cleaned)
        self.assertIn("Apple", cleaned)
        self.assertIn("'Generic Item' (Reason: generic description)", "".join(removed))

    def test_original_tag_override_low_occurrence(self):
        # Special Item [Original] count is 1, min_occurrences is 2, but should be kept due to tag
        term_occurrences = {
            "Special Item [Original]": 1, "Apple": 5, "Banana": 5,
            "CommonWord": 10, "LowCountItem": 5, "Generic Item": 5,
            "Another Common [Original]": 5, "Generic Desc [Original]": 5
        }
        cleaned, removed = clean_glossary(self.glossary, self.excluded_terms, term_occurrences, min_occurrences=2)

        self.assertIn("Special Item [Original]", cleaned)
        self.assertIn("Apple", cleaned)
        # Check that no removal log for "Special Item [Original]" exists for low occurrence
        self.assertFalse(any("'Special Item [Original]' (Reason: low occurrences" in r for r in removed))

    def test_original_tag_override_common_term(self):
        # Another Common [Original] is 'another common' (in excluded_terms), count high, should be kept by tag
        term_occurrences = {
            "Another Common [Original]": 10, "Apple": 5, "Banana": 5,
            "CommonWord": 10, "Special Item [Original]": 5, "LowCountItem": 5, "Generic Item": 5,
            "Generic Desc [Original]": 5
        }
        cleaned, removed = clean_glossary(self.glossary, self.excluded_terms, term_occurrences, min_occurrences=2)

        self.assertIn("Another Common [Original]", cleaned)
        self.assertIn("Apple", cleaned)
        self.assertFalse(any("'Another Common [Original]' (Reason: common term" in r for r in removed))

    def test_original_tag_override_generic_description(self):
        # Generic Desc [Original] has generic desc, count high, should be kept by tag
        term_occurrences = {
            "Generic Desc [Original]": 10, "Apple": 5, "Banana": 5,
            "CommonWord": 10, "Special Item [Original]": 5, "LowCountItem": 5, "Generic Item": 5,
            "Another Common [Original]": 5
        }
        # Modify glossary for this test case temporarily or add to setUp if preferred
        current_glossary = self.glossary.copy()
        current_glossary["Generic Desc [Original]"] = "a kind of special thing"

        cleaned, removed = clean_glossary(current_glossary, self.excluded_terms, term_occurrences, min_occurrences=2)

        self.assertIn("Generic Desc [Original]", cleaned)
        self.assertIn("Apple", cleaned)
        self.assertFalse(any("'Generic Desc [Original]' (Reason: generic description" in r for r in removed))

    def test_removed_log_accuracy_low_occurrence(self):
        term_occurrences = {
            "Banana": 0, "Apple": 5, "CommonWord": 10,
            "Special Item [Original]": 5, "LowCountItem": 5, "Generic Item": 5,
            "Another Common [Original]": 5, "Generic Desc [Original]": 5
        } # min_occurrences default is 1
        cleaned, removed = clean_glossary(self.glossary, self.excluded_terms, term_occurrences, min_occurrences=1)
        self.assertNotIn("Banana", cleaned)
        self.assertTrue(any("'Banana' (Reason: low occurrences (found 0, min is 1))" in r for r in removed))

    def test_interaction_common_override_low_occurrence(self):
        # Term is common, low occurrence, but has [Original] tag
        # Example: "Common Low [Original]"
        # excluded_terms = {'common low'}
        # occurrences = {"Common Low [Original]": 0}
        # min_occurrences = 1
        # Expected: Kept.
        local_glossary = {"Common Low [Original]": "A common but low item"}
        local_excluded = {'common low'}
        term_occurrences = {"Common Low [Original]": 0}

        cleaned, removed = clean_glossary(local_glossary, local_excluded, term_occurrences, min_occurrences=1)
        self.assertIn("Common Low [Original]", cleaned)
        self.assertEqual(len(removed), 0)

    def test_interaction_generic_override_low_occurrence(self):
        # Term has generic description, low occurrence, but has [Original] tag
        # Example: "Generic Low [Original]"
        # occurrences = {"Generic Low [Original]": 0}
        # min_occurrences = 1
        # Expected: Kept.
        local_glossary = {"Generic Low [Original]": "a type of low item"}
        term_occurrences = {"Generic Low [Original]": 0}

        cleaned, removed = clean_glossary(local_glossary, self.excluded_terms, term_occurrences, min_occurrences=1)
        self.assertIn("Generic Low [Original]", cleaned)
        self.assertEqual(len(removed), 0)

if __name__ == '__main__':
    unittest.main()
