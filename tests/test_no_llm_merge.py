"""
Test: No LLM Merge required for test_case.txt on a blank document.

Two layers:

1. Pure-simulation tests (no server, no I/O)
   Replicate the JS frontend merge-strategy decision logic in Python and run it
   against the realistic data returned by the backend process endpoint –– but
   without touching the filesystem.

2. Backend-API tests (require a running server or mocked I/O)
   Call /api/process directly through FastAPI, patching the data directory to a
   temporary location so they work outside Docker.

Goal (invariant):
  Processing tests/test_case.txt against a blank document must NEVER trigger LLM
  (i.e., strategy must always be "template", "subsection", or "direct").
  The critical regression case is Feature: World Engine whose 3 sub-section chunks
  (Context, Technical Requirements, Constraints) must all be handled without LLM
  even after the first chunk is committed and updates the in-memory structure.
"""

import re
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import server.document_manager as dm_module

# ---------------------------------------------------------------------------
# Helpers: mirror of the JS frontend decision logic (used by simulation tests)
# ---------------------------------------------------------------------------

FEATURE_TEMPLATE_SUBSECTIONS = [
    "Context, Aim & Integration",
    "Constraints",
    "User Stories",
    "Technical Requirements",
    "API",
    "Data Layer",
    "Validation",
    "Dependencies",
    "Other Notes",
]

MILESTONE_TEMPLATE_SUBSECTIONS = [
    "Content",
    "Validation",
]


def generate_feature_template(name: str) -> str:
    lines = [f"### Feature: {name}", ""]
    for sub in FEATURE_TEMPLATE_SUBSECTIONS:
        lines += [f"#### {sub}", ""]
    return "\n".join(lines)


def generate_milestone_template(name: str) -> str:
    lines = [f"### Milestone: {name}", ""]
    for sub in MILESTONE_TEMPLATE_SUBSECTIONS:
        lines += [f"#### {sub}", ""]
    return "\n".join(lines)


def parse_subsections(content: str) -> dict:
    """Parse ####-level subsections. Mirrors JS parseSubsections."""
    sections: dict = {}
    current: str | None = None
    buf: list = []

    for line in content.split("\n"):
        t = line.strip()
        if t.startswith("####"):
            if current is not None:
                sections[current] = "\n".join(buf)
            current = re.sub(r"^####\s+", "", t)
            buf = [line]
        elif current is not None:
            buf.append(line)

    if current is not None:
        sections[current] = "\n".join(buf)

    return sections


def is_template_with_structure(content: str) -> bool:
    """Mirrors JS isTemplateWithStructure."""
    if not content or not content.strip():
        return False
    headers = len(re.findall(r"^####\s+", content, re.MULTILINE))
    if headers < 2:
        return False
    for line in content.split("\n"):
        t = line.strip()
        if t and not t.startswith("#"):
            return False
    return True


def is_empty_or_template(content: str) -> bool:
    """Mirrors JS isEmptyOrTemplate."""
    if not content or not content.strip():
        return True
    for line in content.split("\n"):
        t = line.strip()
        if t and not t.startswith("#"):
            return False
    return True


def merge_into_template(template: str, new_content: str) -> str:
    """Mirrors JS mergeIntoTemplate."""
    tmpl_secs = parse_subsections(template)
    new_secs = parse_subsections(new_content)

    for name, body in new_secs.items():
        tmpl_secs[name] = body

    parts: list = []
    header_m = re.search(r"^###\s+.+$", template, re.MULTILINE)
    if header_m:
        parts.append(header_m.group(0))
        parts.append("")

    for sec_body in tmpl_secs.values():
        parts.append(sec_body)
        parts.append("")

    return "\n".join(parts).strip()


