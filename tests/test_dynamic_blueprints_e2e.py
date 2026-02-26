import pytest
from tests.test_merge_e2e import MergeTestClient
from tests.merge_scenarios.fixtures import LLMInput

@pytest.fixture
def alternate_client():
    client = MergeTestClient("alternate_tree")
    client.init_document(reset=True)
    
    # Overwrite the document with the alternate_tree.md content
    with open("alternate_tree.md", "r", encoding="utf-8") as f:
        content = f.read()
    
    client.commit(content)
    yield client
    client.close()

def test_add_module_to_alternate_tree(alternate_client):
    """
    Test that we can process an input that adds a new 'Module'
    to the alternate_tree.md document structure, leveraging dynamic blueprints.
    """
    input_text = """
<<<SPEC_START>>>
Target-Section: Module: Diplomacy
Change-Summary: Adding a new diplomacy module

## MODULE SPECIFICATIONS (The Children)

### Module: Diplomacy

* **Core Loop:** Scout -> Negotiate -> Form Alliance
* **Primary Input (From Core):** Faction Tension, Resource Scarcity
* **Primary Output (To Core):** Treaties, Reduced Market Prices, Military Support
<<<SPEC_END>>>
"""
    
    llm_input = LLMInput(
        sequence_id=1,
        name="Add Diplomacy Module",
        target_section="Module: Diplomacy",
        change_summary="Adding a new diplomacy module",
        raw_text=input_text
    )
    
    alternate_client.process_and_merge_input(llm_input)
    
    final_doc = alternate_client.get_document()
    structure = alternate_client.get_structure()
    section_titles = [s["title"] for s in structure]
    
    assert any("Diplomacy" in t for t in section_titles), "Diplomacy module missing from structure"
    assert "Form Alliance" in final_doc
    assert "Treaties" in final_doc
    
def test_blueprint_system_loads():
    """
    Simple test to verify that the BlueprintsManager successfully loads the module.md 
    blueprint that we expect to drive the e2e module.
    """
    from server.blueprints_manager import blueprints_manager
    blueprints_manager.load_all()
    blueprints = blueprints_manager.list_blueprints()
    assert len(blueprints) > 0, "Expected at least one blueprint to be loaded"
    assert any(bp.meta.name == "module" for bp in blueprints), "Module blueprint not found"
