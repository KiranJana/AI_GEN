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

        # ===== SECTION 1: Scene Description =====
        prompt_box = layout.box()
        prompt_box.label(text="Scene Description", icon='TEXT')
        prompt_box.scale_y = 1.3
        prompt_box.prop(props, "prompt_input", text="")

        # Settings in a compact row
        settings_row = layout.row(align=True)
        settings_row.prop(props, "scene_style", text="Style")
        settings_row.prop(props, "object_count", text="Count")

        # ===== SECTION 2: Asset Library Status =====
        asset_box = layout.box()
        asset_box.label(text="Asset Library (Required)", icon='ASSET_MANAGER')

        # Show asset pack status
        if props.total_assets_in_db > 0:
            status_row = asset_box.row()
            status_row.label(text=f"✓ {props.total_assets_in_db} assets loaded", icon='CHECKMARK')

            # Show matching count if filtered
            from .properties import get_cache_manager
            cache_manager = get_cache_manager()

            if cache_manager.is_cache_valid():
                cached_count = props.get_cached_asset_count()
                if cached_count != props.total_assets_in_db:
                    match_row = asset_box.row()
                    match_row.label(text=f"Matching filters: {cached_count}", icon='FILTER')

            # Asset filters - always visible since Asset Intelligence is mandatory
            filter_col = asset_box.column(align=True)
            filter_col.separator()
            filter_col.label(text="Filters:")
            filter_col.prop(props, "filter_category", text="Category")
            filter_col.prop(props, "filter_quality", text="Quality")
            filter_col.prop(props, "max_complexity", text="Complexity", slider=True)
        else:
            warning_box = asset_box.box()
            warning_box.label(text="⚠ Asset Library Required", icon='ERROR')
            warning_box.label(text="Scan an asset pack to begin")
            action_row = asset_box.row()
            action_row.scale_y = 1.3
            action_row.operator("wm.scan_assets_operator", text="Scan Asset Pack", icon='FILE_FOLDER')

        # ===== SECTION 3: Generate Button =====
        gen_box = layout.box()
        gen_box.scale_y = 2.0

        if props.total_assets_in_db == 0:
            gen_box.enabled = False
            gen_box.label(text="⚠ Scan assets first to generate", icon='INFO')
        else:
            gen_box.operator("wm.generate_scene_operator", text="🚀 Generate Scene", icon='PLAY')

        # ===== SECTION 4: Status & Usage =====
        status_box = layout.box()

        # Status with appropriate icon
        status_row = status_box.row()
        status_icon = 'CHECKMARK' if "Complete" in props.status_text else 'ERROR' if "Error" in props.status_text else 'INFO'
        status_row.label(text=f"Status: {props.status_text}", icon=status_icon)

        # Usage tracker
        usage_row = status_box.row()
        usage_row.label(text=f"Usage: {props.requests_today}/{limit_manager.RPD_LIMIT} today", icon='SORTTIME')

        if props.cooldown_timer > 0:
            cooldown_row = status_box.row()
            cooldown_row.label(text=f"Cooldown: {props.cooldown_timer}s", icon='TIME')


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

        # ===== Asset Pack Scanner =====
        scan_box = layout.box()
        scan_box.label(text="Scan Asset Pack", icon='FILE_FOLDER')

        # Pack path selection
        scan_box.prop(props, "asset_pack_path", text="")

        # Pack name (optional)
        name_row = scan_box.row()
        name_row.prop(props, "asset_pack_name", text="Pack Name")

        # Scan settings in compact row
        settings_row = scan_box.row(align=True)
        settings_row.prop(props, "scan_force_rescan", text="Force Rescan", toggle=True)
        settings_row.prop(props, "scan_max_workers", text="Workers")

        # Scan button
        scan_row = scan_box.row()
        scan_row.scale_y = 1.5
        if props.asset_pack_path:
            scan_row.operator("wm.scan_assets_operator", text="Scan Asset Pack", icon='PLAY')
        else:
            scan_row.enabled = False
            scan_row.label(text="⚠ Select pack path first", icon='ERROR')

        # Scan status
        if props.scan_status != "Not Started":
            status_row = scan_box.row()
            status_row.label(text=props.scan_status, icon='INFO')

        # ===== Database Info =====
        db_box = layout.box()
        db_box.label(text="Database Statistics", icon='PRESET')

        info_row = db_box.row()
        info_row.label(text=f"Total Assets: {props.total_assets_in_db}")
        info_row.operator("wm.update_asset_stats_operator", text="", icon='FILE_REFRESH')

        # ===== Quick Actions =====
        actions_box = layout.box()
        actions_box.label(text="Maintenance", icon='TOOL_SETTINGS')

        action_row = actions_box.row(align=True)
        action_row.operator("wm.clear_asset_cache_operator", text="Clear Cache", icon='TRASH')
        action_row.operator("wm.test_asset_intelligence_operator", text="Test", icon='CONSOLE')

        pattern_row = actions_box.row()
        pattern_row.operator("wm.add_classification_pattern_operator", text="Add Classification Pattern", icon='ADD')


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
            info_box = layout.box()
            info_box.label(text="No assets in database", icon='INFO')
            info_box.label(text="Scan an asset pack to begin")
            return

        # ===== Asset Preview =====
        preview_box = layout.box()
        preview_box.label(text="Asset Preview", icon='VIEWZOOM')

        try:
            from .properties import get_cache_manager
            cache_manager = get_cache_manager()

            sample_assets = props.get_cached_sample_assets()

            if sample_assets:
                preview_box.label(text=f"Sample of {len(sample_assets)} assets:")

                # Show first 3 sample assets
                for asset in sample_assets[:3]:
                    row = preview_box.row()
                    row.label(text=f"• {asset['name']}", icon='MESH_DATA')
                    info_label = f"{asset['category']} | {asset['quality_tier']}"
                    row.label(text=info_label)

                # Show category breakdown
                category_breakdown = props.get_cached_category_breakdown()
                if category_breakdown:
                    breakdown_box = preview_box.box()
                    breakdown_box.label(text="Category Breakdown:", icon='OUTLINER')
                    for cat, count in list(category_breakdown.items())[:5]:
                        cat_row = breakdown_box.row()
                        cat_row.label(text=f"  {cat}: {count}")

            else:
                if cache_manager.is_cache_valid():
                    preview_box.label(text="No assets match filters", icon='ERROR')
                else:
                    preview_box.label(text="Loading...", icon='TIME')
                    refresh_row = preview_box.row()
                    refresh_row.operator("wm.refresh_asset_cache_operator", text="Load Asset Data", icon='FILE_REFRESH')

        except Exception as e:
            error_box = preview_box.box()
            error_box.label(text="Error loading preview", icon='ERROR')
            error_box.label(text=str(e)[:50])


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