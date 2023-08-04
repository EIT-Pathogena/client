import hashlib

from pathlib import Path


def hash_files(*paths: Path) -> str:
    hasher = hashlib.sha256()
    for path in paths:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(16_384), b""):
                hasher.update(block)
    return hasher.hexdigest()