def get_real_original(title: str, fallback: str, struct: dict) -> str:
    """Mirrors JS getRealOriginal. struct maps title -> content."""
    real = struct.get(title, "")
    if real:
        return real

    lower = title.lower()
    if lower.startswith("feature:") or lower.startswith("feature "):
        name = re.sub(r"feature[:\s]*", "", title, flags=re.IGNORECASE).strip()
        return generate_feature_template(name)
    if lower.startswith("milestone:") or lower.startswith("milestone "):
        name = re.sub(r"milestone[:\s]*", "", title, flags=re.IGNORECASE).strip()
        return generate_milestone_template(name)

    return fallback or ""


def decide_merge_strategy(title: str, match: dict, struct: dict) -> str:
    """
    Replicates logic in JS selectPendingMerge (Cases 1, 1.5, 2, 3).

    Returns:
      "template"   – Case 1:   whole template is still empty
      "subsection" – Case 1.5: targeted sub-slot is empty in partially-filled template
      "direct"     – Case 2:   truly blank original
      "llm"        – Case 3:   needs LLM
    """
    real = get_real_original(title, match["original_text"], struct)

    # Case 1 – all-empty template
    if is_template_with_structure(real):
        if parse_subsections(match["new_text"]):
            return "template"

    # Case 1.5 – targeted sub-slots are empty
    new_secs = parse_subsections(match["new_text"])
    if new_secs and real:
        orig_secs = parse_subsections(real)

        def _slot_empty(sub: str) -> bool:
            orig = orig_secs.get(sub)
            if not orig:
                return True   # slot absent → treat as empty
            body = orig.split("\n")[1:]   # skip #### header line
            return all(not l.strip() for l in body)

        if all(_slot_empty(s) for s in new_secs):
            return "subsection"

    # Case 2 – completely empty
    if is_empty_or_template(real):
        return "direct"

    return "llm"


def simulate_accept(title: str, match: dict, strategy: str, struct: dict) -> None:
    """Update struct in-place after accepting a merge (mirrors JS commitMerge)."""
    real = get_real_original(title, match["original_text"], struct)

    if strategy in ("template", "subsection"):
        merged = merge_into_template(real, match["new_text"])
    elif strategy == "direct":
        merged = match["new_text"]
    else:
        merged = f"<LLM_PLACEHOLDER:{title}>"

    struct[title] = merged


# ---------------------------------------------------------------------------
# Backend helpers — redirect data dir so tests can run outside Docker
# ---------------------------------------------------------------------------

TEST_CASE_PATH = Path(__file__).parent / "test_case.txt"
DOC_NAME = "test_no_llm_merge"


@pytest.fixture()
def tmp_data(tmp_path):
    """Patch DocumentManager to write to tmp_path instead of data/."""
    history = tmp_path / "_history"
    history.mkdir()

    # Patch module-level constants the class uses
    with (
        patch.object(dm_module, "DATA_DIR", tmp_path),
        patch.object(dm_module, "HISTORY_DIR", history),
    ):
        # Re-create the singleton so it picks up new paths
        orig_mgr = dm_module.manager
        dm_module.manager = dm_module.DocumentManager()
        yield dm_module.manager
        dm_module.manager = orig_mgr


async def _run_process(tmp_mgr) -> list[dict]:
    """Call the process endpoint with the test case text, return matches."""
    from server.main import process_text, ProcessRequest

    tmp_mgr.init_document(DOC_NAME, reset=True)
    req = ProcessRequest(name=DOC_NAME, text=TEST_CASE_PATH.read_text())

    with patch(
        "server.vector_store.store.find_best_match", new_callable=AsyncMock
    ) as mock_sem:
        mock_sem.return_value = None   # no semantic fallback
        result = await process_text(req)

    assert result["status"] == "success", f"Process failed: {result}"
    return result["matches"]


# ---------------------------------------------------------------------------
# Backend unit tests
# ---------------------------------------------------------------------------


