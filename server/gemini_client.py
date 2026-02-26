"""
Gemini API integration for Specer.

Provides:
- GeminiSpecResponse / SpecBlock: the structured JSON schema the model must return.
- GeminiSessionRepository: manages Chat sessions (one per user conversation) with
  30-minute idle-time eviction and an exchange counter.
- GeminiClient: thin wrapper to create sessions, send messages, and list models.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

logger = logging.getLogger("specer.gemini")

# ---------------------------------------------------------------------------
# Default model — Gemini 3 Flash Preview (the latest Flash-class model)
# Fall back to 2.5 Flash if the preview is not accessible on your API tier.
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "gemini-3-flash-preview"
EXCHANGE_LIMIT = 15
SESSION_IDLE_MINUTES = 30


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class SpecBlock(BaseModel):
    """
    A single atomic spec update proposed by the LLM.

    Attributes:
        target_section: Path to the section to update, e.g. "Feature: Auth > Constraints".
                        Must match an existing section title or describe a new one.
        change_summary: One sentence describing what changes and why.
        content:        Markdown text to merge into the target section.
    """
    target_section: str
    change_summary: str
    content: str


class GeminiSpecResponse(BaseModel):
    """
    The full structured response returned by Gemini on every chat turn.

    Attributes:
        discussion:     Free-text conversational reply shown in the chat history.
        commit_summary: One-liner used as the version-control commit message when
                        the user validates the resulting merges.
        updates:        Zero or more spec update blocks. Empty list = discussion only,
                        no document changes proposed.
    """
    discussion: str
    commit_summary: str
    updates: list[SpecBlock]


# ---------------------------------------------------------------------------
# Session entry (internal)
# ---------------------------------------------------------------------------

class _SessionEntry:
    """Internal container for a live Gemini Chat session."""

    def __init__(self, chat, model: str, doc_name: str):
        self.chat = chat                    # google.genai Chat object
        self.model = model
        self.doc_name = doc_name            # document this session targets
        self.created_at: datetime = datetime.utcnow()
        self.last_used: datetime = datetime.utcnow()
        self.exchange_count: int = 0

    def touch(self):
        """Update last-used timestamp."""
        self.last_used = datetime.utcnow()

    @property
    def idle_seconds(self) -> float:
        return (datetime.utcnow() - self.last_used).total_seconds()

    def to_info(self) -> dict:
        return {
            "model": self.model,
            "doc_name": self.doc_name,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "exchange_count": self.exchange_count,
            "warn": self.exchange_count >= EXCHANGE_LIMIT,
        }


# ---------------------------------------------------------------------------
# Session repository
# ---------------------------------------------------------------------------

class GeminiSessionRepository:
    """
    In-memory store for active Gemini Chat sessions.

    Session lifecycle:
        create(session_id, ...)  → stores a new _SessionEntry
        send(session_id, msg)    → delegates to entry.chat.send_message()
        destroy(session_id)      → removes the entry
        cleanup_idle()           → removes entries idle > SESSION_IDLE_MINUTES
    """

    def __init__(self):
        self._sessions: dict[str, _SessionEntry] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def create(
        self,
        session_id: str,
        model: str,
        system_prompt: str,
        doc_name: str = "default",
    ) -> None:
        """
        Create a new Chat session.

        Steps:
          1. Instantiate the google-genai Client using GEMINI_API_KEY.
          2. Call client.chats.create() with system_instruction and response schema config.
          3. Store the session entry.

        Args:
            session_id:    Caller-supplied UUID string used as the lookup key.
            model:         Gemini model identifier, e.g. "gemini-3-flash-preview".
            system_prompt: Full system instruction built by GeminiClient.build_system_prompt().
            doc_name:      Name of the document this session is working on.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set in environment.")

        client = genai.Client(api_key=api_key)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=GeminiSpecResponse,
        )

        chat = client.chats.create(model=model, config=config)
        entry = _SessionEntry(chat=chat, model=model, doc_name=doc_name)

        async with self._lock:
            self._sessions[session_id] = entry

        logger.info(f"[Session] Created: {session_id} (model={model})")

    async def send(self, session_id: str, message: str) -> GeminiSpecResponse:
        """
        Send one user turn and parse the structured JSON reply.

        Args:
            session_id: Active session UUID.
            message:    Full user message text (may include prepended linked-section content).

        Returns:
            GeminiSpecResponse parsed from the model's JSON reply.

        Raises:
            KeyError:   If session_id does not exist (expired or never created).
            ValueError: If the model response cannot be parsed as GeminiSpecResponse.
        """
        async with self._lock:
            entry = self._sessions.get(session_id)

        if entry is None:
            raise KeyError(f"Session '{session_id}' not found or has expired.")

        logger.info(f"[Session] Sending message to {session_id} (turn {entry.exchange_count + 1})")

        # The SDK sends `message` plus the full internal history on every call.
        # We run in a thread executor to avoid blocking the event loop.
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: entry.chat.send_message(message),
        )

        # Bump counters regardless of parse outcome
        entry.exchange_count += 1
        entry.touch()

        # The SDK returns the raw text; parse it as our schema
        raw_text = response.text
        try:
            parsed = GeminiSpecResponse.model_validate_json(raw_text)
        except Exception as exc:
            logger.error(f"[Session] Failed to parse response for {session_id}: {exc}\nRaw: {raw_text[:500]}")
            raise ValueError(f"Model response could not be parsed: {exc}") from exc

        logger.info(
            f"[Session] {session_id}: turn {entry.exchange_count}, "
            f"{len(parsed.updates)} update(s)"
        )
        return parsed

    async def destroy(self, session_id: str) -> bool:
        """
        Remove a session.

        Returns:
            True if the session existed and was removed, False otherwise.
        """
        async with self._lock:
            existed = session_id in self._sessions
            self._sessions.pop(session_id, None)

        if existed:
            logger.info(f"[Session] Destroyed: {session_id}")
        return existed

    async def info(self, session_id: str) -> Optional[dict]:
        """
        Return metadata for a session, or None if it does not exist.
        """
        async with self._lock:
            entry = self._sessions.get(session_id)
        return entry.to_info() if entry else None

    async def cleanup_idle(self) -> int:
        """
        Remove sessions that have been idle for more than SESSION_IDLE_MINUTES.

        Returns:
            Number of sessions removed.
        """
        cutoff = timedelta(minutes=SESSION_IDLE_MINUTES)
        removed = 0
        async with self._lock:
            expired = [
                sid for sid, entry in self._sessions.items()
                if entry.idle_seconds > cutoff.total_seconds()
            ]
            for sid in expired:
                del self._sessions[sid]
                logger.info(f"[Session] Idle cleanup: removed {sid}")
                removed += 1
        return removed


