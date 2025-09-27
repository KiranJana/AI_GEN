# operator.py

import bpy
import os
import threading
from datetime import datetime
from . import backend
from . import limit_manager
from . import asset_scanner
from . import database

class WM_OT_generate_scene_operator(bpy.types.Operator):
    bl_label = "Generate Scene"
    bl_idname = "wm.generate_scene_operator"
    bl_description = "Starts the scene generation process"

    def execute(self, context):
        props = context.scene.my_tool_properties
        
        usage_data = limit_manager.load_usage_data()
        is_allowed, reason, cooldown = limit_manager.check_limits(usage_data)
        
        if not is_allowed:
            props.status_text = reason
            props.cooldown_timer = cooldown
            self.report({'WARNING'}, f"API Limit Reached: {reason}")
            return {'CANCELLED'}
            
        props.cooldown_timer = 0
        props.status_text = "Processing..."
        
        if props.prompt_input == "":
            self.report({'WARNING'}, "Prompt cannot be empty.")
            props.status_text = "Error: Prompt is empty"
            return {'CANCELLED'}

        # Use asset intelligence if enabled and available
        if props.use_asset_intelligence:
            try:
                db = database.get_database()
                
                # Get filtered assets based on user preferences
                category = None if props.filter_category == 'ALL' else props.filter_category.lower()
                quality = None if props.filter_quality == 'ALL' else props.filter_quality.lower()
                
                available_assets = db.fast_asset_search(
                    category=category,
                    quality_tier=quality,
                    max_complexity=props.max_complexity,
                    limit=100
                )
                
                if available_assets:
                    props.status_text = f"Using {len(available_assets)} assets from database..."
                    # Enhanced scene generation with asset intelligence
                    instructions = backend.call_ai_service_with_assets(
                        props.prompt_input, 
                        props.scene_style, 
                        props.object_count,
                        available_assets
                    )
                else:
                    props.status_text = "No assets found with current filters, using basic generation..."
                    instructions = backend.call_ai_service(props.prompt_input, props.scene_style, props.object_count)
                    
            except Exception as e:
                self.report({'WARNING'}, f"Asset intelligence failed: {e}, using basic generation")
                instructions = backend.call_ai_service(props.prompt_input, props.scene_style, props.object_count)
        else:
            # Original basic scene generation
            instructions = backend.call_ai_service(props.prompt_input, props.scene_style, props.object_count)
        
        if instructions:
            usage_data = limit_manager.log_request(usage_data)
            limit_manager.save_usage_data(usage_data)
            
            # Update daily count property
            today = datetime.now().date()
            props.requests_today = len([r for r in usage_data.get("requests", []) if datetime.fromtimestamp(r).date() == today])
            
            backend.build_scene_from_instructions(instructions)
            props.status_text = "Generation Complete!"
            self.report({'INFO'}, "Scene generation finished.")
        else:
            props.status_text = "Error: AI call failed. See console."
            self.report({'ERROR'}, "Failed to get instructions from AI. See System Console for details.")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class WM_OT_scan_assets_operator(bpy.types.Operator):
    bl_label = "Scan Asset Pack"
    bl_idname = "wm.scan_assets_operator"
    bl_description = "Scan BMS asset pack for AI intelligence"

    def execute(self, context):
        props = context.scene.my_tool_properties
        
        if not props.asset_pack_path or not os.path.exists(props.asset_pack_path):
            self.report({'ERROR'}, "Please select a valid asset pack path")
            props.scan_status = "Error: Invalid path"
            return {'CANCELLED'}
        
        # Start scanning in a separate thread to avoid blocking UI
        scan_thread = threading.Thread(
            target=self._scan_assets_thread,
            args=(context,)
        )
        scan_thread.daemon = True
        scan_thread.start()
        
        props.scan_status = "Scanning started..."
        self.report({'INFO'}, "Asset scanning started in background")
        
        return {'FINISHED'}
    
    def _scan_assets_thread(self, context):
        """Run asset scanning in separate thread."""
        props = context.scene.my_tool_properties
        
        try:
            # Create scanner with user settings
            db = database.create_database()  # Use dependency injection
            scanner = asset_scanner.RobustAssetScanner(
                database=db, 
                max_workers=props.scan_max_workers
            )
            
            # Update status
            def update_status(msg):
                props.scan_status = msg
                # Force UI update (this needs to be called from main thread)
                bpy.app.timers.register(lambda: None, first_interval=0.0)
            
            update_status("Initializing scanner...")
            
            # Run the scan
            pack_name = props.asset_pack_name if props.asset_pack_name else None
            results = scanner.scan_asset_pack_robust(
                pack_path=props.asset_pack_path,
                pack_name=pack_name,
                force_rescan=props.scan_force_rescan,
                max_concurrent=props.scan_max_workers
            )
            
            # Update properties with results
            props.total_assets_in_db = results.get('total_assets', 0)
            props.scan_status = f"Scan complete! Found {results.get('total_assets', 0)} assets"
            
            print("=== SCAN RESULTS ===")
            print(f"Total assets: {results.get('total_assets', 0)}")
            print(f"Categories: {results.get('category_breakdown', {})}")
            print(f"Duration: {results.get('duration_seconds', 0):.1f} seconds")
            
        except Exception as e:
            props.scan_status = f"Scan failed: {str(e)}"
            print(f"Asset scan error: {e}")
            import traceback
            traceback.print_exc()


