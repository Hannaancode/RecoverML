"""Aligned retinal feature entry point, separately retireable from legacy."""
import numpy as np
from scipy.ndimage import gaussian_filter


def features(images):
    green = images[..., 1].astype(np.float32) / np.float32(255.)
    smooth1 = gaussian_filter(green, sigma=(0, 1, 1))
    smooth2 = gaussian_filter(green, sigma=(0, 2, 2))
    gy, gx = np.gradient(smooth1, axis=(1, 2))
    return np.ascontiguousarray(np.stack(
        [green, smooth1, smooth2, gx, gy, np.hypot(gx, gy)], axis=-1).reshape(-1, 6),
        dtype=np.float32)