# ---------------------------------------------------------------------------
# High-level client
# ---------------------------------------------------------------------------

class GeminiClient:
    """
    High-level facade used by the FastAPI endpoints.

    Wraps GeminiSessionRepository and provides helpers for:
    - Building the system prompt from DocumentManager data.
    - Listing available Gemini models.
    """

    def __init__(self, repo: GeminiSessionRepository):
        self.repo = repo

    def build_system_prompt(
        self,
        doc_tree: list[dict],
        scope_label: str,
        scope_content: str,
        global_context: Optional[str],
    ) -> str:
        """
        Construct the system prompt sent once at session creation.

        Args:
            doc_tree:       Flat list of {title, level} dicts from DocumentManager.
            scope_label:    Human-readable scope, e.g. "Document level" or "Feature: Auth".
            scope_content:  Full markdown text of the scope section (parent + children).
            global_context: Content of the top-level "Context, Aim & Integration" section,
                            or None if not present / not requested.

        Returns:
            Fully constructed system prompt string.
        """
        # Build indented tree
        tree_lines = []
        for item in doc_tree:
            indent = "  " * (item["level"] - 1)
            tree_lines.append(f"{indent}- {item['title']}")
        tree_str = "\n".join(tree_lines) or "(empty document)"

        prompt_parts = [
            "You are an expert Technical Architect and Documentation Lead.",
            "Your role is to help refine a software specification document.",
            "",
            "[DOCUMENT TREE]",
            tree_str,
            "",
            "[WORKING SCOPE]",
            f"The user is currently working in: {scope_label}",
            "",
            scope_content or "(no content yet)",
        ]

        if global_context:
            prompt_parts += [
                "",
                "[GLOBAL CONTEXT — Context, Aim & Integration]",
                global_context,
            ]

        prompt_parts += [
            "",
            "INSTRUCTIONS:",
            "- Reply ONLY in the provided JSON schema.",
            "- `discussion`: your conversational reply to the user.",
            "- `commit_summary`: one-line summary of all proposed changes (used as a version-control commit message).",
            "- `updates`: list of spec update blocks. Use an empty list if you are only discussing.",
            "- Each update block must specify `target_section` (matching an existing title or a new one),",
            "  `change_summary` (one sentence), and `content` (valid Markdown).",
        ]

        return "\n".join(prompt_parts)

    async def list_models(self) -> list[str]:
        """
        Return a curated list of Gemini models suitable for structured output.

        Preferred models are listed first. Falls back to a hard-coded list
        if the API call fails (e.g. key not configured yet).
        """
        preferred = [
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
        ]
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return preferred
            client = genai.Client(api_key=api_key)
            models = client.models.list()
            names = [m.name.replace("models/", "") for m in models
                     if "generateContent" in (m.supported_actions or [])]
            # Put preferred first, then append others
            ordered = [m for m in preferred if m in names]
            ordered += [m for m in names if m not in preferred]
            return ordered or preferred
        except Exception as exc:
            logger.warning(f"[GeminiClient] list_models failed: {exc}. Using defaults.")
            return preferred


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

session_repo = GeminiSessionRepository()
gemini_client = GeminiClient(repo=session_repo)
