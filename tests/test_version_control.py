"""
Unit Tests for Version Control functionality.

Tests the document versioning, rollback, and annotation features
without requiring the full server or Ollama.
"""

import pytest
import json
import shutil
from pathlib import Path
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.document_manager import DocumentManager, DATA_DIR, HISTORY_DIR


class TestVersionControl:
    """
    Tests for the version control system in DocumentManager.
    
    Covers:
    - Version initialization on document creation
    - Version increment triggers
    - Rollback functionality
    - Annotated output generation
    """
    
    @pytest.fixture
    def manager(self, tmp_path, monkeypatch):
        """
        Create a DocumentManager with isolated data directory.
        
        Uses a temp directory to avoid polluting real data.
        """
        # Monkeypatch the DATA_DIR and HISTORY_DIR
        test_data_dir = tmp_path / "data"
        test_history_dir = test_data_dir / "_history"
        
        monkeypatch.setattr("server.document_manager.DATA_DIR", test_data_dir)
        monkeypatch.setattr("server.document_manager.HISTORY_DIR", test_history_dir)
        
        return DocumentManager()
    
    def test_init_creates_version_one(self, manager):
        """
        Document initialization should create version 1.
        
        Verifies:
        - VC file is created
        - Version is 1
        - Trigger is 'init'
        """
        manager.init_document("test_doc", reset=True)
        
        vc_data = manager.get_vc_data("test_doc")
        
        assert vc_data["current_version"] == 1
        assert len(vc_data["versions"]) == 1
        assert vc_data["versions"][0]["trigger"] == "init"
        assert vc_data["versions"][0]["comment"] == "Initial document creation"
    
    def test_init_creates_history_snapshot(self, manager):
        """
        Document initialization should create v1 snapshot.
        """
        manager.init_document("test_doc", reset=True)
        
        history_dir = manager._get_history_dir("test_doc")
        snapshot = history_dir / "v1.md"
        
        assert snapshot.exists()
        assert "# Document Title" in snapshot.read_text()
    
    def test_save_increments_version(self, manager):
        """
        Saving document with changes should increment version.
        """
        manager.init_document("test_doc", reset=True)
        
        # Save with new content
        manager.save_document("test_doc", "# New Content\n\nUpdated.")
        
        vc_data = manager.get_vc_data("test_doc")
        
        assert vc_data["current_version"] == 2
        assert len(vc_data["versions"]) == 2
        assert vc_data["versions"][-1]["trigger"] == "manual_edit"
    
    def test_save_same_content_no_version_bump(self, manager):
        """
        Saving identical content should NOT increment version.
        """
        manager.init_document("test_doc", reset=True)
        original_content = manager.get_document("test_doc")
        
        # Save same content
        manager.save_document("test_doc", original_content)
        
        vc_data = manager.get_vc_data("test_doc")
        
        assert vc_data["current_version"] == 1  # Still version 1
    
    def test_simple_save_no_version_bump(self, manager):
        """
        Simple save should NOT increment version (for intermediate states).
        """
        manager.init_document("test_doc", reset=True)
        
        # Use simple save
        manager.save_document_simple("test_doc", "# Intermediate\n\nContent.")
        
        vc_data = manager.get_vc_data("test_doc")
        
        assert vc_data["current_version"] == 1  # Still version 1
    
    def test_merge_validation_increments_version(self, manager):
        """
        Validating merge completion should increment version.
        """
        manager.init_document("test_doc", reset=True)
        
        # Simulate merge workflow: simple saves then validate
        manager.save_document_simple("test_doc", "# Merged Content\n\nAll merged.")
        manager.complete_merge_validation("test_doc", "Completed all merges")
        
        vc_data = manager.get_vc_data("test_doc")
        
        assert vc_data["current_version"] == 2
        assert vc_data["versions"][-1]["trigger"] == "merge_complete"
        assert "Completed all merges" in vc_data["versions"][-1]["comment"]
    
    def test_save_with_sections_changed(self, manager):
        """
        Saving with sections_changed should update section history.
        """
        manager.init_document("test_doc", reset=True)
        
        manager.save_document(
            "test_doc", 
            "# New Content",
            trigger="section_merge",
            sections_changed=["Feature: Auth"]
        )
        
        vc_data = manager.get_vc_data("test_doc")
        
        assert "Feature: Auth" in vc_data["section_history"]
        assert vc_data["section_history"]["Feature: Auth"][0]["version"] == 2
    
    def test_rollback_restores_content(self, manager):
        """
        Rollback should restore document to previous version's content.
        """
        manager.init_document("test_doc", reset=True)
        original = manager.get_document("test_doc")
        
        # Make changes
        manager.save_document("test_doc", "# V2 Content\n\nChanged.")
        manager.save_document("test_doc", "# V3 Content\n\nChanged again.")
        
        # Rollback to v1
        success = manager.rollback_to_version("test_doc", 1)
        
        assert success
        current = manager.get_document("test_doc")
        assert current == original
    
    def test_rollback_increments_version(self, manager):
        """
        Rollback should create a NEW version (not decrement).
        """
        manager.init_document("test_doc", reset=True)
        manager.save_document("test_doc", "# V2\n\n")
        
        manager.rollback_to_version("test_doc", 1)
        
        vc_data = manager.get_vc_data("test_doc")
        
        # Should be version 3 (v1 init, v2 save, v3 rollback)
        assert vc_data["current_version"] == 3
        assert vc_data["versions"][-1]["trigger"] == "rollback"
        assert "version 1" in vc_data["versions"][-1]["comment"]
    
    def test_rollback_nonexistent_version_fails(self, manager):
        """
        Rolling back to a non-existent version should fail.
        """
        manager.init_document("test_doc", reset=True)
        
        success = manager.rollback_to_version("test_doc", 999)
        
        assert not success
    
    def test_annotated_output_includes_version_section(self, manager):
        """
        Annotated output should include Version History section.
        """
        manager.init_document("test_doc", reset=True)
        
        annotated = manager.get_document_annotated("test_doc")
        
        assert "## Version History" in annotated
        assert "**Current Version:** 1" in annotated
        assert "| v1 |" in annotated
    
    def test_annotated_output_includes_section_annotations(self, manager):
        """
        Annotated output should include per-section version notes.
        """
        manager.init_document("test_doc", reset=True)
        
        # Save with section tracking
        manager.save_document(
            "test_doc",
            "# Doc Title\n\n## Feature 1\n\nUpdated content.",
            trigger="section_merge",
            sections_changed=["Feature 1"]
        )
        
        annotated = manager.get_document_annotated("test_doc")
        
        # Should have annotation for Feature 1
        assert "> *v2:" in annotated  # Version annotation
    
    def test_list_versions(self, manager):
        """
        list_versions should return all version entries.
        """
        manager.init_document("test_doc", reset=True)
        manager.save_document("test_doc", "# V2\n\n")
        manager.save_document("test_doc", "# V3\n\n")
        
        versions = manager.list_versions("test_doc")
        
        assert len(versions) == 3
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2
        assert versions[2]["version"] == 3


