import sys
import os
import traceback

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

print("Attempting to import HighlightingService...")
try:
    from core.highlighting_service import HighlightingService
    print("Import Successful!")
except Exception:
    print("Import Failed!")
    traceback.print_exc()
