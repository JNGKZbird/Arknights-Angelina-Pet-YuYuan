"""Spine 3.8 runtime for Python — ported from spine-ts 3.8 (Esoteric Software)."""


class Color:
    def __init__(self, r=1.0, g=1.0, b=1.0, a=1.0):
        self.r, self.g, self.b, self.a = r, g, b, a

    def set(self, r, g, b, a):
        self.r, self.g, self.b, self.a = r, g, b, a

    def __repr__(self):
        return f"Color({self.r:.2f},{self.g:.2f},{self.b:.2f},{self.a:.2f})"

    @staticmethod
    def rgba8888(color, value):
        color.r = ((value & 0xFF000000) >> 24) / 255.0
        color.g = ((value & 0x00FF0000) >> 16) / 255.0
        color.b = ((value & 0x0000FF00) >> 8) / 255.0
        color.a = (value & 0x000000FF) / 255.0

    @staticmethod
    def rgb888(color, value):
        color.r = ((value & 0x00FF0000) >> 16) / 255.0
        color.g = ((value & 0x0000FF00) >> 8) / 255.0
        color.b = (value & 0x000000FF) / 255.0


import math as _math


def deg_to_rad(deg):
    return deg * _math.pi / 180.0


def rad_to_deg(rad):
    return rad * 180.0 / _math.pi


class _Curves:
    LINEAR = 0
    STEPPED = 1
    BEZIER = 2

    @staticmethod
    def apply(curves, index, time):
        # index: curve index (offset of the 19-float block within the curve data)
        curve_type = curves[index]
        if curve_type == _Curves.LINEAR:
            return time
        if curve_type == _Curves.STEPPED:
            return 0.0
        # Bezier: 18 floats (cx1, cy1, cx2, cy2) per segment
        x = time
        n = len(curves)
        # binary search over the bezier segment x positions (stored at index+19*k)
        # simple iterative approximation:
        lo, hi = 0.0, 1.0
        px, py = curves[index + 1], curves[index + 2]
        cx1, cy1 = curves[index + 3], curves[index + 4]
        cx2, cy2 = curves[index + 5], curves[index + 6]
        # bezier x(t) = ...
        for _ in range(8):
            mid = (lo + hi) / 2
            t = mid
            mt = 1 - t
            bx = mt * mt * mt * px + 3 * mt * mt * t * cx1 + 3 * mt * t * t * cx2 + t * t * t
            if bx < x:
                lo = mid
            else:
                hi = mid
        t = (lo + hi) / 2
        mt = 1 - t
        return mt * mt * mt * py + 3 * mt * mt * t * cy1 + 3 * mt * t * t * cy2 + t * t * t * py
