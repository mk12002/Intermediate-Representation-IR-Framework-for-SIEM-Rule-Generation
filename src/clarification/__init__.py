"""Clarification: route under-specified-input detection to a question
instead of a silent omission, on top of the existing caveats/abstained
mechanism (missing info), plus closed-option disambiguation for
genuine structural forks (ambiguous-but-present info). See
gap_checker.py and clarify.py; PROJECT_STATUS.md §4AF/§4AG.
"""
from src.clarification.gap_checker import Gap, find_ambiguities, find_gaps, scan_ambiguities
from src.clarification.clarify import resolve_ambiguity, resolve_clarification

__all__ = ["Gap", "find_gaps", "find_ambiguities", "scan_ambiguities", "resolve_clarification", "resolve_ambiguity"]
