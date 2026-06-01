import pathlib
import sys

# Make `src/` importable so tests run without `pip install -e .`.
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
