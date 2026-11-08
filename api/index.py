import os
import sys

# Ensure backend directory is in Python module search path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.main import app

# Vercel Serverless Function entrypoint expects `app`
__all__ = ["app"]

