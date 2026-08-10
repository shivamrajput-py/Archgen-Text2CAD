
import FreeCAD
import sys
import os

print("===DEBUG_PATHS_START===")
print(f"User AppData: {FreeCAD.getUserAppDataDir()}")
print(f"Home Path: {FreeCAD.getHomePath()}")

# Check where it finds the workbench
try:
    import InitGui
    print(f"InitGui found at: {os.path.dirname(InitGui.__file__)}")
except ImportError:
    print("InitGui not found in path")

# List all 'Mod' directories in sys.path
print("\nScanning sys.path for 'Mod' or 'Workbench' locations:")
for p in sys.path:
    if "Mod" in p or "Workbench" in p:
        print(f" - {p}")

print("===DEBUG_PATHS_END===")
