"""
Fixtures module for ordered LLM input loading.

Provides utilities to load, order, and manage test inputs for merge scenario testing.
Each input has a sequence ID for guaranteed ordering.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List
import re


@dataclass
class LLMInput:
    """
    Represents a single ordered LLM input for merge testing.
    
    Attributes:
        sequence_id: Order in the test sequence (1-indexed, extracted from filename)
        name: Human-readable identifier (filename without number prefix)
        raw_text: The full protocol-formatted input text
        target_section: Expected target section parsed from metadata
        change_summary: Expected change summary parsed from metadata
    """
    sequence_id: int
    name: str
    raw_text: str
    target_section: str
    change_summary: str


def parse_input_metadata(raw_text: str) -> tuple[str, str]:
    """
    Parse Target-Section and Change-Summary from protocol input.
    
    Args:
        raw_text: Full text containing <<<SPEC_START>>> block(s)
    
    Returns:
        Tuple of (target_section, change_summary), first match only
    """
    pattern = r"<<<SPEC_START>>>\s+(?:[*]\s*)?Target-Section:\s*(.*?)\n\s*(?:[*]\s*)?Change-Summary:\s*(.*?)\n"
    match = re.search(pattern, raw_text, re.DOTALL)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", ""


def load_inputs_from_dir(inputs_dir: Path) -> List[LLMInput]:
    """
    Load all .txt files from a directory as ordered LLM inputs.
    
    Files must be named with numeric prefix: 01_name.txt, 02_name.txt, etc.
    Returns inputs sorted by sequence ID.
    
    Args:
        inputs_dir: Path to directory containing input files
        
    Returns:
        List of LLMInput objects, sorted by sequence_id
    """
    inputs = []
    
    for file_path in sorted(inputs_dir.glob("*.txt")):
        # Extract sequence ID from filename (e.g., "01_architecture.txt" -> 1)
        filename = file_path.stem
        match = re.match(r"^(\d+)_(.+)$", filename)
        if not match:
            continue
            
        sequence_id = int(match.group(1))
        name = match.group(2)
        raw_text = file_path.read_text(encoding="utf-8")
        target_section, change_summary = parse_input_metadata(raw_text)
        
        inputs.append(LLMInput(
            sequence_id=sequence_id,
            name=name,
            raw_text=raw_text,
            target_section=target_section,
            change_summary=change_summary
        ))
    
    return sorted(inputs, key=lambda x: x.sequence_id)


def get_scenario_path(scenario_name: str) -> Path:
    """
    Get the path to a test scenario directory.
    
    Args:
        scenario_name: Name of scenario (e.g., "case_1_additive")
        
    Returns:
        Path to the scenario directory
    """
    return Path(__file__).parent / scenario_name


def load_scenario_inputs(scenario_name: str) -> List[LLMInput]:
    """
    Convenience function to load all inputs for a named scenario.
    
    Args:
        scenario_name: Name of scenario directory
        
    Returns:
        List of LLMInput objects for this scenario
    """
    scenario_path = get_scenario_path(scenario_name)
    inputs_dir = scenario_path / "inputs"
    return load_inputs_from_dir(inputs_dir)
