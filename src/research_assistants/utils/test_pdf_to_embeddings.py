import os
from pathlib import Path

import chromadb
import pytest

from pdf_to_embeddings import (
    add_to_collection,
    chunk_text,
    get_or_create_collection,
    init_chromadb_client,
    init_embedding_function,
    init_text_splitter,
)

COLLECTION_NAME = "pytest_temp_collection"
DB_DIR = "temp_chroma_db"


def test_chromadb_persistent_client_rag_pipeline(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    client = init_chromadb_client(path=f"./{DB_DIR}")
    embedding_fn = init_embedding_function()
    collection = get_or_create_collection(client, COLLECTION_NAME, embedding_fn)

    documents = [
        "search_document: This is a test document about robots and AI.",
        "search_document: Another test document about embeddings and intelligence.",
    ]
    metadatas = [{"Title": "Doc1"}, {"Title": "Doc2"}]
    ids = ["id0", "id1"]

    add_to_collection(collection, documents, metadatas, ids)

    assert collection.count() == len(documents)

    results = collection.query(query_texts=["search_query: test document"], n_results=2)
    returned_docs = results.get("documents", [[]])[0]

    assert len(returned_docs) == 2
    assert all(isinstance(doc, str) and doc.strip() for doc in returned_docs)

    reopened_client = chromadb.PersistentClient(path=f"./{DB_DIR}")
    reopened_collection = reopened_client.get_collection(name=COLLECTION_NAME)
    assert reopened_collection.count() == len(documents)


def test_chunk_text_returns_multiple_prefixed_chunks():
    long_text = "This is a test document about robots and AI. " * 200
    splitter = init_text_splitter()

    chunks = chunk_text(long_text, splitter)

    assert len(chunks) > 1
    assert all(chunk.startswith("search_document: ") for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)
