from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.config import settings_manager
from app.database import db, utc_now
from app.tools.registry import ToolDef, tool_registry

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}


def extract_text_from_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(str(path))
        parts = []
        for idx, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                parts.append(f"[Page {idx + 1}]\n{txt}")
        return "\n\n".join(parts)

    if ext == ".docx":
        with zipfile.ZipFile(path, "r") as zf:
            xml_content = zf.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        paragraphs = []
        for elem in tree.iter():
            if elem.tag.endswith("}p"):
                texts = [t.text for t in elem.iter() if t.tag.endswith("}t") and t.text]
                if texts:
                    paragraphs.append("".join(texts))
        return "\n".join(paragraphs)

    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    clean = re.sub(r"\r\n?", "\n", text).strip()
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    step = max(100, chunk_size - overlap)
    while start < len(clean):
        piece = clean[start : start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        if start + chunk_size >= len(clean):
            break
        start += step
    return chunks


def index_folders(folders: list[str] | None = None) -> dict[str, Any]:
    kb_cfg = settings_manager.get().get("knowledge_base", {})
    target_folders = folders if folders is not None else kb_cfg.get("folders", [])
    extensions = {e.lower() for e in kb_cfg.get("extensions", [".txt", ".md", ".pdf", ".docx"])}
    chunk_size = int(kb_cfg.get("chunk_size", 900))
    chunk_overlap = int(kb_cfg.get("chunk_overlap", 150))

    indexed_files = 0
    skipped_files = 0
    errors: list[str] = []
    seen_paths: set[str] = set()

    with db.connect() as conn:
        existing = {
            row["path"]: (row["mtime"], row["size"])
            for row in conn.execute("SELECT path, mtime, size FROM kb_files").fetchall()
        }

        for folder in target_folders:
            root = Path(folder).expanduser()
            if not root.exists():
                errors.append(f"Folder not found: {folder}")
                continue

            files = [root] if root.is_file() else list(root.rglob("*"))
            for fp in files:
                if not fp.is_file():
                    continue
                if any(part in SKIP_DIRS for part in fp.parts):
                    continue
                if fp.suffix.lower() not in extensions:
                    continue
                try:
                    stat = fp.stat()
                    if stat.st_size > 15 * 1024 * 1024:
                        skipped_files += 1
                        continue
                    key = str(fp.resolve())
                    seen_paths.add(key)
                    if key in existing and abs(existing[key][0] - stat.st_mtime) < 0.01 and existing[key][1] == stat.st_size:
                        skipped_files += 1
                        continue

                    text = extract_text_from_file(fp)
                    chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
                    conn.execute("DELETE FROM kb_chunks WHERE file_path = ?", (key,))
                    conn.execute(
                        """
                        INSERT INTO kb_files (path, mtime, size, chunk_count, indexed_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(path) DO UPDATE SET
                            mtime=excluded.mtime,
                            size=excluded.size,
                            chunk_count=excluded.chunk_count,
                            indexed_at=excluded.indexed_at
                        """,
                        (key, stat.st_mtime, stat.st_size, len(chunks), utc_now()),
                    )
                    for idx, ch in enumerate(chunks):
                        conn.execute(
                            "INSERT INTO kb_chunks (file_path, chunk_index, content) VALUES (?, ?, ?)",
                            (key, idx, ch),
                        )
                    indexed_files += 1
                except Exception as exc:
                    errors.append(f"{fp.name}: {exc}")

        # Prune files no longer in configured folders
        if folders is None:
            for old_path in list(existing.keys()):
                if old_path not in seen_paths:
                    conn.execute("DELETE FROM kb_files WHERE path = ?", (old_path,))

    return {
        "ok": True,
        "indexed_files": indexed_files,
        "unchanged_or_skipped": skipped_files,
        "total_files": len(list_indexed_files()),
        "errors": errors[:20],
    }


def list_indexed_files() -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT path, size, chunk_count, indexed_at FROM kb_files ORDER BY indexed_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def search_knowledge_base(query: str, limit: int = 6) -> list[dict[str, Any]]:
    tokens = [re.sub(r"[^\w]", "", tok) for tok in query.split()]
    tokens = [t for t in tokens if len(t) >= 2]
    if not tokens:
        return []

    fts_query = " OR ".join(f'"{t}"*' for t in tokens[:8])
    with db.connect() as conn:
        try:
            rows = conn.execute(
                """
                SELECT kb_chunks.file_path, kb_chunks.chunk_index, kb_chunks.content,
                       bm25(kb_chunks_fts) AS rank
                FROM kb_chunks_fts
                JOIN kb_chunks ON kb_chunks.id = kb_chunks_fts.rowid
                WHERE kb_chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        except Exception:
            like = f"%{query.strip()}%"
            rows = conn.execute(
                """
                SELECT file_path, chunk_index, content, 0.0 AS rank
                FROM kb_chunks
                WHERE content LIKE ?
                LIMIT ?
                """,
                (like, limit),
            ).fetchall()

    results = []
    for r in rows:
        fp = Path(r["file_path"])
        results.append(
            {
                "file_name": fp.name,
                "file_path": r["file_path"],
                "chunk_index": r["chunk_index"],
                "snippet": r["content"][:700],
            }
        )
    return results


async def _tool_search_kb(args: dict[str, Any]) -> dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = int(args.get("limit", 5))
    if not query:
        return {"ok": False, "error": "Query is required."}
    matches = search_knowledge_base(query, limit=limit)
    return {"ok": True, "query": query, "matches": matches, "count": len(matches)}


async def _tool_list_kb_files(args: dict[str, Any]) -> dict[str, Any]:
    files = list_indexed_files()
    folders = settings_manager.get().get("knowledge_base", {}).get("folders", [])
    return {"ok": True, "watched_folders": folders, "indexed_count": len(files), "files": files[:50]}


async def _tool_reindex_kb(args: dict[str, Any]) -> dict[str, Any]:
    return index_folders()


def register_knowledge_tools() -> None:
    tool_registry.register(
        ToolDef(
            name="search_personal_documents",
            description="Search the user's indexed personal files and documents (PDF, DOCX, Markdown, TXT, CSV, code) to answer questions with citations.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords or question"},
                    "limit": {"type": "integer", "description": "Max snippets to return (default 5)"},
                },
                "required": ["query"],
            },
            category="knowledge_base",
            tier=1,
            handler=_tool_search_kb,
        )
    )
    tool_registry.register(
        ToolDef(
            name="list_indexed_documents",
            description="List which folders and personal documents are currently indexed in the local knowledge base.",
            parameters={"type": "object", "properties": {}},
            category="knowledge_base",
            tier=1,
            handler=_tool_list_kb_files,
        )
    )
    tool_registry.register(
        ToolDef(
            name="reindex_personal_documents",
            description="Scan configured personal folders and update the document knowledge base index.",
            parameters={"type": "object", "properties": {}},
            category="knowledge_base",
            tier=2,
            handler=_tool_reindex_kb,
        )
    )