class TestBackendProcess:
    """Verify /api/process returns the right routing data for test_case.txt."""

    async def test_returns_matches(self, tmp_data):
        matches = await _run_process(tmp_data)
        assert len(matches) > 0
        for i, m in enumerate(matches):
            assert m["section"], f"Match {i} has no section"
            assert "original_text" in m
            assert "new_text" in m

    async def test_world_engine_three_chunks_all_new(self, tmp_data):
        """All 3 World Engine sub-section chunks must be routed as (New Section)."""
        matches = await _run_process(tmp_data)
        we = [m for m in matches if "World Engine" in m["section"]]

        assert len(we) == 3, (
            f"Expected 3 World Engine chunks, got {len(we)}: "
            + str([m["new_text"].splitlines()[0] for m in we])
        )
        for m in we:
            assert m["original_text"] == "(New Section)", (
                f"Expected '(New Section)', got '{m['original_text']}' "
                f"for chunk '{m['new_text'].splitlines()[0][:60]}'"
            )


# ---------------------------------------------------------------------------
# Pure simulation tests (no file I/O – always runnable)
# ---------------------------------------------------------------------------


class TestSimulation:
    """
    Simulate the full frontend merge-strategy flow.
    These tests are self-contained and need no server/file-system.
    """

    # Realistic backend output for test_case.txt on a blank document
    # (mirrors what /api/process returns – kept static so tests are always runnable)
    WORLD_ENGINE_CHUNKS = [
        {
            "section": "Feature: World Engine",
            "original_text": "(New Section)",
            "new_text": (
                "#### Context, Aim & Integration\n\n"
                "The Engine is a headless simulation environment that manages the world state "
                "without awareness of player identities, focusing solely on **Entities** and **States**."
            ),
        },
        {
            "section": "Feature: World Engine",
            "original_text": "(New Section)",
            "new_text": (
                "#### Technical Requirements\n\n"
                "* **State Resolution:** Must calculate results of worker/task pairings based on regional deltas.\n"
                "* **Randomness Authority:** Centralized RNG for monster raids, caravan survival, and loot tables.\n"
                "* **Ownership Registry:** Authoritative ledger for city, road, and worker ownership.\n"
                "* **The Event Log:** Immutable record of world events."
            ),
        },
        {
            "section": "Feature: World Engine",
            "original_text": "(New Section)",
            "new_text": (
                "#### Constraints\n\n"
                "* The Engine must ignore any command not signed/originated by the Controller.\n"
                "* State updates are computed as deltas triggered by player interaction or \"ticks\"."
            ),
        },
    ]

    def test_chunk1_uses_template_strategy(self):
        """Chunk 1 on a blank struct → Case 1 (whole template is empty)."""
        struct: dict = {}
        strategy = decide_merge_strategy(
            "Feature: World Engine", self.WORLD_ENGINE_CHUNKS[0], struct
        )
        assert strategy == "template", f"Expected 'template', got '{strategy}'"

    def test_chunk2_uses_subsection_strategy_after_chunk1(self):
        """
        Regression: after chunk 1 is committed, Technical Requirements slot is still
        empty inside the partially-filled template → must use 'subsection', NOT 'llm'.
        """
        struct: dict = {}
        chunk1 = self.WORLD_ENGINE_CHUNKS[0]
        simulate_accept("Feature: World Engine", chunk1, "template", struct)

        # Confirm struct now has partly-filled content
        assert "Feature: World Engine" in struct
        assert "Context, Aim & Integration" in struct["Feature: World Engine"]

        strategy = decide_merge_strategy(
            "Feature: World Engine", self.WORLD_ENGINE_CHUNKS[1], struct
        )
        assert strategy != "llm", (
            "REGRESSION: Technical Requirements triggered LLM after chunk 1 was committed.\n"
            f"struct content:\n{struct.get('Feature: World Engine', '')}"
        )
        assert strategy == "subsection", f"Expected 'subsection', got '{strategy}'"

    def test_chunk3_uses_subsection_strategy_after_chunks1_and_2(self):
        """After chunks 1 and 2 are committed, Constraints slot is still empty → subsection."""
        struct: dict = {}
        for chunk in self.WORLD_ENGINE_CHUNKS[:2]:
            strategy = decide_merge_strategy("Feature: World Engine", chunk, struct)
            simulate_accept("Feature: World Engine", chunk, strategy, struct)

        strategy = decide_merge_strategy(
            "Feature: World Engine", self.WORLD_ENGINE_CHUNKS[2], struct
        )
        assert strategy != "llm", (
            "REGRESSION: Constraints triggered LLM after chunks 1+2 were committed."
        )
        assert strategy == "subsection", f"Expected 'subsection', got '{strategy}'"

    def test_all_world_engine_chunks_no_llm_sequential(self):
        """Full sequential flow: every World Engine chunk avoids LLM."""
        struct: dict = {}
        violations = []

        for i, chunk in enumerate(self.WORLD_ENGINE_CHUNKS):
            strategy = decide_merge_strategy("Feature: World Engine", chunk, struct)
            header = chunk["new_text"].splitlines()[0].strip()
            if strategy == "llm":
                violations.append(f"Chunk {i+1} ('{header}') → llm")
            else:
                simulate_accept("Feature: World Engine", chunk, strategy, struct)

        assert not violations, (
            "LLM triggered for World Engine chunks:\n" + "\n".join(violations)
        )

    def test_subsection_slot_emptiness_detection(self):
        """
        Unit test for the slot-emptiness check in decide_merge_strategy (Case 1.5).
        Verifies that a #### subsection consisting only of its header line
        (no body content) is correctly identified as empty.
        """
        template = generate_feature_template("Test Feature")
        assert is_template_with_structure(template)

        # After inserting content into slot A, slot B must still be empty
        chunk_a = {"original_text": "(New Section)", "new_text": "#### Technical Requirements\n\nSome content here."}
        struct: dict = {}
        simulate_accept("Feature: Test Feature", chunk_a, "template", struct)

        partial = struct["Feature: Test Feature"]
        # "Constraints" slot should still be empty
        orig_secs = parse_subsections(partial)
        constraints = orig_secs.get("Constraints", "")
        body = constraints.split("\n")[1:]
        assert all(not l.strip() for l in body), (
            f"Expected Constraints slot to be empty, got: {repr(constraints)}"
        )


