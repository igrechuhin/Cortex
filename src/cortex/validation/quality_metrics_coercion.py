"""Coercion helpers for quality metrics input types."""

from cortex.core.models import DetailedFileMetadata, ModelDict
from cortex.validation.models import (
    DuplicationDataModel,
    FileMetadataForQuality,
    LinkValidationDataModel,
)


def coerce_file_metadata(
    metadata: DetailedFileMetadata | FileMetadataForQuality | ModelDict,
) -> FileMetadataForQuality:
    """Coerce metadata to FileMetadataForQuality."""
    if isinstance(metadata, FileMetadataForQuality):
        return metadata
    if isinstance(metadata, DetailedFileMetadata):
        return FileMetadataForQuality(
            last_modified=metadata.last_modified,
            token_count=metadata.token_count,
            size_bytes=metadata.size_bytes,
            read_count=metadata.read_count,
            write_count=metadata.write_count,
        )
    return FileMetadataForQuality.model_validate(metadata)


def coerce_files_metadata_map(
    files_metadata: dict[
        str, DetailedFileMetadata | FileMetadataForQuality | ModelDict
    ],
) -> dict[str, FileMetadataForQuality]:
    """Coerce files metadata dict to FileMetadataForQuality values."""
    coerced: dict[str, FileMetadataForQuality] = {}
    for file_name, meta in files_metadata.items():
        coerced[file_name] = coerce_file_metadata(meta)
    return coerced


def coerce_duplication_data(
    duplication_data: DuplicationDataModel | ModelDict,
) -> DuplicationDataModel:
    """Coerce duplication data to DuplicationDataModel."""
    if isinstance(duplication_data, DuplicationDataModel):
        return duplication_data
    dup_count_raw = duplication_data.get("duplicates_found", 0)
    dup_count = int(dup_count_raw) if isinstance(dup_count_raw, (int, float)) else 0
    return DuplicationDataModel(duplicates_found=dup_count)


def coerce_link_validation_data(
    link_validation: LinkValidationDataModel | ModelDict | None,
) -> LinkValidationDataModel | None:
    """Coerce link validation to LinkValidationDataModel or None."""
    if link_validation is None or isinstance(link_validation, LinkValidationDataModel):
        return link_validation
    broken_raw = link_validation.get("broken_links", 0)
    if isinstance(broken_raw, list):
        broken = len(broken_raw)
    else:
        broken = int(broken_raw) if isinstance(broken_raw, (int, float)) else 0
    return LinkValidationDataModel(broken_links=broken)