class TestVersionControlEdgeCases:
    """
    Edge case tests for version control.
    """
    
    @pytest.fixture
    def manager(self, tmp_path, monkeypatch):
        test_data_dir = tmp_path / "data"
        test_history_dir = test_data_dir / "_history"
        
        monkeypatch.setattr("server.document_manager.DATA_DIR", test_data_dir)
        monkeypatch.setattr("server.document_manager.HISTORY_DIR", test_history_dir)
        
        return DocumentManager()
    
    def test_get_vc_data_missing_file(self, manager):
        """
        get_vc_data should return empty structure for missing file.
        """
        vc_data = manager.get_vc_data("nonexistent")
        
        assert vc_data["current_version"] == 0
        assert vc_data["versions"] == []
    
    def test_multiple_consecutive_rollbacks(self, manager):
        """
        Multiple rollbacks should each create new version.
        """
        manager.init_document("test_doc", reset=True)
        manager.save_document("test_doc", "# V2\n\n")
        manager.save_document("test_doc", "# V3\n\n")
        
        manager.rollback_to_version("test_doc", 2)  # Now v4
        manager.rollback_to_version("test_doc", 1)  # Now v5
        
        vc_data = manager.get_vc_data("test_doc")
        
        assert vc_data["current_version"] == 5
        assert vc_data["versions"][-1]["trigger"] == "rollback"
        assert vc_data["versions"][-2]["trigger"] == "rollback"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
