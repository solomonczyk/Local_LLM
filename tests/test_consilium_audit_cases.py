import re
import unittest

from tools.consilium_audit import CASES


class TestConsiliumAuditCases(unittest.TestCase):
    def test_case_ids_unique(self) -> None:
        ids = [case.id for case in CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_case_kinds_valid(self) -> None:
        valid = {"single_tools", "consilium"}
        for case in CASES:
            self.assertIn(case.kind, valid)

    def test_has_russian_case(self) -> None:
        has_cyrillic = any(re.search(r"[А-Яа-я]", case.task or "") for case in CASES)
        self.assertTrue(has_cyrillic)


if __name__ == "__main__":
    unittest.main()
