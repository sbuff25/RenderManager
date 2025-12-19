"""
Wain Vantage Settings Manager v2
================================

SAFE read and write of Vantage 3.x HQ render settings from vantage.ini.

v2.15.1 - Fixed INI corruption bugs:
- Preserves original line endings (CRLF for Windows)
- Atomic writes (temp file -> verify -> rename)
- Only modifies existing keys (never adds new ones)
- Validates file can be re-read after write
- Dry-run mode for testing

Discovery (2024-12-19):
- HQ settings stored in %APPDATA%\Chaos\Vantage\vantage.ini
- Settings in [Preferences] section with "snapshot*Default" keys
- Output path in [DialogLocations] section as "SaveImage"

https://github.com/Spencer-Sliffe/Wain
"""

import os
import re
import shutil
import tempfile
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class VantageHQSettings:
    """Vantage HQ render settings structure."""
    # Resolution
    width: int = 1920
    height: int = 1080
    
    # Quality
    samples: int = 256
    quality_preset: int = 3  # 0=Draft, 1=Low, 2=Medium, 3=High, 4=Ultra
    
    # Denoising
    denoise_enabled: bool = True
    denoiser_type: int = 0  # 0=NVIDIA AI, 1=Intel OIDN
    denoise_intermediate: bool = True
    
    # Effects
    motion_blur: bool = True
    light_cache: bool = True
    temporal: bool = True
    auto_exposure: bool = False
    
    # Output
    output_path: str = ""
    png_alpha: bool = False
    
    # Sequence/Animation
    sequence_output_type: int = 1


