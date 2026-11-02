"""Repository/PDF extraction and source-aware text chunking."""

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pymupdf
from django.conf import settings


SUPPORTED_EXTENSIONS = {'.py', '.java', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.sql'}
IGNORED_DIRS = {
    '.git', '.hg', '.svn', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build',
    '__pycache__', '.mypy_cache', '.pytest_cache', '.tox', 'coverage', 'target',
}


@dataclass
class SourceDocument:
    content: str
    metadata: dict


@dataclass
class ContentChunk:
    content: str
    metadata: dict


def extract_repository_documents(repository_root):
    root = Path(repository_root).resolve()
    documents = []
    visited_files = 0

    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirnames[:] = [
            name for name in dirnames
            if name.lower() not in IGNORED_DIRS and not (current_path / name).is_symlink()
        ]
        for filename in filenames:
            path = current_path / filename
            visited_files += 1
            if visited_files > settings.MAX_REPOSITORY_FILE_COUNT:
                raise ValueError('Repository contains more files than the configured limit.')
            lowered_name = filename.lower()
            if (
                path.is_symlink()
                or path.suffix.lower() not in SUPPORTED_EXTENSIONS
                or '.min.' in lowered_name
                or '.generated.' in lowered_name
                or lowered_name.endswith(('_generated.py', '.d.ts'))
            ):
                continue
            try:
                resolved = path.resolve(strict=True)
                relative = resolved.relative_to(root)
                size = resolved.stat().st_size
            except (OSError, ValueError):
                continue
            if size > settings.MAX_SOURCE_FILE_SIZE_BYTES or not resolved.is_file():
                continue
            try:
                content = resolved.read_bytes().decode('utf-8-sig')
            except (OSError, UnicodeDecodeError):
                continue
            if '\x00' in content:
                continue
            documents.append(SourceDocument(content, {
                'source_type': 'CODE',
                'file_path': PurePosixPath(*relative.parts).as_posix(),
                'file_extension': resolved.suffix.lower(),
            }))
    return documents


def extract_pdf_documents(submission):
    if not submission.project_pdf:
        return []
    try:
        with submission.project_pdf.open('rb') as pdf_file:
            data = pdf_file.read()
        pdf = pymupdf.open(stream=data, filetype='pdf')
        documents = []
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text('text').strip()
            if text:
                documents.append(SourceDocument(text, {
                    'source_type': 'PDF',
                    'file_path': submission.project_pdf.name,
                    'page': page_number,
                }))
        pdf.close()
    except Exception as exc:
        raise ValueError('The submitted PDF could not be read.') from exc
    if not documents:
        raise ValueError('The submitted PDF contains no extractable text.')
    return documents


def split_documents(documents, chunk_size=1000, chunk_overlap=150):
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError('Invalid text chunk size or overlap.')
    chunks = []
    for document in documents:
        text = document.content
        start = 0
        while start < len(text):
            hard_end = min(start + chunk_size, len(text))
            end = hard_end
            if hard_end < len(text):
                lower_bound = start + max(1, chunk_size // 2)
                for separator in ('\n\n', '\n', ' '):
                    boundary = text.rfind(separator, lower_bound, hard_end)
                    if boundary > start:
                        end = boundary + len(separator)
                        break
            content = text[start:end].strip()
            if content:
                metadata = dict(document.metadata)
                if metadata['source_type'] == 'CODE':
                    metadata['start_line'] = text.count('\n', 0, start) + 1
                    metadata['end_line'] = text.count('\n', 0, end) + 1
                chunks.append(ContentChunk(content, metadata))
            if end >= len(text):
                break
            start = max(start + 1, end - chunk_overlap)
    return chunks