class WM_OT_update_asset_stats_operator(bpy.types.Operator):
    bl_label = "Update Asset Stats"
    bl_idname = "wm.update_asset_stats_operator"
    bl_description = "Update asset database statistics"

    def execute(self, context):
        props = context.scene.my_tool_properties
        
        try:
            db = database.get_database()
            stats = db.get_database_stats()
            
            props.total_assets_in_db = stats.get('assets', 0)
            props.scan_status = f"Database contains {stats.get('assets', 0)} assets"
            
            self.report({'INFO'}, f"Found {stats.get('assets', 0)} assets in database")
            
        except Exception as e:
            props.scan_status = f"Error: {str(e)}"
            self.report({'ERROR'}, f"Failed to update stats: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class WM_OT_test_asset_intelligence_operator(bpy.types.Operator):
    bl_label = "Test Asset Intelligence"
    bl_idname = "wm.test_asset_intelligence_operator"
    bl_description = "Run asset intelligence test"

    def execute(self, context):
        props = context.scene.my_tool_properties
        
        try:
            # Run quick database test
            from . import test_scanner
            
            props.scan_status = "Running intelligence test..."
            
            # Run the test in a thread
            test_thread = threading.Thread(target=test_scanner.quick_database_test)
            test_thread.daemon = True
            test_thread.start()
            
            self.report({'INFO'}, "Asset intelligence test started - check console for results")
            props.scan_status = "Test completed - check console"
            
        except Exception as e:
            props.scan_status = f"Test failed: {str(e)}"
            self.report({'ERROR'}, f"Test failed: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class WM_OT_add_classification_pattern_operator(bpy.types.Operator):
    bl_label = "Add Pattern"
    bl_idname = "wm.add_classification_pattern_operator"
    bl_description = "Add a new classification pattern"
    
    pattern_type: bpy.props.EnumProperty(
        name="Pattern Type",
        items=[
            ('category', "Category", "Asset category pattern"),
            ('style', "Style", "Style classification pattern"),
            ('material_family', "Material", "Material family pattern"),
        ]
    )
    
    pattern_name: bpy.props.StringProperty(name="Pattern Name")
    keywords: bpy.props.StringProperty(name="Keywords (comma-separated)")

    def execute(self, context):
        if not self.pattern_name or not self.keywords:
            self.report({'ERROR'}, "Please provide pattern name and keywords")
            return {'CANCELLED'}
        
        try:
            keywords_list = [k.strip() for k in self.keywords.split(',')]
            asset_scanner.add_classification_pattern(
                self.pattern_type,
                self.pattern_name,
                keywords_list
            )
            
            self.report({'INFO'}, f"Added {self.pattern_type} pattern: {self.pattern_name}")
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to add pattern: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def register():
    bpy.utils.register_class(WM_OT_generate_scene_operator)
    bpy.utils.register_class(WM_OT_scan_assets_operator)
    bpy.utils.register_class(WM_OT_update_asset_stats_operator)
    bpy.utils.register_class(WM_OT_test_asset_intelligence_operator)
    bpy.utils.register_class(WM_OT_add_classification_pattern_operator)

def unregister():
    bpy.utils.unregister_class(WM_OT_add_classification_pattern_operator)
    bpy.utils.unregister_class(WM_OT_test_asset_intelligence_operator)
    bpy.utils.unregister_class(WM_OT_update_asset_stats_operator)
    bpy.utils.unregister_class(WM_OT_scan_assets_operator)
    bpy.utils.unregister_class(WM_OT_generate_scene_operator)