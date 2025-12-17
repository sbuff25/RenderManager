"""
Vantage Progress Verification Test
===================================

This script tests that Wain can accurately read progress from Vantage.

Run this WHILE a render is in progress in Vantage to verify:
1. Progress window is detected
2. Frame count is parsed correctly (X/Y)
3. Frame progress percentage is correct
4. Total progress percentage is correct
5. Status changes are detected

Usage:
    1. Start a SEQUENCE render in Vantage (at least 5 frames recommended)
    2. Run: python test_progress_accuracy.py
    3. Compare displayed values to what Vantage shows
    4. Press Ctrl+C to stop

The output should match EXACTLY what Vantage displays.
"""

import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 70)
    print("  Vantage Progress Accuracy Test")
    print("=" * 70)
    print()
    
    try:
        from wain.engines.vantage_comm import get_vantage_communicator
        from wain.engines.interface import RenderStatus
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you're running from the wain directory")
        return
    
    # Create communicator with logging
    def log_msg(msg):
        print(f"  LOG: {msg}")
    
    comm = get_vantage_communicator(log_msg)
    
    print("Monitoring Vantage render progress...")
    print("Start a render in Vantage if you haven't already.")
    print("Press Ctrl+C to stop.")
    print()
    print("-" * 70)
    print(f"{'Time':<10} {'Status':<12} {'Total%':<8} {'Frame':<10} {'Frame%':<8}")
    print("-" * 70)
    
    start_time = time.time()
    last_line = ""
    
    try:
        while True:
            # Read progress
            progress = comm._read_progress_from_ui()
            
            # Format output line
            elapsed = time.time() - start_time
            time_str = f"{elapsed:.1f}s"
            
            frame_str = f"{progress.current_frame}/{progress.total_frames}"
            
            line = (
                f"{time_str:<10} "
                f"{progress.status.value:<12} "
                f"{progress.total_progress:>6.1f}% "
                f"{frame_str:<10} "
                f"{progress.frame_progress:>6.1f}%"
            )
            
            # Only print if changed
            if line != last_line:
                print(line)
                last_line = line
            
            # Check for completion
            if progress.status in [RenderStatus.COMPLETE, RenderStatus.CANCELLED]:
                print()
                print("-" * 70)
                print(f"  Render {progress.status.value}!")
                print("-" * 70)
                break
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print()
        print()
        print("Stopped by user.")
    
    print()
    print("=" * 70)
    print("  Verification Checklist:")
    print("=" * 70)
    print()
    print("  [ ] Frame count matches Vantage display?")
    print("  [ ] Frame % matches Vantage display?")
    print("  [ ] Total % matches Vantage display?")
    print("  [ ] Status changes are detected correctly?")
    print()
    print("  If any don't match, we need to adjust the parsing logic.")
    print("=" * 70)


if __name__ == "__main__":
    main()
