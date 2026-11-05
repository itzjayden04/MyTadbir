import os
import sys
import tempfile
from pathlib import Path

os.environ["MYTADBIR_DB"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
os.environ.pop("ANTHROPIC_API_KEY", None)  # tests use the offline keyword classifier
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import init_db  # noqa: E402

init_db()
