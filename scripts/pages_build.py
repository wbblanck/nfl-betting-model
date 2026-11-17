"""Build the GitHub Pages copy of the dashboard with live venue prices (display only): python scripts/pages_build.py site/"""
import sys
from pathlib import Path

from nflbet import dashboard

if __name__ == "__main__":
    dashboard.build_site(Path(sys.argv[1] if len(sys.argv) > 1 else "site"), fetch="--no-fetch" not in sys.argv)
