import os
import httpx
import json

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

class OllamaClient:
    def __init__(self):
        self.base_url = OLLAMA_HOST

    async def get_embedding(self, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": "nomic-embed-text:latest",
                        "prompt": text
                    },
                    timeout=30.0
                )
                res.raise_for_status()
                data = res.json()
                return data["embedding"]
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return []

    async def generate_merge(self, original: str, new: str, summary: str) -> str:
        prompt = f"""
You are an expert technical writer acting as a 'Semantic Merger'.
Your goal is to merge a CREATE/UPDATE/DELETE change into an existing document section.

CONTEXT:
Existing Section:
{original}

New Information (to be merged):
{new}

Change Request Summary:
{summary}

INSTRUCTIONS:
1. Rewrite the 'Existing Section' to incorporate the 'New Information'.
2. Maintain the original tone and formatting (Markdown).
3. If the new information contradicts the old, the NEW information wins.
4. Output ONLY the merged content. Do not include prologue or explanations.
"""
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": "llama3.2",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=60.0
                )
                res.raise_for_status()
                data = res.json()
                return data["response"]
        except Exception as e:
            return f"Error merging content: {e}"

ollama = OllamaClient()
