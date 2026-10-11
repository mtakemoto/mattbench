def clamp(value, low, high):
    """Return value limited to the inclusive range from low to high."""
    return min(low, max(value, high))
