import sys
from pathlib import Path

# Force the repo root onto sys.path so tests can import the pipeline modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))
