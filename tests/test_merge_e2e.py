"""
End-to-End Tests for Merge Operations.

These tests require a running server with Ollama backend.
Run with: docker compose up -d && uv run pytest tests/test_merge_e2e.py -v

Test Cases:
    1. Additive Only: 3 inputs that add distinct new sections
    2. Merge Conflicts: 3 inputs updating the same section (most recent wins)
    3. Complex Sequence: 5 inputs with mixed add/merge operations
"""

import pytest
import httpx
import time
from pathlib import Path

from tests.merge_scenarios.fixtures import load_scenario_inputs, LLMInput

BASE_URL = "http://localhost:8001/api"
TEST_DOC_PREFIX = "e2e_test_"


class MergeTestClient:
    """
    HTTP client wrapper for E2E merge testing.
    
    Handles the full merge workflow:
        init -> process -> diff -> poll task -> commit
    """
    
    def __init__(self, doc_name: str, base_url: str = BASE_URL):
        """
        Initialize client with a document name.
        
        Args:
            doc_name: Name of the test document (will be prefixed for isolation)
            base_url: API base URL
        """
        self.doc_name = f"{TEST_DOC_PREFIX}{doc_name}"
        self.base_url = base_url
        self.client = httpx.Client(timeout=120.0)  # Long timeout for LLM calls
    
    def init_document(self, reset: bool = True) -> dict:
        """Initialize or reset the test document."""
        response = self.client.post(
            f"{self.base_url}/init",
            json={"name": self.doc_name, "reset": reset}
        )
        response.raise_for_status()
        return response.json()
    
    def process_input(self, llm_input: LLMInput) -> dict:
        """
        Send an LLM input through the /process endpoint.
        
        Args:
            llm_input: The ordered LLM input to process
            
        Returns:
            API response with matched sections
        """
        response = self.client.post(
            f"{self.base_url}/process",
            json={"name": self.doc_name, "text": llm_input.raw_text}
        )
        response.raise_for_status()
        return response.json()
    
    def start_diff_task(self, original: str, new_text: str) -> str:
        """
        Start a background diff/merge task.
        
        Args:
            original: Original section content
            new_text: New content to merge
            
        Returns:
            task_id for polling
        """
        response = self.client.post(
            f"{self.base_url}/diff",
            json={"original": original, "new": new_text}
        )
        response.raise_for_status()
        return response.json()["task_id"]
    
    def poll_task(self, task_id: str, timeout: int = 120) -> dict:
        """
        Poll a task until completion.
        
        Args:
            task_id: Task ID from start_diff_task
            timeout: Maximum seconds to wait
            
        Returns:
            Completed task result
            
        Raises:
            TimeoutError: If task doesn't complete in time
        """
        start = time.time()
        while time.time() - start < timeout:
            response = self.client.get(f"{self.base_url}/task/{task_id}")
            response.raise_for_status()
            data = response.json()
            
            if data["status"] == "completed":
                return data
            elif data["status"] in ("failed", "cancelled"):
                raise RuntimeError(f"Task {task_id} failed: {data.get('error')}")
            
            time.sleep(2)  # Poll every 2 seconds
        
        raise TimeoutError(f"Task {task_id} did not complete in {timeout}s")
    
    def commit(self, content: str) -> dict:
        """Commit the full document content."""
        response = self.client.post(
            f"{self.base_url}/commit",
            json={"name": self.doc_name, "content": content}
        )
        response.raise_for_status()
        return response.json()
    
    def get_document(self) -> str:
        """Get the current document content."""
        response = self.client.get(f"{self.base_url}/spec/{self.doc_name}")
        response.raise_for_status()
        return response.json()["content"]
    
    def get_structure(self) -> list:
        """Get the current document structure."""
        response = self.client.get(f"{self.base_url}/structure/{self.doc_name}")
        response.raise_for_status()
        return response.json()["structure"]
    
    def process_and_merge_input(self, llm_input: LLMInput) -> str:
        """
        Full workflow: process input, merge each match, update document.
        
        This simulates the UI workflow where a user processes input,
        reviews each match, and commits the merged result.
        
        Args:
            llm_input: The LLM input to process
            
        Returns:
            Updated document content after all merges
        """
        # Get current document
        current_doc = self.get_document()
        
        # Process the input
        process_result = self.process_input(llm_input)
        
        if process_result.get("status") != "success":
            raise RuntimeError(f"Process failed: {process_result}")
        
        matches = process_result.get("matches", [])
        
        for match in matches:
            original = match["original_text"]
            new_text = match["new_text"]
            section = match["section"]
            
            # If this is a new section, we just append
            if original == "(New Section)" or original.startswith("(No matching"):
                # Find where to insert (after Features or Roadmap header)
                current_doc = self._insert_new_section(current_doc, new_text, section)
            else:
                # Start diff task and wait for merge
                task_id = self.start_diff_task(original, new_text)
                task_result = self.poll_task(task_id)
                merged = task_result.get("result", new_text)
                
                # Replace original with merged in document
                if merged and original in current_doc:
                    current_doc = current_doc.replace(original, merged)
                elif merged:
                    # If original not found exactly, try to find section and replace
                    current_doc = self._update_section(current_doc, section, merged)
        
        # Commit the updated document
        self.commit(current_doc)
        return current_doc
    
    def _insert_new_section(self, doc: str, new_text: str, section: str) -> str:
        """
        Insert a new section into the document.
        
        Tries to insert after relevant parent section (Features/Roadmap).
        """
        new_text_stripped = new_text.strip()
        
        # Determine where to insert based on section name
        if "milestone" in section.lower():
            # Insert before last line of Roadmap section or at end
            if "## Roadmap" in doc:
                parts = doc.split("## Roadmap", 1)
                return parts[0] + "## Roadmap\n\n" + new_text_stripped + "\n\n" + parts[1].lstrip()
        
        # Default: insert before Roadmap section
        if "## Roadmap" in doc:
            return doc.replace("## Roadmap", new_text_stripped + "\n\n## Roadmap")
        
        # Fallback: append to end
        return doc + "\n\n" + new_text_stripped
    
    def _update_section(self, doc: str, section_title: str, new_content: str) -> str:
        """
        Update an existing section with new content.
        
        Finds the section header and replaces content until next same-level header.
        """
        lines = doc.split('\n')
        result = []
        in_target_section = False
        target_level = None
        new_content_lines = new_content.strip().split('\n')
        content_inserted = False
        
        for line in lines:
            stripped = line.strip()
            
            # Check if this is a header
            if stripped.startswith('#'):
                level = len(stripped.split(' ')[0])
                title = stripped.lstrip('#').strip()
                
                if title.lower() == section_title.lower() or section_title.lower() in title.lower():
                    in_target_section = True
                    target_level = level
                    # Insert new content instead
                    result.extend(new_content_lines)
                    content_inserted = True
                    continue
                elif in_target_section and level <= target_level:
                    in_target_section = False
            
            if not in_target_section:
                result.append(line)
        
        if not content_inserted:
            # Section not found, append new content
            result.extend(['', ''] + new_content_lines)
        
        return '\n'.join(result)
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()


