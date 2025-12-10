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
    """Registry for render engines."""
    
    def __init__(self):
        self.engines: Dict[str, RenderEngine] = {}
        self.register(BlenderEngine())
        self.register(MarmosetEngine())
    
    def register(self, engine: RenderEngine):
        self.engines[engine.engine_type] = engine
    
    def get(self, engine_type: str) -> Optional[RenderEngine]:
        return self.engines.get(engine_type)
    
    def get_all(self) -> List[RenderEngine]:
        return list(self.engines.values())
    
    def get_available(self) -> List[RenderEngine]:
        return [e for e in self.engines.values() if e.is_available]
    
    def detect_engine_for_file(self, file_path: str) -> Optional[RenderEngine]:
        ext = os.path.splitext(file_path)[1].lower()
        for engine in self.engines.values():
            if ext in engine.file_extensions:
                return engine
        return None
    
    def get_all_file_filters(self) -> List[tuple]:
        filters = []
        all_exts = []
        for engine in self.engines.values():
            for ext in engine.file_extensions:
                all_exts.append(f"*{ext}")
            filters.extend(engine.get_file_dialog_filter())
        filters.insert(0, ("All Supported Files", " ".join(all_exts)))
        filters.append(("All Files", "*.*"))
        return filters
