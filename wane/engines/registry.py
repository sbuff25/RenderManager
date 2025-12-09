"""
Wane Engine Registry
====================

Manages registration and lookup of render engines.
"""

import os
from typing import Dict, List, Optional

from wane.engines.base import RenderEngine
from wane.engines.blender import BlenderEngine
from wane.engines.marmoset import MarmosetEngine


class EngineRegistry:
    """
    Registry for render engines.
    
    Manages engine registration, lookup by type, and file type detection.
    """
    
    def __init__(self):
        """Initialize registry with default engines."""
        self.engines: Dict[str, RenderEngine] = {}
        self.register(BlenderEngine())
        self.register(MarmosetEngine())
    
    def register(self, engine: RenderEngine):
        """Register an engine instance."""
        self.engines[engine.engine_type] = engine
    
    def get(self, engine_type: str) -> Optional[RenderEngine]:
        """Get engine by type identifier."""
        return self.engines.get(engine_type)
    
    def get_all(self) -> List[RenderEngine]:
        """Get all registered engines."""
        return list(self.engines.values())
    
    def get_available(self) -> List[RenderEngine]:
        """Get engines that have at least one detected installation."""
        return [e for e in self.engines.values() if e.is_available]
    
    def detect_engine_for_file(self, file_path: str) -> Optional[RenderEngine]:
        """
        Detect the appropriate engine for a file based on extension.
        
        Args:
            file_path: Path to the scene file
            
        Returns:
            RenderEngine if a matching engine is found, None otherwise
        """
        ext = os.path.splitext(file_path)[1].lower()
        for engine in self.engines.values():
            if ext in engine.file_extensions:
                return engine
        return None
    
    def get_all_file_filters(self) -> List[tuple]:
        """
        Get file dialog filters for all supported file types.
        
        Returns:
            List of (description, pattern) tuples for file dialogs
        """
        filters = []
        all_exts = []
        
        for engine in self.engines.values():
            for ext in engine.file_extensions:
                all_exts.append(f"*{ext}")
            filters.extend(engine.get_file_dialog_filter())
        
        # Add "All Supported Files" at the beginning
        filters.insert(0, ("All Supported Files", " ".join(all_exts)))
        # Add "All Files" at the end
        filters.append(("All Files", "*.*"))
        
        return filters