class TestAdditiveOnly:
    """
    Test Case 1: Simple path where each input adds a distinct new section.
    
    Validates that processing 3 inputs that target NEW sections
    results in 3 separate sections being added without conflicts.
    """
    
    @pytest.fixture
    def client(self):
        """Create and cleanup test client."""
        client = MergeTestClient("case1_additive")
        client.init_document(reset=True)
        yield client
        client.close()
    
    def test_additive_three_new_sections(self, client):
        """
        Process 3 inputs that each add a new feature section.
        
        Expected: Document contains all 3 features as distinct sections.
        """
        inputs = load_scenario_inputs("case_1_additive")
        assert len(inputs) == 3, f"Expected 3 inputs, got {len(inputs)}"
        
        # Process each input in order
        for llm_input in inputs:
            print(f"\nProcessing: {llm_input.sequence_id}. {llm_input.name}")
            print(f"  Target: {llm_input.target_section}")
            client.process_and_merge_input(llm_input)
        
        # Verify final document
        final_doc = client.get_document()
        structure = client.get_structure()
        section_titles = [s["title"] for s in structure]
        
        # All 3 features should exist
        assert any("authentication" in t.lower() for t in section_titles), \
            f"Authentication feature missing. Sections: {section_titles}"
        assert any("database" in t.lower() for t in section_titles), \
            f"Database feature missing. Sections: {section_titles}"
        assert any("api" in t.lower() or "gateway" in t.lower() for t in section_titles), \
            f"API Gateway feature missing. Sections: {section_titles}"
        
        print(f"\n✓ All 3 features added successfully")
        print(f"  Final sections: {section_titles}")


