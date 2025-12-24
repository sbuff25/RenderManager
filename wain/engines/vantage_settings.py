"""
Wain Vantage Settings Manager v2.15.38
======================================

SAFE settings management for Chaos Vantage HQ Render.

This module handles reading/writing Vantage's vantage.ini file with
extreme caution to prevent crashes and corruption.

Safety Features:
- Automatic backup before ANY write
- Validation of all values before writing
- Preserves exact INI format (Qt serialization)
- DRY_RUN mode for testing
- Restore capability

INI Location: %APPDATA%/Chaos Group/Vantage/vantage.ini

Key Settings (in [Preferences] section):
- snapshotResDefault=@Size(width height)  # Qt QSize format!
- snapshotSamplesDefault=100               # Integer
- snapshotDenoiseDefault=true              # Boolean
- snapshotDenoiserTypeDefault=0            # 0=NVIDIA OptiX, 1=Intel OIDN, 2=Off

Output Path (in [DialogLocations] section):
- SaveImage=H:/path/to/output/prefix       # Full path including filename prefix

https://github.com/Spencer-Sliffe/Wain
"""

import os
import re
import shutil
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple


# =============================================================================
# CONFIGURATION
# =============================================================================

# Set to True to test without actually writing files
DRY_RUN = False

# Validation limits (hardware safety)
MIN_RESOLUTION = 64
MAX_RESOLUTION = 16384  # 16K is reasonable max
MIN_SAMPLES = 1
MAX_SAMPLES = 65536

# Denoiser type mapping
DENOISER_TYPES = {
    "nvidia": 0,      # NVIDIA OptiX AI
    "oidn": 1,        # Intel Open Image Denoise  
    "off": 2,         # No denoising
}

DENOISER_NAMES = {v: k for k, v in DENOISER_TYPES.items()}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VantageHQSettings:
    """HQ Render settings that can be configured."""
    width: int = 1920
    height: int = 1080
    samples: int = 100
    denoise_enabled: bool = True
    denoiser_type: int = 0  # 0=NVIDIA, 1=OIDN, 2=Off
    output_path: str = ""  # Full output path including folder and prefix
    
    def validate(self) -> Tuple[bool, str]:
        """Validate settings are within safe ranges."""
        if not (MIN_RESOLUTION <= self.width <= MAX_RESOLUTION):
            return False, f"Width {self.width} outside safe range ({MIN_RESOLUTION}-{MAX_RESOLUTION})"
        if not (MIN_RESOLUTION <= self.height <= MAX_RESOLUTION):
            return False, f"Height {self.height} outside safe range ({MIN_RESOLUTION}-{MAX_RESOLUTION})"
        if not (MIN_SAMPLES <= self.samples <= MAX_SAMPLES):
            return False, f"Samples {self.samples} outside safe range ({MIN_SAMPLES}-{MAX_SAMPLES})"
        if self.denoiser_type not in [0, 1, 2]:
            return False, f"Invalid denoiser type {self.denoiser_type} (must be 0, 1, or 2)"
        return True, "OK"
    
    def __str__(self):
        denoiser_name = DENOISER_NAMES.get(self.denoiser_type, "unknown")
        output_str = f", Output: {self.output_path}" if self.output_path else ""
        return f"Resolution: {self.width}x{self.height}, Samples: {self.samples}, Denoiser: {denoiser_name}{output_str}"


# =============================================================================
# INI MANAGER
# =============================================================================

