from __future__ import annotations

import json
import math
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

from automation.excel_safe_values import excel_safe_row, excel_safe_rows, excel_safe_value


class WeirdObject:
    def __str__(self) -> str:
        return "weird-object"


class ExcelSafeValueTests(unittest.TestCase):
    def test_empty_list_becomes_deterministic_json_text(self) -> None:
        self.assertEqual(excel_safe_value([]), "[]")

    def test_nested_collections_become_deterministic_json_text(self) -> None:
        value = {"b": {3, 1, 2}, "a": ["x", {"z": True}]}
        actual = excel_safe_value(value)
        self.assertIsInstance(actual, str)
        self.assertEqual(json.loads(actual), {"a": ["x", {"z": True}], "b": [1, 2, 3]})
        self.assertLess(actual.index('"a"'), actual.index('"b"'))

    def test_excel_native_scalars_pass_through(self) -> None:
        values = [
            None,
            "text",
            7,
            3.25,
            True,
            date(2026, 8, 21),
            datetime(2026, 8, 21, 8, 54),
            time(8, 54),
            timedelta(hours=1),
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertIs(excel_safe_value(value), value)

    def test_non_finite_floats_are_text_not_invalid_numeric_payloads(self) -> None:
        self.assertEqual(excel_safe_value(math.nan), "NaN")
        self.assertEqual(excel_safe_value(math.inf), "Infinity")
        self.assertEqual(excel_safe_value(-math.inf), "-Infinity")

    def test_path_bytes_and_custom_objects_are_safe_text(self) -> None:
        self.assertEqual(excel_safe_value(Path("a") / "b"), str(Path("a") / "b"))
        self.assertEqual(excel_safe_value(b"abc"), "abc")
        self.assertEqual(excel_safe_value(WeirdObject()), "weird-object")

    def test_cyclic_collection_does_not_recurse_forever(self) -> None:
        value: list[object] = []
        value.append(value)
        self.assertEqual(json.loads(excel_safe_value(value)), ["<CYCLE>"])

    def test_row_and_rows_normalize_every_cell(self) -> None:
        self.assertEqual(excel_safe_row([1, [], {"x": 2}]), [1, "[]", '{"x":2}'])
        self.assertEqual(
            excel_safe_rows([[1, []], [2, {"x": 3}]]),
            [[1, "[]"], [2, '{"x":3}']],
        )


if __name__ == "__main__":
    unittest.main()