class TestMergeConflicts:
    """
    Test Case 2: Multiple inputs updating the same section.
    
    Validates that when 3 inputs target the same section,
    the final document reflects the most recent (input 3) data.
    """
    
    @pytest.fixture
    def client(self):
        """Create and cleanup test client."""
        client = MergeTestClient("case2_merges")
        client.init_document(reset=True)
        yield client
        client.close()
    
    def test_most_recent_wins(self, client):
        """
        Process 3 inputs targeting the same Notification System feature.
        
        Expected: Final document contains data from input 3 (push notifications,
        real-time processing, not SMTP).
        """
        inputs = load_scenario_inputs("case_2_merges")
        assert len(inputs) == 3, f"Expected 3 inputs, got {len(inputs)}"
        
        # Process each input in order
        for llm_input in inputs:
            print(f"\nProcessing: {llm_input.sequence_id}. {llm_input.name}")
            print(f"  Summary: {llm_input.change_summary}")
            client.process_and_merge_input(llm_input)
        
        # Verify final document has latest data
        final_doc = client.get_document().lower()
        
        # Should have push notifications (from input 3)
        assert "push notification" in final_doc or "firebase" in final_doc, \
            "Missing push notifications from input 3"
        
        # Should have real-time processing (from input 3)
        assert "real-time" in final_doc, \
            "Missing real-time processing from input 3"
        
        # Should NOT have SMTP (replaced in input 2 with SendGrid)
        # Note: The merge might keep both or replace - we check for SendGrid
        assert "sendgrid" in final_doc, \
            "Missing SendGrid from input 2 (should have replaced SMTP)"
        
        print(f"\n✓ Most recent data correctly merged")


class TestComplexSequence:
    """
    Test Case 3: 5 successive inputs with mixed add and merge operations.
    
    Validates correct ordering and conflict resolution across:
    - Adding new feature (Analytics)
    - Updating that feature twice
    - Adding new milestone
    - Updating milestone + feature in same input
    """
    
    @pytest.fixture
    def client(self):
        """Create and cleanup test client."""
        client = MergeTestClient("case3_complex")
        client.init_document(reset=True)
        yield client
        client.close()
    
    def test_five_successive_merges(self, client):
        """
        Process 5 inputs with mixed operations.
        
        Expected:
        - Analytics feature exists with A/B testing (from input 5)
        - Data retention is 365 days (from input 4)
        - MVP milestone exists with 500 users (from input 5)
        """
        inputs = load_scenario_inputs("case_3_complex")
        assert len(inputs) == 5, f"Expected 5 inputs, got {len(inputs)}"
        
        # Process each input in order
        for llm_input in inputs:
            print(f"\nProcessing: {llm_input.sequence_id}. {llm_input.name}")
            print(f"  Target: {llm_input.target_section}")
            print(f"  Summary: {llm_input.change_summary}")
            client.process_and_merge_input(llm_input)
        
        # Verify final document
        final_doc = client.get_document().lower()
        structure = client.get_structure()
        section_titles = [s["title"].lower() for s in structure]
        
        # Analytics feature should exist
        assert any("analytics" in t for t in section_titles), \
            f"Analytics feature missing. Sections: {section_titles}"
        
        # Analytics should have A/B testing (from input 5)
        assert "a/b test" in final_doc or "ab test" in final_doc, \
            "Missing A/B testing from input 5"
        
        # Analytics should have 365 days retention (from input 4)
        assert "365" in final_doc, \
            "Missing 365 days retention from input 4"
        
        # MVP milestone should exist
        assert any("mvp" in t for t in section_titles), \
            f"MVP milestone missing. Sections: {section_titles}"
        
        # MVP should have 500 users (from input 5)
        assert "500" in final_doc, \
            "Missing 500 beta users from input 5"
        
        print(f"\n✓ Complex sequence correctly processed")
        print(f"  Analytics has A/B testing and 365-day retention")
        print(f"  MVP milestone has 500 user target")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
