"""
RCB Data Pipeline
=================
Six-step ingestion pipeline: Download → Extract → Structure → Index → Validate → Consume

Session 27 — Assignment 14C
R.P.A.PORT LTD - February 2026
"""

from .pipeline import ingest_source, SOURCE_TYPE_TO_COLLECTION
from .extractor import extract_text
from .structurer import structure_with_llm
from .indexer import index_document

__all__ = [
    "ingest_source",
    "extract_text",
    "structure_with_llm",
    "index_document",
    "SOURCE_TYPE_TO_COLLECTION",
]
