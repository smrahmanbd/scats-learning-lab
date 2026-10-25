"""Run every Foundation, Advanced and Mastery script in order (~10 minutes).

    python run_all.py              # everything
    python run_all.py foundation   # one level
"""
import subprocess
import sys
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = {
    "foundation": ["01_ds_lab.py", "02_calibrate_h.py", "03_fixed_vs_scats.py"],
    "advanced": ["01_corridor_scats.py", "02_ablation_study.py"],
    "mastery": ["01_cv_ds_estimation.py", "02_rl_split_selection.py", "03_maxpressure_hybrid.py",
                "04_detector_faults.py", "05_spat_prediction.py"],
}

if __name__ == "__main__":
    chosen = sys.argv[1:] or list(LEVELS)
    for level in chosen:
        for script in LEVELS[level]:
            t = time.time()
            print(f"\n=== {level}/{script} ===", flush=True)
            subprocess.run([sys.executable, os.path.join(HERE, level, script)], check=True)
            print(f"--- done in {time.time() - t:.0f}s", flush=True)
