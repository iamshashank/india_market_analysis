import os
import sys
from pathlib import Path

# Load .env from repo root (parent of backend/)
_repo_root = Path(__file__).parent.parent
_env_file = _repo_root / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(str(_env_file))

# macOS fork-safety guard. yfinance/requests resolve system proxy settings via
# the Objective-C SystemConfiguration framework; when that runs while worker
# threads are alive and a child process is forked, the ObjC runtime aborts the
# child ("+[NSCharacterSet initialize] ... when fork() was called. Crashing
# instead."), which SIGKILLs the gunicorn worker. These two settings disable
# that guard and skip the proxy lookup. No-ops on Linux/production.
if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
    os.environ.setdefault("no_proxy", "*")

from api.web import app  # noqa: E402
