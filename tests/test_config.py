from __future__ import annotations

import os
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from packages.config.env import load_dotenv


class ConfigTests(unittest.TestCase):
    def test_load_dotenv_supports_quotes_export_and_preserves_explicit_values(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("# comment\nexport SIDURI_TEST_QUOTED='hello world'\nSIDURI_TEST_PLAIN=value\n", encoding="utf-8")
            old_plain = os.environ.get("SIDURI_TEST_PLAIN")
            old_quoted = os.environ.get("SIDURI_TEST_QUOTED")
            os.environ["SIDURI_TEST_PLAIN"] = "explicit"
            try:
                load_dotenv(path)
                self.assertEqual(os.environ["SIDURI_TEST_QUOTED"], "hello world")
                self.assertEqual(os.environ["SIDURI_TEST_PLAIN"], "explicit")
            finally:
                if old_quoted is None:
                    os.environ.pop("SIDURI_TEST_QUOTED", None)
                else:
                    os.environ["SIDURI_TEST_QUOTED"] = old_quoted
                if old_plain is None:
                    os.environ.pop("SIDURI_TEST_PLAIN", None)
                else:
                    os.environ["SIDURI_TEST_PLAIN"] = old_plain
