"""hardware package — VRAM-aware generation profiles."""

from capos.hardware.profile import (
    GENERATION_PROFILES,
    HardwareProfile,
    assert_single_concurrency,
    default_low_vram_profile,
    detect_gpu,
    load_hardware_profile,
    resolve_generation_settings,
    save_hardware_profile,
)

__all__ = [
    "GENERATION_PROFILES",
    "HardwareProfile",
    "assert_single_concurrency",
    "default_low_vram_profile",
    "detect_gpu",
    "load_hardware_profile",
    "resolve_generation_settings",
    "save_hardware_profile",
]
