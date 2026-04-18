from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from langchain_core.documents import Document


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
FALLBACK_MESSAGE = "I could not find this in official documents."


def load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from a local .env file into os.environ."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def detect_file_type(file_path: Path) -> Optional[str]:
    suffix = file_path.suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return suffix

    try:
        with file_path.open("rb") as file_obj:
            header = file_obj.read(8)
    except OSError:
        return None

    if header.startswith(b"%PDF"):
        return ".pdf"
    if header.startswith(b"PK"):
        try:
            with zipfile.ZipFile(file_path) as archive:
                names = archive.namelist()
        except zipfile.BadZipFile:
            return None
        if any(name.startswith("word/") for name in names):
            return ".docx"
        return None

    try:
        text_sample = file_path.read_text(encoding="utf-8")[:256]
    except (OSError, UnicodeDecodeError):
        return None
    if text_sample.strip():
        return ".txt"
    return None


def infer_category(file_path: Path) -> str:
    """Infer a simple category from the filename."""
    lowered = file_path.stem.lower()
    category_keywords = {
        "policy": "policy",
        "eligibility": "eligibility",
        "placement": "placement",
        "internship": "internship",
        "recruitment": "recruitment",
        "job": "job",
        "company": "company",
        "training": "training",
    }
    for keyword, category in category_keywords.items():
        if keyword in lowered:
            return category
    return "general"


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def list_supported_files(data_dir: Path) -> List[Path]:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")
    return sorted(
        file_path
        for file_path in data_dir.rglob("*")
        if file_path.is_file() and detect_file_type(file_path) in SUPPORTED_EXTENSIONS
    )


def deduplicate_documents(documents: Sequence[Document]) -> List[Document]:
    unique_docs: List[Document] = []
    seen: set[Tuple[str, str]] = set()
    for document in documents:
        content = document.page_content.strip()
        source = str(document.metadata.get("source", ""))
        key = (source, content)
        if content and key not in seen:
            seen.add(key)
            unique_docs.append(document)
    return unique_docs


def format_context(documents: Sequence[Document]) -> str:
    parts: List[str] = []
    for index, document in enumerate(documents, start=1):
        source = document.metadata.get("source", "unknown")
        category = document.metadata.get("category", "general")
        page = document.metadata.get("page")
        page_label = f", page {page + 1}" if isinstance(page, int) else ""
        parts.append(
            f"[Chunk {index} | source={source} | category={category}{page_label}]\n"
            f"{document.page_content.strip()}"
        )
    return "\n\n".join(parts)


def extract_sources(documents: Sequence[Document]) -> List[str]:
    ordered_sources: List[str] = []
    seen: set[str] = set()
    for document in documents:
        source = str(document.metadata.get("source", "unknown"))
        if source not in seen:
            seen.add(source)
            ordered_sources.append(source)
    return ordered_sources


def clean_answer(answer: Optional[str]) -> str:
    if not answer:
        return FALLBACK_MESSAGE
    cleaned = answer.strip()
    if not cleaned:
        return FALLBACK_MESSAGE
    return cleaned


def post_process_answer(raw_answer: str) -> str:
    """Remove duplicate consecutive lines and enforce a maximum length on LLM responses."""
    lines = raw_answer.strip().splitlines()

    # Remove duplicate consecutive lines
    cleaned: List[str] = []
    for line in lines:
        stripped = line.strip()
        if cleaned and stripped == cleaned[-1].strip():
            continue
        cleaned.append(line)

    result = "\n".join(cleaned).strip()

    # Truncate excessively long responses at a natural boundary
    max_length = 3000
    if len(result) > max_length:
        truncated = result[:max_length]
        last_newline = truncated.rfind("\n")
        if last_newline > max_length // 2:
            result = truncated[:last_newline].strip()
        else:
            result = truncated.strip()

    return result


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
