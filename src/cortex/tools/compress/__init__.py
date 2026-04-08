"""Compression utilities for Cortex internal text assets."""

from .batch import compress_cortex_internal_files, compress_directory
from .compress import CompressResult, compress_file
from .detect import FileType, detect_file_type
from .prompts import build_compress_prompt, build_fix_prompt
from .validate import ValidationResult, validate_compressed

__all__ = [
    "CompressResult",
    "FileType",
    "ValidationResult",
    "build_compress_prompt",
    "build_fix_prompt",
    "compress_directory",
    "compress_cortex_internal_files",
    "compress_file",
    "detect_file_type",
    "validate_compressed",
]
