"""AIF — AI-Native Format (AIF/0.9)."""

from .encoder import json_to_aif
from .decoder import aif_to_json

__version__ = "0.9.0"
__all__ = ["json_to_aif", "aif_to_json"]
