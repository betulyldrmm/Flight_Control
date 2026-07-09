"""
Manevra istasyonlarini farkli kamera konfigurasyonlariyla kosturur.

Amac: sartnamedeki 64x64 piksel tespit kriterinin hangi kamera
ayarlariyla saglanabildigini olcmek.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metrics import ManeuverEvaluator
from tests.fake_target import STATIONS, CameraModel

CAMERAS = {
    "1280x720 / 70 FOV (mevcut)": CameraModel(1280, 720, 70),
    "1280x720 / 50 FOV":          CameraModel(1280, 720, 50),
    "1280x720 / 40 FOV":          CameraModel(1280, 720, 40),
    "1920x1080 / 50 FOV":         CameraModel(1920, 1080, 50),
}

FOLLOW_DIST = 6.0


def main():
    for cam_name, cam in CAMERAS.items():
        print("=" * 62)
        print(f"{cam_name}   (takip mesafesi {FOLLOW_DIST} m)")
        print(f"  {FOLLOW_DIST}m'de bbox kenari: {cam.size_at(FOLLOW_DIST):.0f} px"
              f"  |  max menzil: {cam.max_range_for_min_size():.2f} m")
        print("=" * 62)

        for name, station in STATIONS.items():
            ev = ManeuverEvaluator(name)
            for f in station(cam=cam, follow_dist=FOLLOW_DIST):
                ev.add(f.tracked, f.reference, f.t)
            s = ev.summary()
            durum = "BASARILI" if s["manevra_basarili"] else "BASARISIZ"
            print(f"  {name:<12} {durum:<10} "
                  f"%{s['basari_orani'] * 100:5.1f}  IoU={s['ortalama_iou']:.3f}")
        print()


if __name__ == "__main__":
    main()