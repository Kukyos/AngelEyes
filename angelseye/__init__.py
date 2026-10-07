"""Angel's Eye — CCTV that understands what people are doing."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=ROOT / "config.yaml"):
    return yaml.safe_load(Path(path).read_text())


def env(key):
    """A setting from the environment, else from the project's .env (never committed)."""
    import os
    if os.environ.get(key):
        return os.environ[key]
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"')
    return ""
