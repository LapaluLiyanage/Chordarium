"""Clone BTC-ISMIR19 (code + pretrained weights) into server/engine/weights/."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.engine.chords_btc import DEFAULT_WEIGHTS_DIR, REPO_DIRNAME, is_available  # noqa: E402

REPO_URL = "https://github.com/jayg996/BTC-ISMIR19.git"


def main() -> int:
    DEFAULT_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    repo = DEFAULT_WEIGHTS_DIR / REPO_DIRNAME
    if not repo.exists():
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(repo)], check=True)
    if is_available(DEFAULT_WEIGHTS_DIR):
        print(f"BTC model ready: {repo}")
        return 0
    print(f"Cloned {repo} but the large-vocab weights file is missing.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
