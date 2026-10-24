"""Secure local document storage.

- Only PDF / JPG / PNG are accepted; the file's magic bytes must match its extension.
- Files are saved under a random name; the user's filename is kept only as metadata.
- Paths are resolved and checked to stay inside the storage directory (no path traversal).
"""
import hashlib
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from ..config import settings

ALLOWED = {
    ".pdf": ("application/pdf", [b"%PDF-"]),
    ".png": ("image/png", [b"\x89PNG\r\n\x1a\n"]),
    ".jpg": ("image/jpeg", [b"\xff\xd8\xff"]),
    ".jpeg": ("image/jpeg", [b"\xff\xd8\xff"]),
}


def storage_root() -> Path:
    root = Path(settings.storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_original_name(name: str | None) -> str:
    base = Path(name or "document").name  # strip any directory part
    cleaned = "".join(c for c in base if c.isalnum() or c in "._- ()")
    return (cleaned or "document")[:120]


async def save_upload(upload: UploadFile) -> dict:
    original = safe_original_name(upload.filename)
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF, JPG or PNG files are allowed.")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File is larger than {settings.max_upload_mb} MB.")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    content_type, signatures = ALLOWED[ext]
    if not any(data.startswith(sig) for sig in signatures):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File content does not match its type (expected a real PDF, JPG or PNG).")

    stored = f"{secrets.token_hex(16)}{'.jpg' if ext == '.jpeg' else ext}"
    path = resolve_stored(stored)
    path.write_bytes(data)
    return {
        "original_filename": original,
        "stored_filename": stored,
        "content_type": content_type,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def save_bytes(data: bytes, ext: str) -> str:
    stored = f"{secrets.token_hex(16)}{ext}"
    resolve_stored(stored).write_bytes(data)
    return stored


def resolve_stored(stored_filename: str) -> Path:
    root = storage_root()
    path = (root / stored_filename).resolve()
    if path.parent != root:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid document path.")
    return path
