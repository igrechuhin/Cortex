"""
Phase 3: Validation and Quality Tools

This module previously contained validation configuration tools.

All Phase 3 tools have been consolidated:
- validate_memory_bank → validate(check_type="schema") in tools/consolidated.py
- check_duplications → validate(check_type="duplications") in tools/consolidated.py
- get_quality_score → validate(check_type="quality") in tools/consolidated.py
- check_token_budget → get_memory_bank_stats(include_token_budget=True) in tools/phase1_foundation.py
- configure_validation → configure(component="validation") in tools/consolidated.py

Total: 0 tools (all consolidated)
"""
