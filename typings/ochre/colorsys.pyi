"""
This type stub file was generated by pyright.
"""

from typing import Text

"""Simple color conversions.

This module is a drop-in replacement for the
[standard `colorsys` module](https://docs.python.org/3/library/colorsys.html).

It provides extra functionality to the standard `colorsys` module, but also re-exports
its contents for convenience.

Examples
--------
>>> from ochre import colorsys

This module provides some conversions, among which is RGB from and to HCL:

>>> colorsys.rgb_to_hcl(0.2, 0.4, 0.4)  # doctest: +NUMBER
(3.4, 0.2, 0.4)
>>> colorsys.hcl_to_rgb(3.4, 0.2, 0.4)  # doctest: +NUMBER
(0.2, 0.4, 0.4)

For convenience, the module also re-exports the standard conversions from `colorsys`:

>>> colorsys.rgb_to_hsv(0.2, 0.4, 0.4)
(0.5, 0.5, 0.4)
>>> colorsys.hsv_to_rgb(0.5, 0.5, 0.4)
(0.2, 0.4, 0.4)
"""
__all__ = ["hcl_to_rgb", "rgb_to_hcl", "hls_to_rgb", "hsv_to_rgb", "rgb_to_hls", "rgb_to_hsv", "rgb_to_yiq", "yiq_to_rgb"]
def rgb_to_xyz(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert the color from RGB coordinates to CIEXYZ coordinates."""
    ...

def xyz_to_rgb(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert the color from CIEXYZ coordinates to RGB coordinates."""
    ...

def luv_to_rgb(ell: float, u: float, v: float) -> tuple[float, float, float]:
    """Convert the color from CIELUV coordinates to RGB coordinates."""
    ...

def rgb_to_luv(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert the color from RGB coordinates to CIELUV coordinates."""
    ...

def hcl_to_rgb(h: float, c: float, ell: float) -> tuple[float, float, float]:
    """Convert the color from HCL coordinates to RGB coordinates."""
    ...

def rgb_to_hcl(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert the color from RGB coordinates to HCL coordinates."""
    ...

def xyz_to_luv(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert the color from CIEXYZ coordinates to CIELUV coordinates."""
    ...

def luv_to_xyz(ell: float, u: float, v: float) -> tuple[float, float, float]:
    """Convert the color from CIELUV coordinates to CIEXYZ coordinates."""
    ...

def luv_to_hcl(ell: float, u: float, v: float) -> tuple[float, float, float]:
    """Convert the color from CIELUV coordinates to HCL coordinates."""
    ...

def hcl_to_luv(h: float, c: float, ell: float) -> tuple[float, float, float]:
    """Convert the color from HCL coordinates to CIELUV coordinates."""
    ...

def rgb_to_hex(r: float, g: float, b: float) -> int:
    """Convert the color from RGB coordinates to hexadecimal."""
    ...

def hex_to_rgb(hc: int | Text) -> tuple[float, float, float]:
    """Convert the color from hexadecimal to RGB coordinates."""
    ...

def web_color_to_hex(name: Text) -> int:
    """Convert the color from web color name to hexadecimal."""
    ...

def web_color_to_rgb(name: Text) -> tuple[float, float, float]:
    """Convert the color from web color name to RGB coordinates."""
    ...

def ansi256_to_hex(c: int) -> int:
    """Convert the color from ANSI 256 color code to hexadecimal."""
    ...

def ansi256_to_rgb(c: int) -> tuple[float, float, float]:
    """Convert the color from ANSI 256 color code to RGB coordinates."""
    ...

def hex_to_hex(hc: int | Text) -> int:
    """Ensure that the hexadecimal code is an integer."""
    ...

EPSILON = ...
KAPPA = ...
REF_XYZ_D65_2 = ...
REF_UV_D65_2 = ...