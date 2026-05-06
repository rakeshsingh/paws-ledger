"""Vaccination schedule data loader.

Loads AAHA/AAFP vaccination guidelines from JSON files and provides
query functions for use in the UI vaccination forms.
"""

import json
import os
from typing import Dict, List

_DATA_DIR = os.path.dirname(__file__)


def _load_json(filename: str) -> Dict:
    path = os.path.join(_DATA_DIR, filename)
    with open(path, 'r') as f:
        return json.load(f)


# Load once at import time
_canine_data = _load_json('canine_vaccinations.json')
_feline_data = _load_json('feline_vaccinations.json')


def get_vaccination_schedule(species: str) -> Dict:
    """Get the full vaccination schedule for a species.

    Args:
        species: 'DOG' or 'CAT'

    Returns:
        Full vaccination data dict with core_vaccines and noncore_vaccines.
    """
    if species.upper() == 'DOG':
        return _canine_data
    elif species.upper() == 'CAT':
        return _feline_data
    return {'core_vaccines': [], 'noncore_vaccines': []}


def get_vaccine_names(species: str, include_noncore: bool = True) -> List[str]:
    """Get a flat list of vaccine names for a species.

    Args:
        species: 'DOG' or 'CAT'
        include_noncore: Whether to include noncore vaccines (default True)

    Returns:
        List of vaccine name strings.
    """
    data = get_vaccination_schedule(species)
    names = [v['name'] for v in data.get('core_vaccines', [])]
    if include_noncore:
        names.extend(v['name'] for v in data.get('noncore_vaccines', []))
    return names


def get_vaccine_details(species: str, vaccine_name: str) -> Dict:
    """Get full details for a specific vaccine by name.

    Args:
        species: 'DOG' or 'CAT'
        vaccine_name: The vaccine name to look up

    Returns:
        Vaccine detail dict or empty dict if not found.
    """
    data = get_vaccination_schedule(species)
    all_vaccines = data.get('core_vaccines', []) + data.get('noncore_vaccines', [])
    for v in all_vaccines:
        if v['name'] == vaccine_name:
            return v
    return {}


def get_vaccine_options_for_dropdown(species: str) -> Dict[str, str]:
    """Get vaccine options formatted for a NiceGUI select dropdown.

    Returns a dict of {display_label: vaccine_name} with category grouping hints.
    """
    data = get_vaccination_schedule(species)
    options = {}

    for v in data.get('core_vaccines', []):
        label = f"[Core] {v['name']}"
        options[label] = v['name']

    for v in data.get('noncore_vaccines', []):
        label = f"[Noncore] {v['name']}"
        options[label] = v['name']

    return options
