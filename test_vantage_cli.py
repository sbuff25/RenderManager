"""
Vantage CLI Test Script
=======================

Run this script to test what command-line options are available
in your Chaos Vantage installation.

Usage:
    python test_vantage_cli.py

This will:
1. Find your Vantage installation
2. Run vantage_console.exe -help to see available options
3. Run vantage_console.exe -version to get version info
4. Report what rendering options may be available
"""

import os
import sys
import subprocess
import re

# Search paths for vantage_console.exe
SEARCH_PATHS = [
    r"C:\Program Files\Chaos\Vantage\vantage_console.exe",
    r"C:\Program Files\Chaos Group\Vantage\vantage_console.exe",
    r"C:\Program Files\Chaos\Vantage 3\vantage_console.exe",
    r"C:\Program Files\Chaos\Vantage 2\vantage_console.exe",
]


def find_vantage():
    """Find vantage_console.exe on the system."""
    for path in SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    
    # Also try to find via PATH
    try:
        result = subprocess.run(
            ["where", "vantage_console.exe"],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            path = result.stdout.decode().strip().split('\n')[0]
            if os.path.isfile(path):
                return path
    except:
        pass
    
    return None


def run_command(exe_path, args, timeout=30):
    """Run a command and return stdout + stderr."""
    try:
        startupinfo = None
        creation_flags = 0
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        result = subprocess.run(
            [exe_path] + args,
            capture_output=True,
            timeout=timeout,
            startupinfo=startupinfo,
            creationflags=creation_flags
        )
        
        stdout = result.stdout.decode('utf-8', errors='replace')
        stderr = result.stderr.decode('utf-8', errors='replace')
        
        return {
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output": stdout + stderr
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}


def main():
    print("=" * 60)
    print("  Chaos Vantage CLI Capability Test")
    print("=" * 60)
    print()
    
    # Find Vantage
    vantage_exe = find_vantage()
    
    if not vantage_exe:
        print("[ERROR] Could not find vantage_console.exe")
        print()
        print("Searched locations:")
        for path in SEARCH_PATHS:
            print(f"  - {path}")
        print()
        print("Please ensure Chaos Vantage is installed, or add a custom path.")
        return
    
    print(f"[OK] Found Vantage: {vantage_exe}")
    print()
    
    # Test -version
    print("-" * 40)
    print("Testing: vantage_console.exe -version")
    print("-" * 40)
    
    result = run_command(vantage_exe, ["-version"])
    if "error" in result:
        print(f"[ERROR] {result['error']}")
    else:
        print(f"Return code: {result['returncode']}")
        print(f"Output:\n{result['output']}")
        
        # Try to extract version
        version_match = re.search(r'(\d+\.\d+\.\d+)', result['output'])
        if version_match:
            print(f"\n[VERSION] {version_match.group(1)}")
    
    print()
    
    # Test -help
    print("-" * 40)
    print("Testing: vantage_console.exe -help")
    print("-" * 40)
    
    result = run_command(vantage_exe, ["-help"])
    if "error" in result:
        print(f"[ERROR] {result['error']}")
    else:
        print(f"Return code: {result['returncode']}")
        print(f"Output:\n{result['output']}")
    
    print()
    
    # Also try -h (short form)
    print("-" * 40)
    print("Testing: vantage_console.exe -h")
    print("-" * 40)
    
    result = run_command(vantage_exe, ["-h"])
    if "error" in result:
        print(f"[ERROR] {result['error']}")
    else:
        print(f"Return code: {result['returncode']}")
        output = result['output']
        print(f"Output:\n{output}")
        
        # Analyze available options
        print()
        print("-" * 40)
        print("Detected Command-Line Options:")
        print("-" * 40)
        
        # Look for option patterns
        options = set()
        
        # Pattern: -option or --option
        option_matches = re.findall(r'-{1,2}(\w+)', output)
        options.update(option_matches)
        
        # Check for specific rendering options we need
        critical_options = {
            'sceneFile': 'Load scene file',
            'outputFile': 'Set output file path',
            'output': 'Set output path',
            'camera': 'Select camera',
            'resolution': 'Set resolution',
            'width': 'Set width',
            'height': 'Set height',
            'samples': 'Set samples',
            'frame': 'Set frame number',
            'animation': 'Render animation',
            'startFrame': 'Animation start',
            'endFrame': 'Animation end',
            'render': 'Start rendering',
            'batch': 'Batch rendering',
            'quiet': 'Quiet mode',
        }
        
        print("\nKey options for rendering:")
        for opt, desc in critical_options.items():
            found = any(opt.lower() in o.lower() for o in options)
            status = "[FOUND]" if found else "[NOT FOUND]"
            print(f"  {status} -{opt}: {desc}")
        
        print("\nAll detected options:")
        for opt in sorted(options):
            print(f"  -{opt}")
    
    print()
    print("=" * 60)
    print("Test complete!")
    print()
    print("If rendering options like -outputFile are missing, Wain may need")
    print("to use an alternative approach (e.g., launching Vantage GUI with")
    print("pre-configured .vantage files).")
    print("=" * 60)


if __name__ == "__main__":
    main()
