import os
import json
import logging
from typing import List, Dict

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    from pinecone_text.sparse import BM25Encoder
except ImportError:
    BM25Encoder = None

logger = logging.getLogger(__name__)

def setup_logger():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def migrate_dataset(json_file_path: str, index_name: str):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(json_file_path), ".env"))
    
    if not Pinecone:
        logger.error("pinecone-client not installed. Run: pip install pinecone-client")
        return
    if not SentenceTransformer:
        logger.error("sentence-transformers not installed.")
        return
    if not BM25Encoder:
        logger.error("pinecone-text not installed. Run: pip install pinecone-text")
        return

    pc_api_key = os.environ.get("PINECONE_API_KEY")
    if not pc_api_key:
        logger.error("PINECONE_API_KEY environment variable not set.")
        return

    pc = Pinecone(api_key=pc_api_key)
    
    # Check if index exists
    if index_name not in pc.list_indexes().names():
        logger.error(f"Index '{index_name}' not found. Please create it in the Pinecone console with:")
        logger.error("- Dimensions: 384")
        logger.error("- Metric: dotproduct (REQUIRED for hybrid search)")
        return

    index = pc.Index(index_name)
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    bm25 = BM25Encoder().default()

    if not os.path.exists(json_file_path):
        logger.error(f"Dataset file not found: {json_file_path}")
        return

    with open(json_file_path, 'r', encoding='utf-8') as f:
        examples = json.load(f)

    logger.info(f"Loaded {len(examples)} examples from {json_file_path}")

    # For BM25, we could fit it on our own corpus to get better sparse vectors
    # but default English BM25 works decently out of the box.
    # To fit it on our own dataset:
    corpus = []
    for ex in examples:
        text = f"{ex.get('prompt', '')} {ex.get('category', '')} {' '.join(ex.get('components', []))}"
        corpus.append(text)
    
    logger.info("Fitting BM25 on the dataset corpus...")
    bm25.fit(corpus)
    # Save the fitted values so we can load it later in RAG
    bm25_path = os.path.join(os.path.dirname(json_file_path), "bm25_params.json")
    bm25.dump(bm25_path)
    logger.info(f"Saved BM25 parameters to {bm25_path}")

    batch_size = 50
    vectors_to_upsert = []

    for i, ex in enumerate(examples):
        doc_id = f"gold_ex_{i}"
        
        meta = {
            "prompt": ex.get("prompt", ""),
            "category": ex.get("category", "Unknown"),
            "difficulty": ex.get("difficulty", "intermediate"),
            "components": json.dumps(ex.get("components", [])),
            "tags": json.dumps(ex.get("tags", [])),
            "freecad_apis": json.dumps(ex.get("freecad_apis", [])),
            "engineering_concepts": json.dumps(ex.get("engineering_concepts", [])),
            "validation_criteria": json.dumps(ex.get("validation_criteria", {})),
            "auto_ingested": ex.get("auto_ingested", False),
            "original_index": i
        }

        # Dense vector
        text_for_embedding = corpus[i]
        dense_vector = embedder.encode(text_for_embedding).tolist()
        
        # Sparse vector
        sparse_vector = bm25.encode_documents(text_for_embedding)

        vectors_to_upsert.append({
            "id": doc_id,
            "values": dense_vector,
            "sparse_values": sparse_vector,
            "metadata": meta
        })

        if len(vectors_to_upsert) >= batch_size:
            index.upsert(vectors=vectors_to_upsert)
            logger.info(f"Upserted batch of {len(vectors_to_upsert)} records...")
            vectors_to_upsert = []

    if vectors_to_upsert:
        index.upsert(vectors=vectors_to_upsert)
        logger.info(f"Upserted final batch of {len(vectors_to_upsert)} records.")

    logger.info("Migration to Pinecone complete!")

if __name__ == "__main__":
    setup_logger()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(base_dir, "dataset.json")
    index = os.environ.get("PINECONE_INDEX", "archgencad")
    migrate_dataset(dataset_path, index)
