import sys
import os
from pathlib import Path

# Allow `python backend/main.py` from the project root without PYTHONPATH tricks
sys.path.insert(0, str(Path(__file__).parent.parent))

# Must be set before huggingface_hub is imported anywhere below, so that the rare
# online-fallback model download fails fast instead of hanging through long retries.
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "10")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

try:
    import torch
    torch.set_num_threads(2)
    torch.set_grad_enabled(False)
except ImportError:
    pass

from backend.api import create_app

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    app = create_app()
    print("GraphRAG server starting on http://localhost:1904")
    app.run(host="0.0.0.0", port=1904, threaded=True, debug=False)
