"""LEVI RAG pipeline: chunk → ingest → retrieve → rerank → cite → generate.

Local-first, stdlib-only, offline. Retrieval comes from
:mod:`levi.memory.retrieval`; generation is a lazy call into the agent
runtime with an honest fallback when no generator is available.
"""

from .chunking import chunk_text, Chunk
from .ingest import ingest_file, ingest_directory, IngestReport
from .pipeline import ask, AskResult
from .eval import evaluate, build_questions, print_report

__all__ = [
    "chunk_text",
    "Chunk",
    "ingest_file",
    "ingest_directory",
    "IngestReport",
    "ask",
    "AskResult",
    "evaluate",
    "build_questions",
    "print_report",
]
