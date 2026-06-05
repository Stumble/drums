import sys
import warnings
from pathlib import Path

# Make `app` importable from every test.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Silence third-party stdlib-deprecation noise (audioread on py3.12).
warnings.filterwarnings("ignore", category=DeprecationWarning)
