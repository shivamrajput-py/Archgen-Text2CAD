# Hybrid RAG System (Pinecone + Cohere Reranking)
import os
import json
import logging
from typing import Dict, List, Optional
import numpy as np

try:
    import cohere
except ImportError:
    cohere = None

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

from pinecone_text.sparse import BM25Encoder

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class HybridRAG:
    def __init__(self, json_file_path: str, embedding_model: str = "all-MiniLM-L6-v2"):
        self.json_file_path = json_file_path
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Initialize BM25
        self.bm25 = None
        if BM25Encoder:
            try:
                self.bm25 = BM25Encoder().default()
                bm25_path = os.path.join(os.path.dirname(json_file_path), "bm25_params.json")
                if os.path.exists(bm25_path):
                    self.bm25.load(bm25_path)
                    logger.info("Loaded BM25 params for sparse retrieval.")
                else:
                    logger.warning(f"BM25 params not found at {bm25_path}. Sparse vectors may not match corpus.")
            except Exception as e:
                logger.warning(f"BM25 initialization failed: {e}")
        
        # Load local examples as fallback
        self.local_examples = self._load_examples()
        self.embeddings = None
        self._create_local_embeddings()
        
        self.pc = None
        self.index = None
        self.co = None
        
        pc_api_key = os.environ.get("PINECONE_API_KEY")
        if pc_api_key and Pinecone:
            try:
                self.pc = Pinecone(api_key=pc_api_key)
                self.index_name = os.environ.get("PINECONE_INDEX", "archgencad")
                if self.index_name in self.pc.list_indexes().names():
                    self.index = self.pc.Index(self.index_name)
                    logger.info(f"Connected to Pinecone index: {self.index_name}")
                else:
                    logger.warning(f"Pinecone index {self.index_name} not found.")
            except Exception as e:
                logger.warning(f"Pinecone initialization failed: {e}")
                
        co_api_key = os.environ.get("COHERE_API_KEY")
        if co_api_key and cohere:
            try:
                # Use v2 client
                self.co = cohere.ClientV2(co_api_key)
                logger.info("Connected to Cohere V2")
            except Exception as e:
                logger.warning(f"Cohere initialization failed: {e}")

    def _load_examples(self) -> List[Dict]:
        try:
            if not os.path.exists(self.json_file_path):
                return []
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading examples: {e}")
            return []
            
    def _create_local_embeddings(self):
        if not self.local_examples:
            return
        texts = [ex.get('prompt', '') for ex in self.local_examples]
        try:
            self.embeddings = self.embedding_model.encode(texts)
        except Exception:
            pass

    def retrieve_similar_examples(
        self,
        query: str,
        k: int = 3,
        category: str = None,
        difficulty: str = None,
        components: List[str] = None,
        script_only: bool = False,
        use_mmr: bool = True,
        mmr_lambda: float = 0.7
    ) -> List[Dict]:
        # Step 1: Retrieval
        results = []
        if self.index:
            try:
                # Build dense query vector
                query_vector = self.embedding_model.encode(query).tolist()
                
                # Build sparse vector for hybrid search
                sparse_vector = None
                if self.bm25:
                    sparse_vector = self.bm25.encode_queries(query)
                
                # Fetch top 10 for reranking.
                query_kwargs = {
                    "vector": query_vector,
                    "top_k": 10,
                    "include_metadata": True
                }
                if sparse_vector:
                    query_kwargs["sparse_vector"] = sparse_vector
                    
                res = self.index.query(**query_kwargs)
                for match in res['matches']:
                    meta = match['metadata']
                    
                    def safe_parse(val, default="[]"):
                        if isinstance(val, list): return val
                        try:
                            return json.loads(val)
                        except:
                            return json.loads(default)

                    # Fetch script and chain_of_thoughts from local storage to bypass Pinecone metadata limits
                    script_content = ""
                    cot_content = ""
                    
                    if "original_index" in meta:
                        idx = int(meta["original_index"])
                        if idx < len(self.local_examples):
                            original_ex = self.local_examples[idx]
                            script_content = original_ex.get("script", "")
                            cot_content = original_ex.get("chain_of_thoughts", "")
                    elif "filepath" in meta:
                        try:
                            with open(meta["filepath"], 'r', encoding='utf-8') as f:
                                local_data = json.load(f)
                                script_content = local_data.get("script", "")
                                cot_content = local_data.get("chain_of_thoughts", "")
                        except Exception as e:
                            logger.error(f"Failed to read local example file {meta['filepath']}: {e}")
                            
                    # Fallback to metadata if it was somehow stored there (legacy)
                    if not script_content:
                        script_content = meta.get("script", "")
                    if not cot_content:
                        cot_content = meta.get("chain_of_thoughts", "")
                            
                    results.append({
                        "prompt": meta.get("prompt", ""),
                        "script": script_content,
                        "chain_of_thoughts": cot_content,
                        "category": meta.get("category", ""),
                        "difficulty": meta.get("difficulty", "intermediate"),
                        "components": safe_parse(meta.get("components")),
                        "tags": safe_parse(meta.get("tags")),
                        "freecad_apis": safe_parse(meta.get("freecad_apis")),
                        "engineering_concepts": safe_parse(meta.get("engineering_concepts")),
                        "validation_criteria": meta.get("validation_criteria", ""),
                        "similarity_score": match.get("score", 0.0)
                    })
            except Exception as e:
                logger.warning(f"Pinecone search failed, using local fallback: {e}")
                results = self._local_search(query, k=10)
        else:
            results = self._local_search(query, k=10)
            
        # Soft category filter — only apply if it doesn't wipe all results.
        # When prompt extraction fails (dead model), category defaults to 'architectural'
        # which would eliminate turbine/mechanical examples. We prefer relevance over strict category.
        if category:
            category_filtered = [r for r in results if not r.get("category") or r.get("category", "").lower() == category.lower()]
            if category_filtered:
                results = category_filtered
                logger.info(f"Category filter '{category}' kept {len(results)} results")
            else:
                logger.warning(f"Category filter '{category}' would remove ALL results — skipping filter, returning by vector similarity only")
            
        if not results:
            return []
            
        # Step 2: Cohere Reranking
        if self.co and len(results) > 1:
            try:
                docs = []
                for r in results:
                    # Construct rich text for reranker
                    doc_text = f"Prompt: {r.get('prompt', '')}\n"
                    if r.get('chain_of_thoughts'):
                        doc_text += f"Reasoning: {r['chain_of_thoughts']}\n"
                    if r.get('tags'):
                        doc_text += f"Tags: {', '.join(r['tags'])}\n"
                    if r.get('components'):
                        doc_text += f"Components: {', '.join(r['components'])}\n"
                    if r.get('freecad_apis'):
                        doc_text += f"APIs: {', '.join(r['freecad_apis'])}\n"
                    
                    script = r.get('script', '')
                    # Progressive script truncation strategy context for reranker
                    script_start = '\n'.join(script.splitlines()[:200])
                    doc_text += f"Script:\n{script_start}"
                    
                    docs.append(doc_text)
                
                rerank_res = self.co.rerank(
                    model="rerank-v3.5",
                    query=query,
                    documents=docs,
                    top_n=k
                )
                
                final_results = []
                for reranked in rerank_res.results:
                    idx = reranked.index
                    res = results[idx]
                    res["boosted_score"] = reranked.relevance_score
                    res["similarity_score"] = reranked.relevance_score
                    if script_only:
                        final_results.append({
                            "prompt": res["prompt"],
                            "script": res["script"],
                            "difficulty": res["difficulty"],
                            "similarity_score": res["similarity_score"],
                            "boosted_score": res["boosted_score"]
                        })
                    else:
                        final_results.append(res)
                return final_results
            except Exception as e:
                logger.warning(f"Cohere reranking failed: {e}")
                
        # Fallback ranking if no Cohere
        results = results[:k]
        for r in results:
            r["boosted_score"] = r.get("similarity_score", 0.5)
        return results

    def _local_search(self, query: str, k: int) -> List[Dict]:
        if not self.local_examples or self.embeddings is None:
            return []
        from sklearn.metrics.pairwise import cosine_similarity
        query_vec = self.embedding_model.encode([query])
        sims = cosine_similarity(query_vec, self.embeddings)[0]
        top_indices = np.argsort(sims)[-k:][::-1]
        results = []
        for idx in top_indices:
            ex = self.local_examples[idx].copy()
            ex["similarity_score"] = float(sims[idx])
            ex["boosted_score"] = float(sims[idx])
            results.append(ex)
        return results

    def ingest_gold_generation(self, prompt: str, script: str, category: str = "Unknown", components: List[str] = None, difficulty: str = "intermediate") -> bool:
        # Replaced by orchestrator saving to pending_review directly.
        pass
        
    def approve_entry(self, index: int) -> bool:
        return False
        
    def get_pending_entries(self) -> List[Dict]:
        return []

    @property
    def examples(self):
        return self.local_examples
