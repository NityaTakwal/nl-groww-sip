import sys
from pathlib import Path

# Make the shared `common` package (project root) importable when run from 02_discovery_engine/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
