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

    async def generate_summary(self, content: str) -> str:
        """Generate a concise executive summary of a feature section.

        Goal:
            Produce a 100–200 word plain-prose summary of the provided feature
            content, suitable for storage as a ``#### Summary`` subsection at
            the top of the feature.

        Args:
            content: The full markdown content of the feature section
                     (including all sub-sections such as Constraints, API, etc.).

        Returns:
            A 100–200 word plain-prose summary string, or an error message
            prefixed with ``"Error:"`` if the call fails.
        """
        prompt = f"""You are an expert technical writer.
Read the following feature specification and write a concise executive summary.

RULES:
1. The summary MUST be between 100 and 200 words.
2. Write in plain prose — no bullet points, no headers, no markdown.
3. Cover: what the feature does, its main constraints, and its key technical approach.
4. Output ONLY the summary text. Do not include any preamble or explanation.

FEATURE CONTENT:
{content}
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
                return data["response"].strip()
        except httpx.TimeoutException as e:
            error_msg = f"Timeout after 60s: {type(e).__name__}"
            print(f"[Ollama] {error_msg}")
            return f"Error: {error_msg}"
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:100]}"
            print(f"[Ollama] {error_msg}")
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e) or 'Unknown error'}"
            print(f"[Ollama] Unexpected error: {error_msg}")
            import traceback
            traceback.print_exc()
            return f"Error: {error_msg}"

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
        except httpx.TimeoutException as e:
            error_msg = f"Timeout after 60s: {type(e).__name__}"
            print(f"[Ollama] {error_msg}")
            return f"Error merging content: {error_msg}"
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:100]}"
            print(f"[Ollama] {error_msg}")
            return f"Error merging content: {error_msg}"
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e) or 'Unknown error'}"
            print(f"[Ollama] Unexpected error: {error_msg}")
            import traceback
            traceback.print_exc()
            return f"Error merging content: {error_msg}"

ollama = OllamaClient()
