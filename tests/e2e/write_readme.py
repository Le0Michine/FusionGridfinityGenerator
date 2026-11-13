"""
Writes README.md, the list of shape test cases, from the case files, see testCases.casesMarkdown.
"""

import os
import importlib.util

E2E_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(E2E_FOLDER))
README_PATH = os.path.join(E2E_FOLDER, "README.md")
CASES_FOLDER = os.path.join(E2E_FOLDER, "cases")


def load_test_cases():
    spec = importlib.util.spec_from_file_location("testCases", os.path.join(PROJECT_ROOT, "commands", "commandSnapshotTests", "testCases.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(load_test_cases().casesMarkdown(CASES_FOLDER))
    print(f"Wrote {README_PATH}")
