import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.fake_target import CameraModel

configs = [
    ("1280x720, 70 FOV (mevcut)", 1280, 720, 70),
    ("1280x720, 50 FOV",          1280, 720, 50),
    ("1280x720, 40 FOV",          1280, 720, 40),
    ("1920x1080, 70 FOV",         1920, 1080, 70),
    ("1920x1080, 50 FOV",         1920, 1080, 50),
]

print(f"{'Konfigurasyon':<28} {'f (px)':>8} {'Max mesafe':>12} {'6m bbox':>10}")
print("-" * 62)
for name, w, h, fov in configs:
    cam = CameraModel(w, h, fov)
    print(f"{name:<28} {cam.focal_px:>8.0f} "
          f"{cam.max_range_for_min_size():>10.2f} m {cam.size_at(6.0):>8.0f} px")

print()
print("Max mesafe: hedefin 64x64 piksel kaplayabilecegi en uzak nokta.")
print("6m bbox:    6 metre takip mesafesinde hedefin kenar uzunlugu.")