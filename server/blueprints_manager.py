from pathlib import Path
from typing import Dict, List, Optional
import yaml

from server.blueprint import Blueprint, BlueprintMeta

class BlueprintsManager:
    """
    Service responsible for loading, parsing, and providing structural blueprints 
    from a filesystem configuration directory.
    
    Context Compilation:
    - Goal: Decouple hardcoded templates (e.g. "Feature") from document generation and parsing.
    - Path: Reads `.md` files containing YAML frontmatter from `blueprints/` dir.
    - Plan:
        1. Initialize with specific directory path.
        2. Iterate directory, read `.md` files.
        3. Extract YAML between `---` blocks.
        4. Parse remaining text as `template_content`.
        5. Store instances of `Blueprint`.
    - Unknowns:
        - How to gracefully handle missing fields in YAML without crashing?
    """
    
    def __init__(self, blueprints_dir: str = "blueprints"):
        self.blueprints_dir = Path(blueprints_dir)
        self._cache: Dict[str, Blueprint] = {}

    def load_all(self) -> None:
        """
        Reloads all blueprints from the configured directory.
        Clears existing in-memory cache and populates with new items.
        """
        self._cache.clear()
        if not self.blueprints_dir.exists():
            print(f"Blueprints directory '{self.blueprints_dir}' not found.")
            return

        for path in self.blueprints_dir.glob("*.md"):
            try:
                content = path.read_text(encoding="utf-8")
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    yaml_content = parts[1].strip()
                    template_content = parts[2].lstrip()
                    
                    meta_dict = yaml.safe_load(yaml_content)
                    if meta_dict and isinstance(meta_dict, dict):
                        meta = BlueprintMeta(**meta_dict)
                        bp = Blueprint(meta=meta, template_content=template_content)
                        self._cache[meta.name] = bp
            except Exception as e:
                print(f"Failed to load blueprint {path}: {e}")

    def get_blueprint(self, name: str) -> Optional[Blueprint]:
        """
        Fetch a specific blueprint by its `name` attribute.
        """
        return self._cache.get(name)

    def list_blueprints(self) -> List[Blueprint]:
        """
        Return all loaded blueprints.
        """
        return list(self._cache.values())

    def match_blueprint_for_title(self, title: str) -> Optional[Blueprint]:
        """
        Determine which blueprint applies to a given markdown title
        based on the `template_prefix`.
        """
        for count, bp in enumerate(self._cache.values()):
            if title.strip().startswith(bp.meta.template_prefix):
                return bp
        return None

# Global instance for app
blueprints_manager = BlueprintsManager()
