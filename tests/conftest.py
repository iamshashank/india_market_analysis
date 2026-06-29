"""Make the backend package importable in tests (flat-module imports)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
os.environ.setdefault("INCLUDE_NEWS", "0")
# Force the local-JSON fallback so tests never touch a real MySQL.
os.environ.setdefault("MYSQL_URL", "")