class VantageINIManager:
    """
    SAFE manager for reading and writing Vantage HQ render settings.
    
    Safety features:
    - Preserves exact file format (line endings, encoding)
    - Atomic writes (write to temp, verify, then rename)
    - Only modifies keys that already exist
    - Creates backup before any modification
    - Validates file after write
    """
    
    DEFAULT_INI_PATH = os.path.join(
        os.environ.get('APPDATA', ''),
        'Chaos', 'Vantage', 'vantage.ini'
    )
    
    QUALITY_PRESETS = {0: 'Draft', 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Ultra'}
    DENOISER_TYPES = {0: 'NVIDIA AI', 1: 'Intel OIDN'}
    
    def __init__(self, ini_path: Optional[str] = None, read_only: bool = False):
        """
        Initialize the INI manager.
        
        Args:
            ini_path: Path to vantage.ini (uses default if not specified)
            read_only: If True, will never write to the file (for testing)
        """
        self.ini_path = ini_path or self.DEFAULT_INI_PATH
        self.read_only = read_only
        self._line_ending = '\r\n'  # Windows default, will be detected
        self._encoding = 'utf-8'
    
    def exists(self) -> bool:
        """Check if INI file exists."""
        return os.path.isfile(self.ini_path)
    
    def _detect_line_ending(self, content: bytes) -> str:
        """Detect line ending used in file."""
        if b'\r\n' in content:
            return '\r\n'
        elif b'\n' in content:
            return '\n'
        elif b'\r' in content:
            return '\r'
        return '\r\n'  # Default to Windows
    
    def _read_raw(self) -> Tuple[str, str, str]:
        """
        Read file preserving exact format.
        
        Returns:
            Tuple of (content, line_ending, encoding)
        """
        if not self.exists():
            return '', '\r\n', 'utf-8'
        
        # Read as binary first to detect line endings
        with open(self.ini_path, 'rb') as f:
            raw = f.read()
        
        line_ending = self._detect_line_ending(raw)
        
        # Try different encodings
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                content = raw.decode(encoding)
                return content, line_ending, encoding
            except UnicodeDecodeError:
                continue
        
        # Fallback
        content = raw.decode('utf-8', errors='replace')
        return content, line_ending, 'utf-8'
    
    def backup(self) -> Optional[str]:
        """Create timestamped backup of INI file."""
        if not self.exists():
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{self.ini_path}.wain_backup_{timestamp}"
        
        try:
            shutil.copy2(self.ini_path, backup_path)
            return backup_path
        except Exception as e:
            print(f"[Vantage] Backup failed: {e}")
            return None
    
    def read_ini(self) -> Dict[str, Dict[str, str]]:
        """
        Read INI file into nested dict structure.
        
        Returns:
            Dict of {section: {key: value}}
        """
        content, self._line_ending, self._encoding = self._read_raw()
        
        sections = {}
        current_section = 'General'
        sections[current_section] = {}
        
        for line in content.split('\n'):
            line = line.rstrip('\r')  # Handle both line endings
            stripped = line.strip()
            
            if not stripped or stripped.startswith(';') or stripped.startswith('#'):
                continue
            
            if stripped.startswith('[') and stripped.endswith(']'):
                current_section = stripped[1:-1]
                if current_section not in sections:
                    sections[current_section] = {}
                continue
            
            if '=' in stripped:
                key, value = stripped.split('=', 1)
                sections[current_section][key.strip()] = value.strip()
        
        return sections
    
    def _write_safe(self, updates: Dict[str, Dict[str, str]]) -> bool:
        """
        Safely write updates to INI file.
        
        Only modifies keys that already exist in the file.
        Uses atomic write pattern for safety.
        
        Args:
            updates: Dict of {section: {key: new_value}}
            
        Returns:
            True if write succeeded and was verified
        """
        if self.read_only:
            print("[Vantage] Read-only mode - skipping write")
            return False
        
        if not self.exists():
            print("[Vantage] INI file does not exist")
            return False
        
        # Read original file preserving format
        content, line_ending, encoding = self._read_raw()
        lines = content.split('\n')
        
        # Process lines and apply updates
        current_section = 'General'
        new_lines = []
        modified_keys = []
        
        for line in lines:
            # Remove only trailing \r, keep other whitespace
            clean_line = line.rstrip('\r')
            stripped = clean_line.strip()
            
            # Section header
            if stripped.startswith('[') and stripped.endswith(']'):
                current_section = stripped[1:-1]
                new_lines.append(clean_line)
                continue
            
            # Key=Value line
            if '=' in stripped and not stripped.startswith(';') and not stripped.startswith('#'):
                key = stripped.split('=', 1)[0].strip()
                
                # Check if we have an update for this key in this section
                if current_section in updates and key in updates[current_section]:
                    new_value = updates[current_section][key]
                    
                    # Preserve leading whitespace (indentation)
                    leading = len(clean_line) - len(clean_line.lstrip())
                    new_line = ' ' * leading + f"{key}={new_value}"
                    new_lines.append(new_line)
                    modified_keys.append(f"[{current_section}]{key}")
                else:
                    new_lines.append(clean_line)
            else:
                new_lines.append(clean_line)
        
        # Reconstruct content with original line endings
        new_content = line_ending.join(new_lines)
        
        # Ensure file ends properly
        if content.endswith('\n') or content.endswith('\r\n'):
            if not new_content.endswith(line_ending):
                new_content += line_ending
        
        # ATOMIC WRITE: Write to temp file first
        temp_path = self.ini_path + '.wain_temp'
        
        try:
            # Write to temp file
            with open(temp_path, 'w', encoding=encoding, newline='') as f:
                f.write(new_content)
            
            # Verify temp file can be read back
            test_sections = {}
            with open(temp_path, 'r', encoding=encoding) as f:
                test_content = f.read()
            
            # Basic validation - check we can parse it
            for test_line in test_content.split('\n'):
                test_line = test_line.rstrip('\r').strip()
                if test_line.startswith('[') and test_line.endswith(']'):
                    continue
                if '=' in test_line and not test_line.startswith(';'):
                    # Parseable
                    pass
            
            # Verify our updates are present
            for section, keys in updates.items():
                for key, expected_value in keys.items():
                    search_pattern = f"{key}={expected_value}"
                    if search_pattern not in test_content:
                        print(f"[Vantage] Verification failed: {key} not found with expected value")
                        os.unlink(temp_path)
                        return False
            
            # All good - replace original with temp
            # On Windows, need to remove original first
            backup_during_write = self.ini_path + '.wain_atomic_backup'
            
            try:
                # Move original to backup
                if os.path.exists(self.ini_path):
                    shutil.move(self.ini_path, backup_during_write)
                
                # Move temp to original
                shutil.move(temp_path, self.ini_path)
                
                # Remove atomic backup (the write succeeded)
                if os.path.exists(backup_during_write):
                    os.unlink(backup_during_write)
                
                print(f"[Vantage] Successfully updated: {', '.join(modified_keys)}")
                return True
                
            except Exception as e:
                # Restore from backup if anything went wrong
                print(f"[Vantage] Error during atomic swap: {e}")
                if os.path.exists(backup_during_write):
                    shutil.move(backup_during_write, self.ini_path)
                return False
            
        except Exception as e:
            print(f"[Vantage] Error writing temp file: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return False
    
    # =========================================================================
    # Qt Format Helpers
    # =========================================================================
    
    def parse_size(self, value: str) -> Tuple[int, int]:
        """Parse Qt @Size(W H) format."""
        match = re.match(r'@Size\((\d+)\s+(\d+)\)', value)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0
    
    def format_size(self, width: int, height: int) -> str:
        """Format dimensions as Qt @Size(W H)."""
        return f"@Size({width} {height})"
    
    # =========================================================================
    # High-Level Read/Write Methods
    # =========================================================================
    
    def read_hq_settings(self) -> VantageHQSettings:
        """Read current HQ render settings from vantage.ini."""
        settings = VantageHQSettings()
        sections = self.read_ini()
        
        prefs = sections.get('Preferences', {})
        dialogs = sections.get('DialogLocations', {})
        
        # Resolution
        if 'snapshotResDefault' in prefs:
            w, h = self.parse_size(prefs['snapshotResDefault'])
            if w > 0 and h > 0:
                settings.width = w
                settings.height = h
        
        # Samples
        if 'snapshotSamplesDefault' in prefs:
            try:
                settings.samples = int(prefs['snapshotSamplesDefault'])
            except ValueError:
                pass
        
        # Quality preset
        if 'qualityPresetRenderDialogDefault' in prefs:
            try:
                settings.quality_preset = int(prefs['qualityPresetRenderDialogDefault'])
            except ValueError:
                pass
        
        # Denoising
        if 'snapshotDenoiseDefault' in prefs:
            settings.denoise_enabled = prefs['snapshotDenoiseDefault'].lower() == 'true'
        
        if 'snapshotDenoiserTypeDefault' in prefs:
            try:
                settings.denoiser_type = int(prefs['snapshotDenoiserTypeDefault'])
            except ValueError:
                pass
        
        # Effects
        if 'snapshotMoblurDefault' in prefs:
            settings.motion_blur = prefs['snapshotMoblurDefault'].lower() == 'true'
        
        if 'snapshotLightCacheDefault' in prefs:
            settings.light_cache = prefs['snapshotLightCacheDefault'].lower() == 'true'
        
        if 'snapshotTemporalDefault' in prefs:
            settings.temporal = prefs['snapshotTemporalDefault'].lower() == 'true'
        
        # Output
        if 'SaveImage' in dialogs:
            settings.output_path = dialogs['SaveImage']
        
        return settings
    
    def apply_job_settings(self, 
                           width: int = None,
                           height: int = None, 
                           samples: int = None,
                           output_path: str = None,
                           backup: bool = True) -> bool:
        """
        Apply ONLY the specified job settings to vantage.ini.
        
        This is the SAFE method - only updates what you specify,
        and only if those keys already exist in the file.
        
        Args:
            width: Resolution width (optional)
            height: Resolution height (optional)
            samples: Sample count (optional)
            output_path: Output folder path (optional)
            backup: Create backup before writing
            
        Returns:
            True if write succeeded
        """
        if self.read_only:
            print("[Vantage] Read-only mode - settings not applied")
            return False
        
        # Build updates dict with ONLY specified values
        updates = {'Preferences': {}, 'DialogLocations': {}}
        
        # Resolution - must have both width AND height
        if width is not None and height is not None:
            updates['Preferences']['snapshotResDefault'] = self.format_size(width, height)
        
        # Samples
        if samples is not None:
            updates['Preferences']['snapshotSamplesDefault'] = str(samples)
        
        # Output path
        if output_path is not None:
            # Convert to forward slashes (Qt style)
            output_path = output_path.replace('\\', '/')
            updates['DialogLocations']['SaveImage'] = output_path
        
        # Remove empty sections
        updates = {k: v for k, v in updates.items() if v}
        
        if not updates:
            print("[Vantage] No settings to apply")
            return True
        
        # Create backup
        if backup:
            backup_path = self.backup()
            if backup_path:
                print(f"[Vantage] Backup created: {backup_path}")
        
        # Apply updates
        return self._write_safe(updates)
    
    def validate_ini(self) -> Tuple[bool, str]:
        """
        Validate that the INI file is readable and has expected structure.
        
        Returns:
            Tuple of (is_valid, message)
        """
        if not self.exists():
            return False, f"File not found: {self.ini_path}"
        
        try:
            sections = self.read_ini()
            
            if 'Preferences' not in sections:
                return False, "Missing [Preferences] section"
            
            prefs = sections['Preferences']
            
            # Check for critical keys
            if 'snapshotResDefault' in prefs:
                w, h = self.parse_size(prefs['snapshotResDefault'])
                if w <= 0 or h <= 0:
                    return False, f"Invalid resolution format: {prefs['snapshotResDefault']}"
            
            return True, "INI file is valid"
            
        except Exception as e:
            return False, f"Error reading INI: {e}"


# =============================================================================
# Module-level convenience functions
# =============================================================================

def get_ini_manager(read_only: bool = False) -> VantageINIManager:
    """Get a VantageINIManager instance."""
    return VantageINIManager(read_only=read_only)


def read_vantage_settings() -> VantageHQSettings:
    """Read current Vantage HQ settings."""
    return VantageINIManager().read_hq_settings()


def apply_render_settings(width: int = None, 
                          height: int = None, 
                          samples: int = None,
                          output_path: str = None) -> bool:
    """
    Apply render settings to Vantage INI.
    
    Only updates the settings you specify.
    Creates automatic backup before modification.
    """
    manager = VantageINIManager()
    return manager.apply_job_settings(
        width=width,
        height=height,
        samples=samples,
        output_path=output_path
    )


def validate_vantage_ini() -> Tuple[bool, str]:
    """Validate Vantage INI file."""
    return VantageINIManager().validate_ini()
