"""
OmniKiosk Module 3: Document Computer Vision Scanner & Spatial Guidance
"""

from .document_scanner import (
    Frame,
    DocumentContourDetector,
    SpatialAlignmentEngine,
    SpatialGuidanceEngine,
    SharpnessEvaluator,
    AutoSnapshotController,
    LocalOCR,
    SyntheticFrameGenerator,
    DocumentScannerSession,
    SHARPNESS_THRESHOLD,
    STABILITY_FRAMES,
    OFFSET_THRESHOLD_PX,
    SKEW_THRESHOLD_DEG,
    FRAME_WIDTH,
    FRAME_HEIGHT,
    load_env,
)

__all__ = [
    "Frame",
    "DocumentContourDetector",
    "SpatialAlignmentEngine",
    "SpatialGuidanceEngine",
    "SharpnessEvaluator",
    "AutoSnapshotController",
    "LocalOCR",
    "SyntheticFrameGenerator",
    "DocumentScannerSession",
    "SHARPNESS_THRESHOLD",
    "STABILITY_FRAMES",
    "OFFSET_THRESHOLD_PX",
    "SKEW_THRESHOLD_DEG",
    "FRAME_WIDTH",
    "FRAME_HEIGHT",
    "load_env",
]
