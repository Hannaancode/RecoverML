"""Recorded older extractor with an injected spatial alignment defect."""
import numpy as np
from .eyeai_current import features as aligned_features


def features(images):
    aligned = aligned_features(images).reshape(*images.shape[:3], 6)
    return np.ascontiguousarray(np.roll(aligned, 3, axis=2).reshape(-1, 6))
