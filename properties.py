# properties.py - Context-safe caching implementation

import bpy
import json
import time
import tempfile
import os

# External cache storage (not in Blender properties)
class AssetCacheManager:
    """Manages asset cache outside of Blender's property system to avoid context restrictions."""
    
    def __init__(self):
        self.cache_data = {}
        self.cache_timestamp = 0
        self.cache_valid = False
        self.cache_file = None
        
    def get_cache_file_path(self):
        """Get cache file path in temp directory."""
        if not self.cache_file:
            config_path = bpy.utils.user_resource('CONFIG')
            self.cache_file = os.path.join(config_path, "asset_cache.json")
        return self.cache_file
    
    def is_cache_valid(self, max_age=30):
        """Check if cache is valid and not too old."""
        if not self.cache_valid:
            return False
        
        current_time = time.time()
        cache_age = current_time - self.cache_timestamp
        return cache_age < max_age
    
    def get_cache_key(self, category, quality, max_complexity):
        """Generate cache key from filter parameters."""
        return f"{category or 'ALL'}_{quality or 'ALL'}_{max_complexity}"
    
    def get_filtered_assets(self, category, quality, max_complexity, limit=100):
        """Get filtered assets with external caching."""
        cache_key = self.get_cache_key(category, quality, max_complexity)
        
        # Check if we have valid cached data
        if self.is_cache_valid() and cache_key in self.cache_data:
            print(f"Using cached assets for {cache_key}")
            return self.cache_data[cache_key]['assets']
        
        # Cache miss or invalid, refresh from database
        try:
            from . import database
            db = database.get_database()
            
            # Get filtered assets based on current filter settings
            filtered_assets = db.fast_asset_search(
                category=category,
                quality_tier=quality,
                max_complexity=max_complexity,
                limit=limit
            )
            
            # Update external cache
            current_time = time.time()
            self.cache_data[cache_key] = {
                'assets': filtered_assets,
                'count': len(filtered_assets),
                'timestamp': current_time,
                'category_breakdown': self._calculate_category_breakdown(filtered_assets),
                'sample_assets': filtered_assets[:5]
            }
            
            self.cache_timestamp = current_time
            self.cache_valid = True
            
            print(f"Refreshed cache for {cache_key}: {len(filtered_assets)} assets")
            return filtered_assets
            
        except Exception as e:
            print(f"Error updating external asset cache: {e}")
            self.cache_valid = False
            return []
    
    def get_cached_count(self, category, quality, max_complexity):
        """Get cached asset count without triggering database query."""
        cache_key = self.get_cache_key(category, quality, max_complexity)
        
        if self.is_cache_valid() and cache_key in self.cache_data:
            return self.cache_data[cache_key]['count']
        return 0
    
    def get_cached_sample_assets(self, category, quality, max_complexity):
        """Get sample assets for UI preview."""
        cache_key = self.get_cache_key(category, quality, max_complexity)
        
        if self.is_cache_valid() and cache_key in self.cache_data:
            return self.cache_data[cache_key]['sample_assets']
        return []
    
    def get_cached_category_breakdown(self, category, quality, max_complexity):
        """Get category breakdown."""
        cache_key = self.get_cache_key(category, quality, max_complexity)
        
        if self.is_cache_valid() and cache_key in self.cache_data:
            return self.cache_data[cache_key]['category_breakdown']
        return {}
    
    def invalidate_cache(self):
        """Mark cache as invalid."""
        self.cache_valid = False
        self.cache_data.clear()
        print("Asset cache invalidated")
    
    def _calculate_category_breakdown(self, assets):
        """Calculate category breakdown from assets."""
        breakdown = {}
        for asset in assets:
            cat = asset.get('category', 'unknown')
            breakdown[cat] = breakdown.get(cat, 0) + 1
        return breakdown

# Global cache manager instance
_cache_manager = AssetCacheManager()

def get_cache_manager():
    """Get the global cache manager instance."""
    return _cache_manager

