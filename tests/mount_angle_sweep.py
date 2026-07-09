import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.sim_loop import run_closed_loop
from tests.target_paths import PATHS
from tests.fake_target import CameraModel
from src.pid_controller import TrackingController

CAMERAS = {
    "1280x720/70": CameraModel(1280, 720, 70),
    "1280x720/40": CameraModel(1280, 720, 40),
    "1920x1080/50": CameraModel(1920, 1080, 50),
}
MOUNTS = [0, 5, 10, 15, 20]
DESIRED = 4.0

for cam_name, cam in CAMERAS.items():
    vfov = math.degrees(math.atan(cam.h / 2 / cam.focal_px))
    print(f"\n{cam_name}  (dikey yari acı {vfov:.1f} derece)")
    print(f"{'mount':>6} | " + " | ".join(f"{n:>9}" for n in PATHS))
    print("-" * 56)

    for m in MOUNTS:
        row = []
        for name, (path, dur) in PATHS.items():
            ctrl = TrackingController(cam=cam, desired_distance_m=DESIRED)
            r = run_closed_loop(name, path, dur, cam=cam, controller=ctrl,
                                initial_dist=DESIRED, camera_mount_deg=m)
            s = r.summary()
            row.append(f"{s['basari_orani']*100:8.1f}%")
        print(f"{m:>4}deg | " + " | ".join(row))