# ---------------------------------------------------------------------------
# End-to-end simulation over ALL chunks from test_case.txt (backend-assisted)
# ---------------------------------------------------------------------------


class TestFullSimulation:
    """
    Full stateful simulation using real /api/process data.
    Accepts each chunk sequentially and asserts no LLM is needed at any point.
    """

    async def test_no_llm_for_full_test_case(self, tmp_data):
        """
        Processes the complete test_case.txt and simulates the frontend merge
        strategy for every returned chunk, in order.
        Asserts that not a single chunk requires the LLM.
        """
        matches = await _run_process(tmp_data)

        # Group matches into per-section queues (mirrors JS pendingMerges)
        pending: dict = {}
        for m in matches:
            pending.setdefault(m["section"], []).append(m)

        struct: dict = {}
        violations: list = []
        log: list = []

        for title, queue in pending.items():
            for chunk in queue:
                strategy = decide_merge_strategy(title, chunk, struct)
                header = chunk["new_text"].splitlines()[0][:60] if chunk["new_text"] else "(empty)"
                entry = f"section='{title}' | strategy='{strategy}' | header='{header}'"
                log.append(entry)

                if strategy == "llm":
                    violations.append(entry)
                else:
                    simulate_accept(title, chunk, strategy, struct)

        print("\n[simulation] Merge decisions:")
        for e in log:
            print(f"  {'✗' if 'llm' in e else '✓'} {e}")

        assert not violations, (
            f"\nLLM would be triggered for {len(violations)} chunk(s):\n"
            + "\n".join(f"  ✗ {v}" for v in violations)
        )