class MySceneProperties(bpy.types.PropertyGroup):
    # Original scene generation properties
    prompt_input: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the scene you want to generate",
        default=""
    )
    
    object_count: bpy.props.IntProperty(
        name="Object Count",
        description="Number of primary objects in the scene",
        default=15,
        min=1,
        max=100
    )

    scene_style: bpy.props.EnumProperty(
        name="Style",
        description="Artistic style of the scene",
        items=[
            ('CYBERPUNK', "Cyberpunk", "A futuristic, neon-lit dystopian style"),
            ('FANTASY', "Fantasy", "A magical, medieval-inspired style"),
            ('SCI_FI', "Sci-Fi", "A clean, futuristic science-fiction style"),
        ]
    )

    add_rain_effect: bpy.props.BoolProperty(
        name="Add Rain",
        description="Include a rain particle effect in the scene",
        default=False
    )
    
    status_text: bpy.props.StringProperty(
        name="Status",
        default="Ready"
    )

    requests_today: bpy.props.IntProperty(
        name="Requests Today",
        default=0
    )
    
    cooldown_timer: bpy.props.IntProperty(
        name="Cooldown",
        default=0
    )
    
    # Asset Intelligence Properties
    asset_pack_path: bpy.props.StringProperty(
        name="Asset Pack Path",
        description="Path to the BMS asset pack directory",
        subtype='DIR_PATH',
        default="",
        update=lambda self, context: get_cache_manager().invalidate_cache()
    )
    
    asset_pack_name: bpy.props.StringProperty(
        name="Pack Name",
        description="Name for the asset pack (auto-detected if empty)",
        default=""
    )
    
    scan_status: bpy.props.StringProperty(
        name="Scan Status",
        description="Current status of asset scanning",
        default="Not Started"
    )
    
    total_assets_in_db: bpy.props.IntProperty(
        name="Total Assets",
        description="Total number of assets in database",
        default=0,
        update=lambda self, context: get_cache_manager().invalidate_cache()
    )
    
    scan_force_rescan: bpy.props.BoolProperty(
        name="Force Rescan",
        description="Force rescan of existing assets",
        default=False
    )
    
    scan_max_workers: bpy.props.IntProperty(
        name="Max Workers",
        description="Maximum number of concurrent scanning workers",
        default=2,
        min=1,
        max=8
    )
    
    # Asset selection properties for scene generation
    use_asset_intelligence: bpy.props.BoolProperty(
        name="Use Asset Intelligence",
        description="Use asset database for intelligent scene generation",
        default=True,
        update=lambda self, context: get_cache_manager().invalidate_cache()
    )
    
    filter_category: bpy.props.EnumProperty(
        name="Category Filter",
        description="Filter assets by category",
        items=[
            ('ALL', "All Categories", "Use all available categories"),
            ('ARCHITECTURE', "Architecture", "Buildings, walls, structures"),
            ('VEHICLES', "Vehicles", "Cars, trucks, bikes"),
            ('LIGHTING', "Lighting", "Lights, lamps, neon signs"),
            ('PROPS', "Props", "Various props and objects"),
            ('FURNITURE', "Furniture", "Tables, chairs, etc."),
            ('ELECTRONICS', "Electronics", "Computers, screens, devices"),
        ],
        default='ALL'
    )

    filter_quality: bpy.props.EnumProperty(
        name="Quality Filter",
        description="Filter assets by quality tier",
        items=[
            ('ALL', "All Quality", "Use all quality levels"),
            ('LOW', "Low", "Low polygon count assets"),
            ('MEDIUM', "Medium", "Medium polygon count assets"),
            ('HIGH', "High", "High polygon count assets"),
            ('ULTRA', "Ultra", "Ultra high polygon count assets"),
        ],
        default='ALL'
    )

    max_complexity: bpy.props.FloatProperty(
        name="Max Complexity",
        description="Maximum complexity score for selected assets",
        default=10.0,
        min=0.0,
        max=10.0
    )
    
    def get_filtered_assets(self, limit=100):
        """Get filtered assets using external cache manager."""
        cache_manager = get_cache_manager()
        
        # Convert filter values
        category = None if self.filter_category == 'ALL' else self.filter_category.lower()
        quality = None if self.filter_quality == 'ALL' else self.filter_quality.lower()
        
        return cache_manager.get_filtered_assets(category, quality, self.max_complexity, limit)
    
    def get_cached_sample_assets(self):
        """Get sample assets for UI preview."""
        cache_manager = get_cache_manager()
        
        category = None if self.filter_category == 'ALL' else self.filter_category.lower()
        quality = None if self.filter_quality == 'ALL' else self.filter_quality.lower()
        
        return cache_manager.get_cached_sample_assets(category, quality, self.max_complexity)
    
    def get_cached_category_breakdown(self):
        """Get category breakdown."""
        cache_manager = get_cache_manager()
        
        category = None if self.filter_category == 'ALL' else self.filter_category.lower()
        quality = None if self.filter_quality == 'ALL' else self.filter_quality.lower()
        
        return cache_manager.get_cached_category_breakdown(category, quality, self.max_complexity)
    
    def get_cached_asset_count(self):
        """Get cached asset count."""
        cache_manager = get_cache_manager()
        
        category = None if self.filter_category == 'ALL' else self.filter_category.lower()
        quality = None if self.filter_quality == 'ALL' else self.filter_quality.lower()
        
        return cache_manager.get_cached_count(category, quality, self.max_complexity)
    
    def refresh_asset_cache(self):
        """Manually refresh the asset cache."""
        cache_manager = get_cache_manager()
        cache_manager.invalidate_cache()
        return self.get_filtered_assets()

def register():
    bpy.utils.register_class(MySceneProperties)

def unregister():
    bpy.utils.unregister_class(MySceneProperties)