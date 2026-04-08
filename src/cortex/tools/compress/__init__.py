"""Compression utilities for Cortex internal text assets."""

from .batch import (
    CompressionBatchSummary,
    CompressionVerificationResult,
    compress_cortex_internal_files,
    compress_directory,
    summarize_compression_results,
    verify_compression_success_criteria,
)
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
    "CompressionBatchSummary",
    "CompressionVerificationResult",
    "compress_directory",
    "compress_cortex_internal_files",
    "compress_file",
    "detect_file_type",
    "summarize_compression_results",
    "verify_compression_success_criteria",
    "validate_compressed",
]
