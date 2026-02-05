import httpx as requests
import time
import json

BASE_URL = "http://localhost:8000/api"

def test_init_reset():
    print("Testing Init with Reset...")
    res = requests.post(f"{BASE_URL}/init", json={"name": "test_doc", "reset": True})
    assert res.status_code == 200
    data = res.json()
    assert "Document Title" in data["content"]
    assert "## Lexicon" in data["content"]
    print("PASS: Init Reset defaults enforced.")

def test_process_splitting():
    print("Testing Process Splitting...")
    # First init
    requests.post(f"{BASE_URL}/init", json={"name": "test_doc", "reset": True})
    
    text = """
<<<SPEC_START>>>
Target-Section: Features
Change-Summary: Added two features
    
### Feature A
Description A.

### Feature B
Description B.
<<<SPEC_END>>>
"""
    res = requests.post(f"{BASE_URL}/process", json={"name": "test_doc", "text": text})
    assert res.status_code == 200
    data = res.json()
    
    matches = data["matches"]
    print(f"DEBUG: Found {len(matches)} matches")
    # Should be 2 matches because we split by header
    assert len(matches) == 2
    assert matches[0]["new_text"].strip().startswith("### Feature A")
    assert matches[1]["new_text"].strip().startswith("### Feature B")
    print("PASS: Process Splitting logic working.")

if __name__ == "__main__":
    try:
        test_init_reset()
        test_process_splitting()
        print("ALL INTEGRATION TESTS PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
