import requests
import json
import time

BASE_URL = "http://localhost:8001/api"

def test_flow():
    doc_name = "test_doc"
    
    print(f"1. Init Document '{doc_name}'...")
    res = requests.post(f"{BASE_URL}/init", json={"name": doc_name, "reset": True})
    print(res.json())
    assert res.status_code == 200

    # 2. Process (Match)
    print("\n2. Processing Protocol input...")
    protocol_text = """
<<<SPEC_START>>>
Target-Section: Introduction
Change-Summary: Update the introduction to mention AI.

# Introduction
This is an AI-powered merger tool.
<<<SPEC_END>>>
"""
    res = requests.post(f"{BASE_URL}/process", json={"name": doc_name, "text": protocol_text})
    print("Response:", json.dumps(res.json(), indent=2))
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    
    # 3. Diff (Merge)
    print("\n3. Generating Merge (Diff)...")
    original = data["match"]["original_text"]
    new_text = data["match"]["new_text"]
    
    res = requests.post(f"{BASE_URL}/diff", json={"original": original, "new": new_text})
    print("Response:", json.dumps(res.json(), indent=2))
    assert res.status_code == 200
    merged = res.json()["merged"]
    assert len(merged) > 0
    
    # 4. Commit
    print("\n4. Committing Change...")
    res = requests.post(f"{BASE_URL}/commit", json={"name": doc_name, "content": merged})
    print(res.json())
    assert res.status_code == 200

    print("\nAll tests passed!")

if __name__ == "__main__":
    try:
        test_flow()
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        exit(1)
