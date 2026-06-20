import os
from pathlib import Path
import logging
from typing import List, Tuple, Dict
from datetime import date
from xmlrpc import client

import pymupdf.layout
import pymupdf4llm
import re
from transformers import AutoTokenizer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pypdf import PdfReader

def setup_logger(log_filename: str = None):
    if log_filename is None:
        log_folder = Path(__file__).resolve().parents[0] / "logs"
        os.makedirs(log_folder, exist_ok=True)
        log_filename = Path(log_folder).resolve() / "pdf_to_embeddings.log"
        if not os.path.exists(log_filename):
            open(log_filename, 'w').close()

    # File handler with UTF-8 encoding
    handler = logging.FileHandler(log_filename, encoding='utf-8')
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(__name__)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    return logger


def init_text_splitter(model_name: str = "nomic-ai/nomic-embed-text-v1.5", chunk_size: int = 512, chunk_overlap: int = 100):
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

    def token_len(text: str) -> int:
        return len(tokenizer.encode(text))

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=token_len,
        separators=["\n\n", "\n", ".", " "]
    )

    return text_splitter


def init_embedding_function(model_name: str = "nomic-ai/nomic-embed-text-v1.5", device: str = "cpu"):
    return SentenceTransformerEmbeddingFunction(
        model_name=model_name,
        device=device,
        normalize_embeddings=False,
        trust_remote_code=True
    )


def init_chromadb_client(path: str = None):
    db_path = path or os.getenv("CHROMADB_PATH")
    if db_path is None:
        db_path = str(Path(__file__).resolve().parents[1] / "chroma_db")
    os.makedirs(db_path, exist_ok=True)
    client = chromadb.PersistentClient(path=db_path)
    return client


def get_or_create_collection(client, name: str, embedding_function, logger):
    try:
        collection = client.get_collection(name=name, embedding_function=embedding_function)
        logger.info(f"Collection '{name}' already exists. Using existing collection.")
        return collection
    except chromadb.errors.NotFoundError:
        collection = client.create_collection(name=name, embedding_function=embedding_function)
        logger.info(f"Collection '{name}' created.")
        return collection


def convert_pdf_to_markdown(pdf_path: str) -> str:
    return pymupdf4llm.to_markdown(pdf_path)


def extract_pdf_metadata(pdf_path: str) -> Dict[str, str]:
    reader = PdfReader(pdf_path)
    metadata = reader.metadata or {}
    title = metadata.get("/Title", "Unknown")
    authors = metadata.get("/Authors", "Unknown")
    if authors == "Unknown":
        authors = metadata.get("/Author", "Unknown")
    year = metadata.get("/Year", "Unknown")
    return {"Title": title, "Authors": authors, "Year": year}


def chunk_text(md_text: str, text_splitter) -> List[str]:
    chunks = text_splitter.create_documents([md_text])
    paper_chunks_list = [f"search_document: {paper_chunk.page_content}" for paper_chunk in chunks]
    return paper_chunks_list


def prepare_metadatas(metadata: Dict[str, str], n: int) -> List[Dict[str, str]]:
    return [metadata for _ in range(n)]


def generate_ids(start: int, n: int) -> Tuple[List[str], int]:
    ids = [f"id{i}" for i in range(start, start + n)]
    return ids, start + n


def add_to_collection(collection, documents: List[str], metadatas: List[Dict[str, str]], ids: List[str]):
    collection.add(documents=documents, metadatas=metadatas, ids=ids)


def strip_references(text):
    match = re.search(r'\n#{1,3}\s*[*_]*\s*(references|bibliography)\s*[*_]*\s*\n', text, re.IGNORECASE)
    if match:
        return text[:match.start()]
    return text

def write_pdf_to_markdown(pdf_folder: str, pdf_path: str, doc: str, logger) -> str:
    md_text = convert_pdf_to_markdown(pdf_path)
    md_text = strip_references(md_text)
    md_file = os.path.join(pdf_folder, "md_files", doc[:-4] + ".md")
    # with open(md_file, 'r', encoding='utf-8') as f:
    #     md_text = f.read()
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_text)
    logger.info(f"Converted {doc} to {md_file}")
    return md_text

def process_pdf_folder(pdf_folder: str, collection, text_splitter, logger, id_start: int = 0) -> int:
    id_count = id_start
    for doc in os.listdir(pdf_folder):
        logger.info(f"Processing {doc}")
        pdf_path = os.path.join(pdf_folder, doc)
        if doc.endswith(".pdf"):
            logger.info(f"Processing PDF: {pdf_path}")
            md_text = write_pdf_to_markdown(pdf_folder, pdf_path, doc, logger)
            metadata = extract_pdf_metadata(pdf_path)

            paper_chunks_list = chunk_text(md_text, text_splitter)
            len_chunks = len(paper_chunks_list)
            logger.info(f"Number of total chunks: {len_chunks}")

            paper_chunks_metadata = [metadata for _ in range(len_chunks)]
            paper_chunks_ids = [f"id{i}" for i in range(id_count, id_count + len_chunks)]
            id_count += len_chunks

            add_to_collection(collection, paper_chunks_list, paper_chunks_metadata, paper_chunks_ids)
            logger.info(f"Added {len(paper_chunks_list)} chunks from {doc} to collection")

    logger.info("Finished processing all PDFs and adding to collection")


def main():
    logger = setup_logger()

    text_splitter = init_text_splitter()
    embedding_fn = init_embedding_function()
    client = init_chromadb_client()

    today = str(date.today())
    collection_name = os.getenv("CHROMADB_COLLECTION", f"collection_{today}")
    collection = get_or_create_collection(client, collection_name, embedding_fn, logger)
    pdf_folder = os.getenv("PDF_FOLDER", os.path.join(os.getcwd(), "lit_review_pdfs"))
    process_pdf_folder(pdf_folder, collection, text_splitter, logger)

    # Example query
    results = collection.query(
        query_texts=["search_query: What is the effect of robot errors?"],
        n_results=3
    )

    print(results)


if __name__ == "__main__":
    main()
