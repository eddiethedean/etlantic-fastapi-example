from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    home = Path(__file__).resolve().parents[1] / "Home.py"
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "streamlit", "run", str(home), *sys.argv[1:]]
        )
    )


if __name__ == "__main__":
    main()
