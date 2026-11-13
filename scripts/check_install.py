"""Check a DUGCO Tools install. Run it with the same Python that runs ComfyUI:

    python custom_nodes/DUGCO_Tools/scripts/check_install.py

It only reads; it installs and deletes nothing. Exit code 0 = every required package
is present, 1 = something required is missing. Add --json for machine-readable output.
"""
import importlib
import importlib.metadata as metadata
import json
import sys
from pathlib import Path

PACK = Path(__file__).resolve().parent.parent
CUSTOM_NODES = PACK.parent

# module to import, pip package that provides it, which tools need it
REQUIRED = [
    ("torch", "torch", "every tool (ships with ComfyUI: do not install or upgrade it here)"),
    ("numpy", "numpy", "every tool (ships with ComfyUI: do not install or upgrade it here)"),
    ("OpenEXR", "OpenEXR", "Pass Viewer, Multi-Pass EXR Exporter"),
    ("Imath", "Imath", "Multi-Pass EXR Exporter"),
    ("av", "av", "Pass Viewer"),
    ("cv2", "opencv-python", "Pass Viewer, Track Path To Shot, Plate Relight"),
]
# Any one of these already provides cv2. Installing a second one on top can break the first.
CV2_PACKAGES = ("opencv-python", "opencv-contrib-python", "opencv-python-headless", "opencv-contrib-python-headless")

# Standalone packs that register the same node ids as this pack.
DUPLICATES = ("ComfyUI-DUGco-PassViewer", "ComfyUI-DUGco-FilmFinish", "ComfyUI-DUGco-FrameTools",
              "exr_multi_pass_exporter", "ComfyUI_exr_multi_pass_exporter", "comfyui-plate-relight", "comfyaudit",
              "comfy_workflow_audit", "comfyui_waitingMusak", "ComfyUI-Elevator-Music")


def siblings():
    return [p for p in CUSTOM_NODES.iterdir() if p.is_dir() and p != PACK] if CUSTOM_NODES.is_dir() else []


def main():
    report = {"python": sys.executable, "python_version": sys.version.split()[0], "pack": str(PACK),
              "packages": {}, "missing": [], "notes": []}

    for module, package, used_by in REQUIRED:
        try:
            mod = importlib.import_module(module)
            report["packages"][module] = getattr(mod, "__version__", "installed")
        except Exception as err:                      # ImportError, or a broken binary wheel
            report["packages"][module] = None
            report["missing"].append({"module": module, "package": package, "used_by": used_by, "error": str(err)[:200]})

    have_cv2 = [p for p in CV2_PACKAGES if _installed(p)]
    if len(have_cv2) > 1:
        report["notes"].append(f"More than one OpenCV package is installed ({', '.join(have_cv2)}). If cv2 misbehaves, keep one.")

    in_custom_nodes = CUSTOM_NODES.name.lower() == "custom_nodes"
    if not in_custom_nodes:
        report["notes"].append(f"This pack is not inside a ComfyUI custom_nodes folder (it is in {CUSTOM_NODES}). ComfyUI will not load it from here.")

    dupes = [p.name for p in siblings() if p.name in DUPLICATES and not p.name.endswith(".disabled")]
    if dupes:
        report["notes"].append("Standalone packs that register the same nodes are also installed: " + ", ".join(dupes)
                               + ". Remove or disable them (ask the user first), or the node ids will clash.")

    if in_custom_nodes and not any("videohelpersuite" in p.name.lower() for p in siblings()):
        report["notes"].append("Example workflows only: ComfyUI-VideoHelperSuite is not installed. The video example workflows use it to load and save clips.")

    if "--json" in sys.argv:
        print(json.dumps(report, indent=1))
    else:
        print(f"DUGCO Tools install check\n  Python  {report['python']}  ({report['python_version']})\n  Pack    {report['pack']}\n")
        for module, _, used_by in REQUIRED:
            version = report["packages"][module]
            print(f"  {'OK     ' if version else 'MISSING'}  {module:8s} {version or '':12s} {'' if version else 'needed by ' + used_by}")
        installable = [m["package"] for m in report["missing"] if m["module"] not in ("torch", "numpy")]
        if installable:
            print(f'\nInstall what is missing with this same Python:\n  "{sys.executable}" -m pip install {" ".join(installable)}')
        if any(m["module"] in ("torch", "numpy") for m in report["missing"]):
            print("\ntorch or numpy is missing: this is probably not the Python that runs ComfyUI. Find that one and run this again.")
        for note in report["notes"]:
            print(f"\nNOTE  {note}")
        print("\nResult: " + ("required packages are all present." if not report["missing"] else "something required is missing."))
    return 1 if report["missing"] else 0


def _installed(package):
    try:
        metadata.version(package)
        return True
    except metadata.PackageNotFoundError:
        return False


if __name__ == "__main__":
    sys.exit(main())
