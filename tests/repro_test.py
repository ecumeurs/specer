
import asyncio
from server.document_manager import manager
from server.main import process_text, ProcessRequest
from pathlib import Path

# Mock Vector Store for consistent results without running Ollama
from unittest.mock import AsyncMock, patch
from server.vector_store import store

async def run_test():
    # 1. Setup Document
    doc_name = "repro_test_doc"
    manager.init_document(doc_name, reset=True)
    
    # Check initial structure logic? 
    # The default doc has: Context, Aim & Integration > Integration? 
    # Let's check default content in manager.init_document
    # Default has: "Context, Aim & Integration" -> "Integration" subheader? 
    # No, default has:
    # ## Context, Aim & Integration
    # ### Context
    # ### Aim
    # ### Integration
    
    # 2. Read Test Case
    test_content = Path("tests/test_case.txt").read_text()
    
    # 3. Process
    req = ProcessRequest(name=doc_name, text=test_content)
    
    # We mock store.find_best_match to ensure we rely on Structure Matching for the first case
    # If structure matching works, finding embeddings shouldn't matter as much.
    # But if it falls back, we want to control it.
    
    with patch('server.vector_store.store.find_best_match', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = None # Simulate no semantic match to force new section or verify structure match priority
        
        result = await process_text(req)
        
    matches = result["matches"]
    print(f"Found {len(matches)} matches.")
    
    # 4. Assertions
    
    # Block 1: Target-Section: Context, Aim & Integration: Integration
    # Expected: Should match "Integration" (suffix) or "Context, Aim & Integration" ?
    # The default doc has "Integration" as a header under "Context, Aim & Integration". 
    # manager.get_structure returns flat list of sections.
    # Let's verify what manager.get_structure returns for the default doc first.
    structure = manager.get_structure(doc_name)
    titles = [s['title'] for s in structure]
    print(f"Existing Titles: {titles}")
    
    # Matches are flattened. count chunks per block to index correctly.
    # Block 1: 2 chunks (Integration)
    # Block 2: 3 chunks (World Engine)
    # Block 3: 3 chunks (UI Architecture)
    # Block 4: 6 chunks (Roadmap)
    
    # Block 1
    m1 = matches[0]
    print(f"Match 1 (Block 1) Assignment: '{m1['section']}'")
    assert m1['section'] == "Integration" or m1['section'] == "Context, Aim & Integration", \
        f"Block 1 failed: Got {m1['section']}"

    # Block 2
    # Start index = 2
    m2 = matches[2]
    print(f"Match 2 (Block 2) Assignment: '{m2['section']}'")
    assert "World Engine" in m2['section'], f"Block 2 failed: Got {m2['section']}"
    assert m2['original_text'] == "(New Section)", f"Block 2 failed: Expected New Section, got '{m2['original_text']}'"
    
    # Block 3
    # Start index = 2 + 3 = 5
    m3 = matches[5]
    print(f"Match 3 (Block 3) Assignment: '{m3['section']}'")
    assert "UI Architecture" in m3['section'], f"Block 3 failed: Got {m3['section']}"
    assert m3['original_text'] == "(New Section)", f"Block 3 failed: Expected New Section, got '{m3['original_text']}'"

    # Block 4
    # Expected: "Milestone 1...", "Milestone 2..." should be NEW sections, not merged into "Roadmap".
    # Iterate through roadmap matches
    print("Block 4 matches:")
    milestone_matches = 0
    for i in range(8, len(matches)):
        m = matches[i]
        header = m['new_text'].splitlines()[0] if m['new_text'] else ""
        print(f"Match {i+1} Assignment: '{m['section']}' - Header: {header[:30]}...")
        
        # We expect matches that have clear Milestone headers to be assigned to that Milestone Title
        if "Milestone" in header:
             milestone_matches += 1
             # Current Bug: It assigns to "Roadmap" because Target-Section is "Roadmap"
             # Goal: Assign to "Milestone 1: The Scavenger (MVP)"
             assert "Milestone" in m['section'], f"Expected Section to be Milestone, got '{m['section']}'"
             assert m['original_text'] == "(New Section)", f"Expected New Section for Milestone, got '{m['original_text']}'"

    assert milestone_matches > 0, "No milestone chunks found?"

if __name__ == "__main__":
    asyncio.run(run_test())
