import os
import json
import argparse
import shutil
import logging
from typing import List, Dict

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

logger = logging.getLogger(__name__)

def setup_logger():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def get_pending_files(pending_dir: str) -> List[str]:
    if not os.path.exists(pending_dir):
        return []
    return [os.path.join(pending_dir, f) for f in os.listdir(pending_dir) if f.endswith('.json')]

def ingest_to_pinecone(filepath: str, index, embedder, bm25=None):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Add a unique ID, e.g. based on filename
        doc_id = os.path.basename(filepath).replace('.json', '')
        
        # Prepare metadata for Pinecone without large text fields
        meta = {
            "prompt": data.get("prompt", ""),
            "category": data.get("category", "Unknown"),
            "difficulty": data.get("difficulty", "intermediate"),
            "components": json.dumps(data.get("components", [])),
            "tags": json.dumps(data.get("tags", [])),
            "freecad_apis": json.dumps(data.get("freecad_apis", [])),
            "engineering_concepts": json.dumps(data.get("engineering_concepts", [])),
            "validation_criteria": json.dumps(data.get("validation_criteria", {})),
            "auto_ingested": True,
            "filepath": os.path.join("core", "ingested", f"{doc_id}.json")
        }
        
        # Combine text for dense embedding
        text_for_embedding = f"Prompt: {meta['prompt']} Category: {meta['category']} Components: {' '.join(data.get('components', []))}"
        vector = embedder.encode(text_for_embedding).tolist()
        
        # Upsert with sparse vector if available
        upsert_data = {"id": doc_id, "values": vector, "metadata": meta}
        if bm25:
            upsert_data["sparse_values"] = bm25.encode_documents(text_for_embedding)
            
        index.upsert(vectors=[upsert_data])
        return True
    except Exception as e:
        logger.error(f"Failed to ingest {filepath}: {e}")
        return False

def main():
    setup_logger()
    parser = argparse.ArgumentParser(description="Manage ArchgenCAD RAG dataset")
    parser.add_argument("--review", action="store_true", help="Review and ingest pending generations")
    args = parser.parse_args()
    
    if not args.review:
        parser.print_help()
        return

    pc_api_key = os.environ.get("PINECONE_API_KEY")
    if not pc_api_key or not Pinecone:
        logger.error("PINECONE_API_KEY not set or pinecone client not installed.")
        return
        
    pc = Pinecone(api_key=pc_api_key)
    index_name = os.environ.get("PINECONE_INDEX", "archgencad")
    if index_name not in pc.list_indexes().names():
        logger.error(f"Pinecone index '{index_name}' not found.")
        return
        
    index = pc.Index(index_name)
    
    try:
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer("all-MiniLM-L6-v2")
    except ImportError:
        logger.error("sentence_transformers not installed.")
        return
        
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    bm25 = None
    try:
        from pinecone_text.sparse import BM25Encoder
        bm25_path = os.path.join(base_dir, "bm25_params.json")
        if os.path.exists(bm25_path):
            bm25 = BM25Encoder().default()
            bm25.load(bm25_path)
            logger.info("Loaded BM25 params for hybrid search.")
    except Exception as e:
        logger.warning(f"Could not load BM25 params: {e}")
    pending_dir = os.path.join(base_dir, "pending_review")
    ingested_dir = os.path.join(base_dir, "ingested")
    os.makedirs(ingested_dir, exist_ok=True)
    
    pending_files = get_pending_files(pending_dir)
    if not pending_files:
        logger.info("No pending generations to review.")
        return
        
    logger.info(f"Found {len(pending_files)} pending files.")
    
    for filepath in pending_files:
        filename = os.path.basename(filepath)
        print(f"\n--- Reviewing: {filename} ---")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"Prompt: {data.get('prompt')}")
            print(f"Score: {data.get('score')}")
            
            choice = input("Ingest this generation? (y/n/s=skip): ").strip().lower()
            if choice == 'y':
                if ingest_to_pinecone(filepath, index, embedder, bm25):
                    shutil.move(filepath, os.path.join(ingested_dir, filename))
                    logger.info(f"Ingested and moved {filename}")
            elif choice == 'n':
                os.remove(filepath)
                logger.info(f"Deleted {filename}")
            else:
                logger.info(f"Skipped {filename}")
                
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}")

if __name__ == "__main__":
    main()
