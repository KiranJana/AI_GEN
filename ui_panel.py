# ui_panel.py - Optimized to eliminate redundant database queries
import bpy
from . import limit_manager
from datetime import datetime

class VIEW3D_PT_ai_scene_generator(bpy.types.Panel):
    bl_label = "AI Scene Generator"
    bl_idname = "VIEW3D_PT_ai_scene_gen"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'AI Gen'

    def draw(self, context):
        layout = self.layout
        props = context.scene.my_tool_properties

        # Scene Generation Section
        main_box = layout.box()
        main_box.label(text="1. Describe Your Scene:")
        main_box.scale_y = 1.5
        main_box.prop(props, "prompt_input", text="")
        
        settings_box = layout.box()
        settings_box.label(text="2. Adjust Settings:")
        row = settings_box.row(); row.label(text="Style:"); row.prop(props, "scene_style", text="")
        row = settings_box.row(); row.label(text="Object Count:"); row.prop(props, "object_count", text="")
        
        # Asset Intelligence Section
        intel_box = layout.box()
        intel_box.label(text="3. Asset Intelligence:")
        
        # Toggle asset intelligence
        intel_box.prop(props, "use_asset_intelligence", text="Use Smart Asset Selection")
        
        if props.use_asset_intelligence:
            # Asset filters
            filter_col = intel_box.column()
            filter_col.prop(props, "filter_category", text="Category")
            filter_col.prop(props, "filter_quality", text="Quality")
            filter_col.prop(props, "max_complexity", text="Max Complexity")
            
            # Show cached asset count (no database query)
            from .properties import get_cache_manager
            cache_manager = get_cache_manager()
            
            if cache_manager.is_cache_valid():
                cached_count = props.get_cached_asset_count()
                info_row = filter_col.row()
                info_row.label(text=f"Matching Assets: {cached_count}")
            else:
                refresh_row = filter_col.row()
                refresh_row.operator("wm.refresh_asset_cache_operator", text="Load Asset Data", icon='FILE_REFRESH')
        
        effects_box = layout.box()
        effects_box.label(text="4. Add Effects:")
        effects_box.prop(props, "add_rain_effect")

        # Generate button
        generate_box = layout.box()
        generate_box.scale_y = 2.0
        if props.use_asset_intelligence and props.total_assets_in_db == 0:
            generate_box.enabled = False
            generate_box.operator("wm.generate_scene_operator", text="Scan Assets First", icon='ERROR')
        else:
            generate_box.operator("wm.generate_scene_operator", text="Generate Scene", icon='PLAY')
        
        # Status section
        status_box = layout.box()
        row = status_box.row(align=True)
        row.label(text="Status:")
        row.label(text=props.status_text, icon='INFO')
        
        # Usage tracking
        usage_box = layout.box()
        row = usage_box.row()
        row.label(text="Daily Usage:")
        row.label(text=f"{props.requests_today} / {limit_manager.RPD_LIMIT}")

        if props.cooldown_timer > 0:
            row = usage_box.row()
            row.label(text="Cooldown:")
            row.label(text=f"{props.cooldown_timer} seconds", icon='TIME')


class VIEW3D_PT_asset_intelligence(bpy.types.Panel):
    bl_label = "Asset Intelligence"
    bl_idname = "VIEW3D_PT_asset_intelligence"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'AI Gen'
    bl_parent_id = "VIEW3D_PT_ai_scene_gen"

    def draw(self, context):
        layout = self.layout
        props = context.scene.my_tool_properties

        # Asset Pack Scanning
        scan_box = layout.box()
        scan_box.label(text="Asset Pack Scanner:")
        
        # Pack path selection
        scan_box.prop(props, "asset_pack_path", text="Pack Path")
        
        row = scan_box.row()
        row.prop(props, "asset_pack_name", text="Pack Name")
        
        # Scan settings
        settings_row = scan_box.row()
        settings_row.prop(props, "scan_force_rescan", text="Force Rescan")
        settings_row.prop(props, "scan_max_workers", text="Workers")
        
        # Scan button
        scan_row = scan_box.row()
        scan_row.scale_y = 1.5
        if props.asset_pack_path:
            scan_row.operator("wm.scan_assets_operator", text="Scan Asset Pack", icon='FILE_REFRESH')
        else:
            scan_row.enabled = False
            scan_row.operator("wm.scan_assets_operator", text="Select Pack Path First", icon='ERROR')
        
        # Scan status
        status_row = scan_box.row()
        status_row.label(text=f"Status: {props.scan_status}")
        
        # Database info - NO database query here, use cached values
        db_box = layout.box()
        db_box.label(text="Database Info:")
        
        info_row = db_box.row()
        info_row.label(text=f"Assets in DB: {props.total_assets_in_db}")
        info_row.operator("wm.update_asset_stats_operator", text="", icon='FILE_REFRESH')
        
        # Quick actions
        actions_box = layout.box()
        actions_box.label(text="Quick Actions:")
        
        action_row = actions_box.row()
        action_row.operator("wm.test_asset_intelligence_operator", text="Test Intelligence", icon='CONSOLE')
        action_row.operator("wm.add_classification_pattern_operator", text="Add Pattern", icon='ADD')


