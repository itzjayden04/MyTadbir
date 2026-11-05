import os
import sys
import tempfile
from pathlib import Path

os.environ["MYTADBIR_DB"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
os.environ["MYTADBIR_OFFLINE"] = "1"  # tests use the offline keyword classifier; no API spend
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import init_db  # noqa: E402

init_db()
