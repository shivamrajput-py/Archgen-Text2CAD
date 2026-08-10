import sys
import os
import subprocess
import importlib.util

def print_status(component, success, message=""):
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    mark = "✅" if success else "❌"
    print(f"{mark} {component}: {color}{'OK' if success else 'FAILED'}{reset} {message}")

def check_import(module_name):
    try:
        importlib.import_module(module_name)
        print_status(f"Import {module_name}", True)
        return True
    except ImportError as e:
        print_status(f"Import {module_name}", False, str(e))
        return False

def check_file(filepath):
    exists = os.path.exists(filepath)
    print_status(f"File {filepath}", exists)
    return exists

def main():
    print("🔍 Starting System Diagnostics...\n")
    
    # 1. Check Python Version
    print(f"Python Version: {sys.version.split()[0]}")
    
    # 2. Check Dependencies
    print("\n📦 Checking Dependencies:")
    dependencies = [
        "fastapi", "uvicorn", "pydantic", "langchain_openai", 
        "langchain_core", "sentence_transformers", "numpy"
    ]
    all_deps_ok = all(check_import(dep) for dep in dependencies)
    
    # 3. Check Files
    print("\n📂 Checking File Structure:")
    files = ["app.py", "main.py", "dataset.json", "run_freecad.bat"]
    all_files_ok = all(check_file(f) for f in files)
    
    # 4. Check FreeCAD Connection
    print("\n🛠️ Checking FreeCAD Integration:")
    if os.path.exists("run_freecad.bat"):
        # Create a simple test script
        test_script = "test_script.py"
        with open(test_script, "w") as f:
            f.write("import FreeCAD\nprint('FreeCAD_OK')")
            
        try:
            result = subprocess.run(
                [".\\run_freecad.bat", test_script], 
                capture_output=True, 
                text=True, 
                shell=True
            )
            
            if "FreeCAD_OK" in result.stdout:
                print_status("FreeCAD Execution", True, "Successfully ran a test script")
            else:
                print_status("FreeCAD Execution", False, "Could not verify FreeCAD output")
                print(f"   Stdout: {result.stdout.strip()}")
                print(f"   Stderr: {result.stderr.strip()}")
                print("   👉 Check if FreeCAD is installed in a standard location (C:\\Program Files\\FreeCAD...)")
                print("   👉 Or edit run_freecad.bat to point to your installation.")
        except Exception as e:
            print_status("FreeCAD Execution", False, str(e))
        finally:
            if os.path.exists(test_script):
                os.remove(test_script)
    else:
        print_status("FreeCAD Execution", False, "Skipped (run_freecad.bat missing)")

    print("\n" + "="*50)
    if all_deps_ok and all_files_ok:
        print("\033[92m🎉 System appears ready! You can run the server with:\033[0m")
        print("python main.py")
    else:
        print("\033[91m⚠️ Some checks failed. Please fix the errors above.\033[0m")

if __name__ == "__main__":
    main()
