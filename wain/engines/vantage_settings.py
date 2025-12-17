"""
Vantage Settings Schema
=======================

Defines all configurable settings for Chaos Vantage renders.
These settings can be modified in Wain and will be applied
to Vantage before rendering starts.

Settings are organized by category and include validation rules.
"""

from wain.engines.interface import (
    EngineSettingsSchema,
    SettingDefinition,
    SettingType,
    SettingCategory,
)


def get_vantage_settings_schema() -> EngineSettingsSchema:
    """
    Return the complete settings schema for Chaos Vantage.
    
    These settings mirror what's available in Vantage's
    High Quality Render panel.
    """
    return EngineSettingsSchema(
        engine_type="vantage",
        engine_name="Chaos Vantage",
        version="1.0.0",
        settings=[
            # =================================================================
            # OUTPUT SETTINGS
            # =================================================================
            SettingDefinition(
                id="output_path",
                name="Output Path",
                type=SettingType.PATH,
                category=SettingCategory.OUTPUT,
                default="",
                description="Where to save rendered images",
                required=True,
            ),
            SettingDefinition(
                id="output_format",
                name="Output Format",
                type=SettingType.CHOICE,
                category=SettingCategory.OUTPUT,
                default="png",
                description="Image file format",
                choices=[
                    {"id": "png", "name": "PNG"},
                    {"id": "jpg", "name": "JPEG"},
                    {"id": "exr", "name": "OpenEXR"},
                    {"id": "tga", "name": "TGA"},
                ],
            ),
            SettingDefinition(
                id="resolution_width",
                name="Width",
                type=SettingType.INTEGER,
                category=SettingCategory.OUTPUT,
                default=1920,
                description="Render width in pixels",
                min_value=1,
                max_value=16384,
            ),
            SettingDefinition(
                id="resolution_height",
                name="Height",
                type=SettingType.INTEGER,
                category=SettingCategory.OUTPUT,
                default=1080,
                description="Render height in pixels",
                min_value=1,
                max_value=16384,
            ),
            
            # =================================================================
            # QUALITY SETTINGS
            # =================================================================
            SettingDefinition(
                id="quality_preset",
                name="Quality Preset",
                type=SettingType.CHOICE,
                category=SettingCategory.QUALITY,
                default="high",
                description="Overall quality preset",
                choices=[
                    {"id": "draft", "name": "Draft"},
                    {"id": "low", "name": "Low"},
                    {"id": "medium", "name": "Medium"},
                    {"id": "high", "name": "High"},
                    {"id": "ultra", "name": "Ultra"},
                    {"id": "custom", "name": "Custom"},
                ],
            ),
            SettingDefinition(
                id="samples",
                name="Samples",
                type=SettingType.INTEGER,
                category=SettingCategory.QUALITY,
                default=256,
                description="Number of render samples (higher = better quality, slower)",
                min_value=1,
                max_value=65536,
                step=64,
                depends_on="quality_preset",  # Show if preset is "custom"
            ),
            SettingDefinition(
                id="denoiser",
                name="Denoiser",
                type=SettingType.CHOICE,
                category=SettingCategory.QUALITY,
                default="nvidia",
                description="Denoising method",
                choices=[
                    {"id": "off", "name": "Off"},
                    {"id": "native", "name": "Native"},
                    {"id": "nvidia", "name": "NVIDIA AI"},
                    {"id": "oidn", "name": "Intel OIDN"},
                ],
            ),
            SettingDefinition(
                id="motion_blur",
                name="Motion Blur",
                type=SettingType.BOOLEAN,
                category=SettingCategory.QUALITY,
                default=True,
                description="Enable motion blur for animations",
            ),
            SettingDefinition(
                id="motion_blur_samples",
                name="Motion Blur Samples",
                type=SettingType.INTEGER,
                category=SettingCategory.QUALITY,
                default=8,
                description="Number of motion blur samples",
                min_value=1,
                max_value=64,
                depends_on="motion_blur",
            ),
            
            # =================================================================
            # CAMERA SETTINGS
            # =================================================================
            SettingDefinition(
                id="camera",
                name="Camera",
                type=SettingType.CHOICE,
                category=SettingCategory.CAMERA,
                default="",
                description="Camera to render from",
                choices=[],  # Populated dynamically from scene
            ),
            SettingDefinition(
                id="camera_type",
                name="Camera Type",
                type=SettingType.CHOICE,
                category=SettingCategory.CAMERA,
                default="perspective",
                description="Camera projection type",
                choices=[
                    {"id": "perspective", "name": "Perspective"},
                    {"id": "spherical", "name": "Spherical (360°)"},
                    {"id": "cube_6x1", "name": "Cube 6x1"},
                    {"id": "stereo_spherical", "name": "Stereo Spherical"},
                    {"id": "stereo_cube", "name": "Stereo Cube 6x1"},
                ],
            ),
            SettingDefinition(
                id="depth_of_field",
                name="Depth of Field",
                type=SettingType.BOOLEAN,
                category=SettingCategory.CAMERA,
                default=True,
                description="Enable depth of field effect",
            ),
            SettingDefinition(
                id="exposure",
                name="Exposure",
                type=SettingType.FLOAT,
                category=SettingCategory.CAMERA,
                default=0.0,
                description="Exposure adjustment (EV)",
                min_value=-10.0,
                max_value=10.0,
                step=0.1,
            ),
            
            # =================================================================
            # ANIMATION SETTINGS
            # =================================================================
            SettingDefinition(
                id="frame_start",
                name="Start Frame",
                type=SettingType.INTEGER,
                category=SettingCategory.ANIMATION,
                default=1,
                description="First frame to render",
                min_value=0,
            ),
            SettingDefinition(
                id="frame_end",
                name="End Frame",
                type=SettingType.INTEGER,
                category=SettingCategory.ANIMATION,
                default=1,
                description="Last frame to render",
                min_value=0,
            ),
            SettingDefinition(
                id="frame_step",
                name="Frame Step",
                type=SettingType.INTEGER,
                category=SettingCategory.ANIMATION,
                default=1,
                description="Render every Nth frame",
                min_value=1,
                max_value=100,
            ),
            
            # =================================================================
            # LIGHTING SETTINGS
            # =================================================================
            SettingDefinition(
                id="gi_enabled",
                name="Global Illumination",
                type=SettingType.BOOLEAN,
                category=SettingCategory.LIGHTING,
                default=True,
                description="Enable global illumination",
            ),
            SettingDefinition(
                id="gi_bounces",
                name="GI Bounces",
                type=SettingType.INTEGER,
                category=SettingCategory.LIGHTING,
                default=4,
                description="Number of light bounces",
                min_value=1,
                max_value=128,
                depends_on="gi_enabled",
            ),
            SettingDefinition(
                id="environment_enabled",
                name="Environment Light",
                type=SettingType.BOOLEAN,
                category=SettingCategory.LIGHTING,
                default=True,
                description="Use environment/HDRI lighting",
            ),
            
            # =================================================================
            # ADVANCED SETTINGS
            # =================================================================
            SettingDefinition(
                id="render_elements",
                name="Render Elements",
                type=SettingType.MULTI_CHOICE,
                category=SettingCategory.ADVANCED,
                default=["beauty"],
                description="Additional render passes to output",
                choices=[
                    {"id": "beauty", "name": "Beauty"},
                    {"id": "diffuse", "name": "Diffuse Filter"},
                    {"id": "gi", "name": "Global Illumination"},
                    {"id": "lighting", "name": "Lighting"},
                    {"id": "reflection", "name": "Reflection"},
                    {"id": "refraction", "name": "Refraction"},
                    {"id": "specular", "name": "Specular"},
                    {"id": "self_illumination", "name": "Self-Illumination"},
                    {"id": "atmosphere", "name": "Atmosphere"},
                    {"id": "background", "name": "Background"},
                    {"id": "normals", "name": "Bumped Normals"},
                    {"id": "z_depth", "name": "Z-Depth"},
                    {"id": "material_mask", "name": "Material Mask"},
                    {"id": "object_mask", "name": "Object Mask"},
                ],
            ),
            SettingDefinition(
                id="transparent_background",
                name="Transparent Background",
                type=SettingType.BOOLEAN,
                category=SettingCategory.ADVANCED,
                default=False,
                description="Render with transparent background (alpha channel)",
            ),
            SettingDefinition(
                id="overwrite_existing",
                name="Overwrite Existing",
                type=SettingType.BOOLEAN,
                category=SettingCategory.ADVANCED,
                default=True,
                description="Overwrite existing rendered files",
            ),
        ],
    )


# Singleton instance
VANTAGE_SETTINGS_SCHEMA = get_vantage_settings_schema()