class VIEW3D_PT_asset_browser(bpy.types.Panel):
    bl_label = "Asset Browser"
    bl_idname = "VIEW3D_PT_asset_browser"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'AI Gen'
    bl_parent_id = "VIEW3D_PT_ai_scene_gen"

    def draw(self, context):
        layout = self.layout
        props = context.scene.my_tool_properties

        if props.total_assets_in_db == 0:
            layout.label(text="No assets in database")
            layout.label(text="Scan an asset pack first")
            return

        # Asset search and preview - USE CACHED DATA, NO DATABASE QUERIES
        search_box = layout.box()
        search_box.label(text="Asset Search:")
        
        # Search filters (read-only display of current filters)
        if props.use_asset_intelligence:
            search_box.label(text=f"Category: {props.filter_category}")
            search_box.label(text=f"Quality: {props.filter_quality}")
            search_box.label(text=f"Max Complexity: {props.max_complexity:.1f}")
            
            # Show cached count without database query
            from .properties import get_cache_manager
            cache_manager = get_cache_manager()
            
            if cache_manager.is_cache_valid():
                cached_count = props.get_cached_asset_count()
                search_box.label(text=f"Found: {cached_count} assets")
        
        # Asset preview area - USE CACHED SAMPLE DATA
        preview_box = layout.box()
        preview_box.label(text="Asset Preview:")
        
        try:
            # Get sample assets from cache (no database query)
            from .properties import get_cache_manager
            cache_manager = get_cache_manager()
            
            sample_assets = props.get_cached_sample_assets()
            
            if sample_assets:
                preview_box.label(text=f"Showing {len(sample_assets)} sample assets:")
                for asset in sample_assets[:3]:  # Show first 3
                    row = preview_box.row()
                    row.label(text=f"• {asset['name']}")
                    row.label(text=f"({asset['category']}, {asset['quality_tier']})")
                
                # Show category breakdown from cache
                category_breakdown = props.get_cached_category_breakdown()
                if category_breakdown:
                    breakdown_row = preview_box.row()
                    breakdown_text = ", ".join([f"{cat}: {count}" for cat, count in list(category_breakdown.items())[:3]])
                    breakdown_row.label(text=f"Categories: {breakdown_text}")
                    
            else:
                if cache_manager.is_cache_valid():
                    preview_box.label(text="No assets match current filters")
                else:
                    preview_box.label(text="Loading asset data...")
                    # Trigger cache refresh
                    refresh_row = preview_box.row()
                    refresh_row.operator("wm.refresh_asset_cache_operator", text="Load Assets", icon='FILE_REFRESH')
                
        except Exception as e:
            preview_box.label(text=f"Error: {str(e)}")


# New operator to manually refresh asset cache
class WM_OT_refresh_asset_cache_operator(bpy.types.Operator):
    bl_label = "Refresh Asset Cache"
    bl_idname = "wm.refresh_asset_cache_operator"
    bl_description = "Refresh the asset filter cache"

    def execute(self, context):
        props = context.scene.my_tool_properties
        
        try:
            # Refresh the cache
            assets = props.refresh_asset_cache()
            self.report({'INFO'}, f"Cache refreshed: {len(assets)} assets found")
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to refresh cache: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


def register():
    bpy.utils.register_class(VIEW3D_PT_ai_scene_generator)
    bpy.utils.register_class(VIEW3D_PT_asset_intelligence)
    bpy.utils.register_class(VIEW3D_PT_asset_browser)
    bpy.utils.register_class(WM_OT_refresh_asset_cache_operator)

def unregister():
    bpy.utils.unregister_class(WM_OT_refresh_asset_cache_operator)
    bpy.utils.unregister_class(VIEW3D_PT_asset_browser)
    bpy.utils.unregister_class(VIEW3D_PT_asset_intelligence)
    bpy.utils.unregister_class(VIEW3D_PT_ai_scene_generator)