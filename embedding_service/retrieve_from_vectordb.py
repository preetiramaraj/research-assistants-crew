from pathlib import Path
from datetime import datetime
import json,os
import logging
import re

from pdf_to_embeddings import (
    init_chromadb_client,
    get_or_create_collection,
    init_embedding_function
)
from run_paths import latest_run_dir

def setup_logger(log_filename: str = None):
    if log_filename is None:
        log_folder = Path(__file__).resolve().parents[0] / "logs"
        os.makedirs(log_folder, exist_ok=True)
        log_filename = Path(log_folder).resolve() / "retrieve_from_vectordb.log"
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

# Retrieve keywords from the search queries file
def retrieve_keywords() -> list[str]:
    queries_path = latest_run_dir() / "search_queries.md"
    with open(queries_path, 'r', encoding='utf-8') as f:
        keywords = [line.strip() for line in f if line.strip()]

    return keywords

# Retrieving chunks from the collection using the queries with the keywords
def retrieve_chunks(collection):
    keywords = retrieve_keywords()
    background_questions = [
        "search_query: What existing approaches address {kw}?",
        "search_query: What are the key limitations or gaps in current research on {kw}?",
        "search_query: What methods are commonly used to evaluate {kw}?",
    ]
   
    all_results = []
    for kw in keywords:
        for q_template in background_questions:
            question = q_template.format(kw=kw)
            logger.info(f"Querying collection for: {question}")
            result_dict = query_collection(collection, question)
            result_dict['query'] = question  # Add the query to the result dictionary
            all_results.append(result_dict)
    return all_results

# Retrieving only the top chunk for each query for this current version.
# Note: This can be modified to retrieve more chunks if needed in the future.
def query_collection(collection, query: str, n_results: int = 1):
    results = collection.query(
        query_texts=[query], 
        n_results=n_results
    )
    return results

def select_collection(client):
     # Provide a list of collections to the user, let them choose one, then pass it here
    # OR fall back to the latest collection if the selection is invalid
    collections = client.list_collections()
    collection_names = []
    if isinstance(collections, list):
        for c in collections:
            if isinstance(c, dict) and 'name' in c:
                collection_names.append(c['name'])
            else:
                s = str(c)
                # Try to parse patterns like "Collection(name=collection_2026-06-14)"
                m = re.search(r"name=([^\)\s]+)", s)
                if m:
                    name = m.group(1).strip().strip('\"\'')
                    collection_names.append(name)
                else:
                    collection_names.append(s)
    else:
        s = str(collections)
        m = re.search(r"name=([^\)\s]+)", s)
        if m:
            collection_names = [m.group(1).strip().strip('\"\'')]
        else:
            collection_names = [s]

    if not collection_names:
        logger.error("No collections found. Exiting.")
        raise SystemExit(1)

    print("Available collections:")
    for i, name in enumerate(collection_names, start=1):
        print(f"{i}. {name}")

    default_name = f"collection_{latest_run_dir().name}"
    has_default = default_name in collection_names
    prompt = "Select collection by number or name"
    if has_default:
        prompt += f" (press Enter to use latest — {default_name})"
    selection = input(prompt + ": ").strip()

    collection_name = None
    if selection == "":
        if has_default:
            collection_name = default_name
    elif selection.isdigit():
        idx = int(selection) - 1
        if 0 <= idx < len(collection_names):
            collection_name = collection_names[idx]
    else:
        if selection in collection_names:
            collection_name = selection

    if collection_name is None:
        logger.error("No valid collection selected (and no collection exists yet for the latest run). Exiting.")
        raise SystemExit(1)

    return collection_name

def write_chunks_to_file(all_results: list[dict], collection_name: str, logger):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bg_chunks_file_name = f"bg_chunks_{collection_name.split('_')[-1]}_{timestamp}.txt"
    background_results_path = latest_run_dir() / bg_chunks_file_name
    
    with open(background_results_path, 'w', encoding='utf-8') as f:
        logger.info(f"Writing results to {background_results_path}")
        documents_combined = []
        curr_dict = {}
        for result_dict in all_results:
            ids = result_dict.get("ids", [])
            docs = result_dict.get("documents", [])
            # Storing in dictionary to remove duplicates based on IDs
            if isinstance(docs[0], list):
                for i in range(len(docs[0])):
                    curr_dict[ids[0][i]] = docs[0][i]

        logger.info(f"Number of unique documents: {len(curr_dict)}")
        documents_combined = "\n\n".join(curr_dict.values())
        f.write(documents_combined)

if __name__ == "__main__":
    logger = setup_logger()
    client = init_chromadb_client()
    embedding_fn = init_embedding_function()

    collection_name = select_collection(client)
    collection = get_or_create_collection(client, collection_name, embedding_fn, logger)
    logger.info(f"Using collection: {collection_name}")
   
    all_results = retrieve_chunks(collection)
    write_chunks_to_file(all_results, collection_name, logger)
       
