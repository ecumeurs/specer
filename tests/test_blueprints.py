import pytest
from pathlib import Path

from server.blueprints_manager import BlueprintsManager
from server.blueprint import Blueprint

@pytest.fixture
def temp_blueprints(tmp_path):
    mgr = BlueprintsManager(str(tmp_path))
    return mgr, tmp_path

def test_load_all_success(temp_blueprints):
    mgr, path = temp_blueprints
    
    # Create valid blueprint
    bp = path / "module.md"
    bp.write_text("""---
name: "module"
type: "numerable"
level: 3
allows_summary: true
template_prefix: "### "
parent_section: "Some Parent"
---
Template Body""")

    mgr.load_all()
    blueprints = mgr.list_blueprints()
    assert len(blueprints) == 1
    assert blueprints[0].meta.name == "module"
    assert "Template Body" in blueprints[0].template_content

def test_load_all_malformed_yaml(temp_blueprints):
    mgr, path = temp_blueprints
    
    bp = path / "bad.md"
    bp.write_text("""---
[bad yaml
---
Body""")

    mgr.load_all()
    assert len(mgr.list_blueprints()) == 0

def test_match_blueprint_for_title(temp_blueprints):
    mgr, path = temp_blueprints
    
    bp = path / "module.md"
    bp.write_text("""---
name: "module"
type: "numerable"
level: 3
allows_summary: true
template_prefix: "### "
parent_section: "Some Parent"
---
Template Body""")
    mgr.load_all()
    
    match = mgr.match_blueprint_for_title("### Commerce")
    assert match is not None
    assert match.meta.name == "module"
