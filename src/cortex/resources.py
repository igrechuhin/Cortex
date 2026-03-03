"""Resources (templates and guides) for MCP Memory Bank."""

from cortex.core.constants import MemoryBankFile
from cortex.guides.benefits import GUIDE as BENEFITS_GUIDE
from cortex.guides.setup import GUIDE as SETUP_GUIDE
from cortex.guides.structure import GUIDE as STRUCTURE_GUIDE
from cortex.guides.usage import GUIDE as USAGE_GUIDE
from cortex.templates.active_context import TEMPLATE as ACTIVE_CONTEXT_TEMPLATE
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
    MemoryBankFile.PROJECT_BRIEF: PROJECTBRIEF_TEMPLATE,
    MemoryBankFile.PRODUCT_CONTEXT: PRODUCT_CONTEXT_TEMPLATE,
    MemoryBankFile.ACTIVE_CONTEXT: ACTIVE_CONTEXT_TEMPLATE,
    MemoryBankFile.SYSTEM_PATTERNS: SYSTEM_PATTERNS_TEMPLATE,
    MemoryBankFile.TECH_CONTEXT: TECH_CONTEXT_TEMPLATE,
    MemoryBankFile.PROGRESS: PROGRESS_TEMPLATE,
}

GUIDES = {
    "setup": SETUP_GUIDE,
    "usage": USAGE_GUIDE,
    "benefits": BENEFITS_GUIDE,
    "structure": STRUCTURE_GUIDE,
}
