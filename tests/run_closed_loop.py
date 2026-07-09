import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.sim_loop import run_closed_loop, MAX_CLIMB_ACCEL, MAX_FWD_ACCEL, DEFAULT_DRAG
from tests.target_paths import PATHS
from tests.fake_target import CameraModel
from src.pid_controller import TrackingController

CAMERAS = {
    "1280x720 / 70 FOV": CameraModel(1280, 720, 70),
    "1280x720 / 40 FOV": CameraModel(1280, 720, 40),
    "1920x1080 / 50 FOV": CameraModel(1920, 1080, 50),
}

DESIRED_DIST = 4.0

print(f"Takipci dinamigi: max ileri ivme {MAX_FWD_ACCEL:.1f} m/s^2, "
      f"max tirmanis ivmesi {MAX_CLIMB_ACCEL:.1f} m/s^2, drag {DEFAULT_DRAG}")
print(f"  -> denge ileri hizi ~{MAX_FWD_ACCEL/DEFAULT_DRAG:.0f} m/s, "
      f"denge tirmanis hizi ~{MAX_CLIMB_ACCEL/DEFAULT_DRAG:.0f} m/s")
print()

for cam_name, cam in CAMERAS.items():
    print("=" * 78)
    print(f"{cam_name}   max menzil: {cam.max_range_for_min_size():.2f} m   "
          f"hedef mesafe: {DESIRED_DIST} m")
    print("=" * 78)

    for name, (path, dur) in PATHS.items():
        ctrl = TrackingController(cam=cam, desired_distance_m=DESIRED_DIST)
        r = run_closed_loop(name, path, dur, cam=cam,
                            controller=ctrl, initial_dist=DESIRED_DIST)
        s = r.summary()
        durum = "BASARILI" if s["manevra_basarili"] else "BASARISIZ"
        print(f"  {name:<10} {durum:<10} %{s['basari_orani']*100:5.1f}  "
              f"mesafe ort/max: {s['ort_mesafe_m']:.1f}/{s['max_mesafe_m']:.1f} m  "
              f"min bbox: {s['min_bbox_px']:.0f}px  "
              f"doygun: {s['doygun_frame']}  kayip: {s['kayip_frame']}")
    print()