import json
import numpy as np
from pathlib import Path
from server.document_manager import manager
from server.ollama_client import ollama

class VectorStore:
    def __init__(self):
        pass

    def _load_vectors(self, name: str):
        md_path, vec_path = manager._get_paths(name)
        if not vec_path.exists():
            return []
        try:
            return json.loads(vec_path.read_text(encoding="utf-8"))
        except:
            return []

    def _save_vectors(self, name: str, vectors: list):
        _, vec_path = manager._get_paths(name)
        vec_path.write_text(json.dumps(vectors), encoding="utf-8")

    def cosine_similarity(self, v1, v2):
        dotted = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0
        return dotted / (norm1 * norm2)

    async def sync_document(self, name: str):
        """
        Naive sync: Re-chunk the document and re-calculate embeddings.
        In a real app, we'd only calc changed chunks.
        """
        content = manager.get_document(name)
        if not content:
            return
        
        # Simple splitting by headers (H1, H2, H3)
        # Using a regex to find headers
        import re
        chunks = []
        # Split by lines starting with #
        # This is a VERY naive splitter
        lines = content.split('\n')
        current_chunk = []
        current_header = "Introduction"
        
        for line in lines:
            if line.startswith('#'):
                if current_chunk:
                    chunks.append({"header": current_header, "text": "\n".join(current_chunk)})
                # Strip hashes to match document_manager.get_structure format
                current_header = line.lstrip('#').strip()
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        if current_chunk:
             chunks.append({"header": current_header, "text": "\n".join(current_chunk)})
             
        # Now get embeddings for each chunk
        vectors = []
        for chunk in chunks:
            # We embed the text content
            vec = await ollama.get_embedding(chunk["text"])
            vectors.append({
                "header": chunk["header"],
                "text": chunk["text"],
                "vector": vec
            })
            
        self._save_vectors(name, vectors)
        return vectors

    async def find_best_match(self, name: str, query_text: str):
        # Ensure vectors are up to date (Naive: sync on every search for MVP)
        vectors = await self.sync_document(name)
        
        if not vectors:
            return None

        query_vec = await ollama.get_embedding(query_text)
        if not query_vec:
            return None
        
        best_score = -1
        best_match = None
        
        for item in vectors:
            score = self.cosine_similarity(query_vec, item["vector"])
            if score > best_score:
                best_score = score
                best_match = item
                
        return best_match

store = VectorStore()
