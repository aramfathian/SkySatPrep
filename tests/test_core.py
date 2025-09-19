import numpy as np
from skysatprep.core import robust_percentiles, apply_shadow_highlight_tone

def test_percentiles_basic():
    arr = np.array([[0, 10, 100, 65535]], dtype=np.uint16)
    lo, hi = robust_percentiles(arr, 1, 99)
    assert 0 <= lo < hi <= 65535

def test_tone_curve_bounds():
    x = np.linspace(0, 1, 1000).astype(np.float32)
    y = apply_shadow_highlight_tone(x, shadow_boost=0.2, highlight_comp=0.1)
    assert np.all(y >= 0) and np.all(y <= 1)
    assert np.all(np.diff(y) >= -1e-6)