class VantageINIManager:
    """
    Safe manager for Vantage's vantage.ini file.
    
    IMPORTANT: This class preserves the exact INI format including Qt serialization.
    Vantage uses Qt's QSettings which has special formats like @Size(w h).
    """
    
    def __init__(self, log_func=None):
        self.log = log_func or print
        self.ini_path = self._find_ini_path()
        self.backup_path = None
    
    def _find_ini_path(self) -> Optional[str]:
        """Find the vantage.ini file."""
        appdata = os.environ.get('APPDATA', '')
        if not appdata:
            return None
        
        # Standard location
        ini_path = os.path.join(appdata, 'Chaos Group', 'Vantage', 'vantage.ini')
        if os.path.exists(ini_path):
            return ini_path
        
        # Alternative location
        alt_path = os.path.join(appdata, 'Chaos', 'Vantage', 'vantage.ini')
        if os.path.exists(alt_path):
            return alt_path
        
        return None
    
    def exists(self) -> bool:
        """Check if INI file exists."""
        return self.ini_path is not None and os.path.exists(self.ini_path)
    
    def create_backup(self) -> Optional[str]:
        """Create a timestamped backup of the INI file."""
        if not self.exists():
            self.log("Cannot backup: INI file not found")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.dirname(self.ini_path)
        backup_name = f"vantage_backup_{timestamp}.ini"
        backup_path = os.path.join(backup_dir, backup_name)
        
        try:
            shutil.copy2(self.ini_path, backup_path)
            self.backup_path = backup_path
            self.log(f"Backup created: {backup_name}")
            return backup_path
        except Exception as e:
            self.log(f"Backup failed: {e}")
            return None
    
    def restore_backup(self, backup_path: str = None) -> bool:
        """Restore from a backup file."""
        path = backup_path or self.backup_path
        if not path or not os.path.exists(path):
            self.log("No backup to restore")
            return False
        
        try:
            shutil.copy2(path, self.ini_path)
            self.log(f"Restored from backup")
            return True
        except Exception as e:
            self.log(f"Restore failed: {e}")
            return False
    
    def read_settings(self) -> Optional[VantageHQSettings]:
        """Read current HQ settings from INI file."""
        if not self.exists():
            self.log("INI file not found")
            return None
        
        try:
            with open(self.ini_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            settings = VantageHQSettings()
            
            # Parse resolution: @Size(width height)
            res_match = re.search(r'snapshotResDefault=@Size\((\d+)\s+(\d+)\)', content)
            if res_match:
                settings.width = int(res_match.group(1))
                settings.height = int(res_match.group(2))
            
            # Parse samples
            samples_match = re.search(r'snapshotSamplesDefault=(\d+)', content)
            if samples_match:
                settings.samples = int(samples_match.group(1))
            
            # Parse denoise enabled
            denoise_match = re.search(r'snapshotDenoiseDefault=(true|false)', content)
            if denoise_match:
                settings.denoise_enabled = denoise_match.group(1) == 'true'
            
            # Parse denoiser type
            denoiser_match = re.search(r'snapshotDenoiserTypeDefault=(\d+)', content)
            if denoiser_match:
                settings.denoiser_type = int(denoiser_match.group(1))
            
            # Parse output path from [DialogLocations] section
            # SaveImage=H:/path/to/output/prefix
            output_match = re.search(r'^SaveImage=(.+)$', content, re.MULTILINE)
            if output_match:
                settings.output_path = output_match.group(1).strip()
            
            return settings
            
        except Exception as e:
            self.log(f"Error reading INI: {e}")
            return None
    
    def write_settings(self, settings: VantageHQSettings) -> bool:
        """
        Write HQ settings to INI file.
        
        SAFETY: Creates backup first, validates all values, preserves format.
        """
        # Validate settings
        valid, msg = settings.validate()
        if not valid:
            self.log(f"REJECTED: {msg}")
            return False
        
        if not self.exists():
            self.log("INI file not found")
            return False
        
        # Create backup BEFORE any modification
        if not DRY_RUN:
            backup = self.create_backup()
            if not backup:
                self.log("ABORTED: Could not create backup")
                return False
        
        try:
            # Read current content
            with open(self.ini_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content  # Keep copy for comparison
            
            # Update resolution (preserve @Size format exactly)
            # Use \g<1> instead of \1 to avoid ambiguity with following digits
            content = re.sub(
                r'(snapshotResDefault=)@Size\(\d+\s+\d+\)',
                f'\\g<1>@Size({settings.width} {settings.height})',
                content
            )
            
            # Update samples
            content = re.sub(
                r'(snapshotSamplesDefault=)\d+',
                f'\\g<1>{settings.samples}',
                content
            )
            
            # Update denoise enabled
            denoise_str = 'true' if settings.denoise_enabled else 'false'
            content = re.sub(
                r'(snapshotDenoiseDefault=)(true|false)',
                f'\\g<1>{denoise_str}',
                content
            )
            
            # Update denoiser type
            content = re.sub(
                r'(snapshotDenoiserTypeDefault=)\d+',
                f'\\g<1>{settings.denoiser_type}',
                content
            )
            
            # Update output path in [DialogLocations] section if provided
            if settings.output_path:
                # Normalize path separators to forward slashes (Vantage uses forward slashes)
                output_path = settings.output_path.replace('\\', '/')
                
                # Simple line-based replacement for SaveImage
                if re.search(r'^SaveImage=', content, re.MULTILINE):
                    # Replace existing SaveImage line
                    content = re.sub(
                        r'^SaveImage=.*$',
                        f'SaveImage={output_path}',
                        content,
                        flags=re.MULTILINE
                    )
                    self.log(f"Updated SaveImage to: {output_path}")
                else:
                    # Add SaveImage to [DialogLocations] section if it doesn't exist
                    if '[DialogLocations]' in content:
                        content = re.sub(
                            r'(\[DialogLocations\]\r?\n)',
                            f'\\g<1>SaveImage={output_path}\n',
                            content
                        )
                        self.log(f"Added SaveImage: {output_path}")
                    else:
                        # Create [DialogLocations] section if it doesn't exist
                        content += f'\n[DialogLocations]\nSaveImage={output_path}\n'
                        self.log(f"Created [DialogLocations] with SaveImage: {output_path}")
            
            # Log what changed
            if DRY_RUN:
                self.log("=== DRY RUN MODE - NO FILES MODIFIED ===")
            
            self.log(f"Settings to apply: {settings}")
            
            # Show diff
            if original_content != content:
                self.log("Changes detected:")
                for old_line, new_line in zip(original_content.split('\n'), content.split('\n')):
                    if old_line != new_line:
                        self.log(f"  - {old_line.strip()}")
                        self.log(f"  + {new_line.strip()}")
            else:
                self.log("No changes needed")
                return True
            
            # Write file
            if DRY_RUN:
                self.log("=== DRY RUN - Would write above changes ===")
                return True
            
            with open(self.ini_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.log("Settings written successfully")
            return True
            
        except Exception as e:
            self.log(f"Error writing INI: {e}")
            # Try to restore backup
            if self.backup_path and not DRY_RUN:
                self.log("Attempting to restore backup...")
                self.restore_backup()
            return False


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def read_vantage_settings(log_func=None) -> Optional[VantageHQSettings]:
    """Read current Vantage HQ settings."""
    manager = VantageINIManager(log_func)
    return manager.read_settings()


def apply_vantage_settings(
    width: int = None,
    height: int = None,
    samples: int = None,
    denoiser: str = None,
    output_path: str = None,
    log_func=None
) -> bool:
    """
    Apply HQ render settings to Vantage.
    
    Only modifies settings that are explicitly provided.
    Creates backup before any modification.
    
    Args:
        width: Render width (64-16384)
        height: Render height (64-16384)
        samples: Render samples (1-65536)
        denoiser: "nvidia", "oidn", or "off"
        output_path: Output FOLDER path (not filename prefix - that's set in Vantage UI)
        log_func: Optional logging function
    
    Returns:
        True if successful, False otherwise
    """
    manager = VantageINIManager(log_func)
    
    # Read current settings
    current = manager.read_settings()
    if not current:
        return False
    
    # Apply changes
    if width is not None:
        current.width = width
    if height is not None:
        current.height = height
    if samples is not None:
        current.samples = samples
    if denoiser is not None:
        denoiser_lower = denoiser.lower()
        if denoiser_lower in DENOISER_TYPES:
            current.denoiser_type = DENOISER_TYPES[denoiser_lower]
            current.denoise_enabled = denoiser_lower != "off"
        else:
            if log_func:
                log_func(f"Unknown denoiser: {denoiser}")
            return False
    if output_path is not None:
        current.output_path = output_path
    
    # Write settings
    return manager.write_settings(current)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    """Test the settings manager."""
    print("=" * 60)
    print("Vantage Settings Manager Test")
    print("=" * 60)
    
    # Enable dry run for safety
    DRY_RUN = True
    print(f"\nDRY_RUN = {DRY_RUN}")
    
    manager = VantageINIManager(print)
    
    print(f"\nINI Path: {manager.ini_path}")
    print(f"Exists: {manager.exists()}")
    
    if manager.exists():
        print("\n--- Current Settings ---")
        settings = manager.read_settings()
        if settings:
            print(f"  {settings}")
            
            print("\n--- Test Write (DRY RUN) ---")
            settings.width = 3840
            settings.height = 2160
            settings.samples = 500
            settings.denoiser_type = 0  # NVIDIA
            manager.write_settings(settings)
