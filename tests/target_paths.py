"""Hedef IHA'nin dunya koordinatlarindaki gercek rotalari (dokuman Bolum 2)."""

import math


def station_1(t: float, speed: float = 3.0):
    """7m ileri, 5m saga, 7m yukari, 5m sola."""
    x, y, z = 0.0, 0.0, 5.0
    segs = [(7.0, (1, 0, 0)), (5.0, (0, 1, 0)),
            (7.0, (0, 0, 1)), (5.0, (0, -1, 0))]
    for dist, (dx, dy, dz) in segs:
        dur = dist / speed
        if t <= dur:
            x += dx * speed * t; y += dy * speed * t; z += dz * speed * t
            return (x, y, z)
        t -= dur
        x += dx * dist; y += dy * dist; z += dz * dist
    return (x, y, z)


def station_1_duration(speed=3.0):
    return (7 + 5 + 7 + 5) / speed


def station_2(t: float, speed: float = 5.0, length: float = 15.0, amp: float = 2.0):
    """Sabit irtifa, yatay sinus."""
    s = min(speed * t, length)
    return (s, amp * math.sin(2 * math.pi * s / (length / 1.5)), 5.0)


def station_2_duration(speed=5.0, length=15.0):
    return length / speed


def station_3(t: float, speed: float = 6.0, length: float = 15.0, amp: float = 2.0):
    """8m baslangic irtifasi, dusey sinus."""
    s = min(speed * t, length)
    return (s, 0.0, 8.0 + amp * math.sin(2 * math.pi * s / (length / 1.5)))


def station_3_duration(speed=6.0, length=15.0):
    return length / speed


def station_4(t: float, speed: float = 8.0, length: float = 15.0, amp: float = 2.0):
    """3D helisel sinus -> 50m tirmanis -> 25m ileri, 20m irtifaya dalis."""
    t_sine = length / speed
    t_climb = 42.0 / 15.0      # 8m -> 50m, 15 m/s
    t_dive = 3.0

    if t <= t_sine:
        s = speed * t
        ph = 2 * math.pi * s / (length / 1.5)
        return (s, amp * math.sin(ph), 8.0 + amp * math.cos(ph))

    if t <= t_sine + t_climb:
        p = (t - t_sine) / t_climb
        return (length, 0.0, 8.0 + 42.0 * p)

    p = min((t - t_sine - t_climb) / t_dive, 1.0)
    return (length + 25.0 * p, 0.0, 50.0 - 30.0 * p)


def station_4_duration(speed=8.0, length=15.0):
    return length / speed + 42.0 / 15.0 + 3.0


PATHS = {
    "1_linear": (station_1, station_1_duration()),
    "2_sine_x": (station_2, station_2_duration()),
    "3_sine_y": (station_3, station_3_duration()),
    "4_3d":     (station_4, station_4_duration()),
}