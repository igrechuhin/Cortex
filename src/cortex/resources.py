"""Resources (templates and guides) for MCP Memory Bank."""

from cortex.guides.benefits import GUIDE as BENEFITS_GUIDE
from cortex.guides.setup import GUIDE as SETUP_GUIDE
from cortex.guides.structure import GUIDE as STRUCTURE_GUIDE
from cortex.guides.usage import GUIDE as USAGE_GUIDE
from cortex.templates.active_context import TEMPLATE as ACTIVE_CONTEXT_TEMPLATE
from cortex.templates.memory_bank_instructions import (
    TEMPLATE as MEMORY_BANK_INSTRUCTIONS_TEMPLATE,
)
from cortex.templates.product_context import (
    TEMPLATE as PRODUCT_CONTEXT_TEMPLATE,
)
from cortex.templates.progress import TEMPLATE as PROGRESS_TEMPLATE
from cortex.templates.projectBrief import TEMPLATE as PROJECTBRIEF_TEMPLATE
from cortex.templates.system_patterns import (
    TEMPLATE as SYSTEM_PATTERNS_TEMPLATE,
)
from cortex.templates.tech_context import TEMPLATE as TECH_CONTEXT_TEMPLATE

TEMPLATES = {
    "memorybankinstructions.md": MEMORY_BANK_INSTRUCTIONS_TEMPLATE,
    "projectBrief.md": PROJECTBRIEF_TEMPLATE,
    "productContext.md": PRODUCT_CONTEXT_TEMPLATE,
    "activeContext.md": ACTIVE_CONTEXT_TEMPLATE,
    "systemPatterns.md": SYSTEM_PATTERNS_TEMPLATE,
    "techContext.md": TECH_CONTEXT_TEMPLATE,
    "progress.md": PROGRESS_TEMPLATE,
}

GUIDES = {
    "setup": SETUP_GUIDE,
    "usage": USAGE_GUIDE,
    "benefits": BENEFITS_GUIDE,
    "structure": STRUCTURE_GUIDE,
}
