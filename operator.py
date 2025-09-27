# operator.py - Fixed threading version

import bpy
import os
import threading
from datetime import datetime
from . import backend
from . import limit_manager
from . import database

# Import the working scanner instead of the broken one
try:
    from .asset_scanner import RobustAssetScanner
except ImportError:
    # Fallback if import fails
    RobustAssetScanner = None

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
            
            # Use debug version if available
            if hasattr(backend, 'build_scene_from_instructions_debug'):
                backend.build_scene_from_instructions_debug(instructions)
            else:
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
            target=self._scan_assets_thread_fixed,
            args=(context,)
        )
        scan_thread.daemon = True
        scan_thread.start()
        
        props.scan_status = "Scanning started..."
        self.report({'INFO'}, "Asset scanning started in background")
        
        return {'FINISHED'}
    
    def _scan_assets_thread_fixed(self, context):
        """Run asset scanning with proper threading - FIXED VERSION."""
        
        # Get initial values from context (thread-safe)
        asset_pack_path = context.scene.my_tool_properties.asset_pack_path
        asset_pack_name = context.scene.my_tool_properties.asset_pack_name
        force_rescan = context.scene.my_tool_properties.scan_force_rescan
        
        def safe_update_status(message):
            """Safely update status from background thread."""
            def update_status_main_thread():
                try:
                    context.scene.my_tool_properties.scan_status = message
                except:
                    print(f"Status update: {message}")  # Fallback to console
                return None  # Important: return None to unregister timer
            
            # Schedule update on main thread
            bpy.app.timers.register(update_status_main_thread, first_interval=0.0)
        
        try:
            if not RobustAssetScanner:
                safe_update_status("Error: Scanner not available")
                return
            
            # Use the working scanner
            scanner = RobustAssetScanner()
            
            safe_update_status("Initializing scanner...")
            print("Asset scanning thread started")
            
            # Run the scan
            pack_name = asset_pack_name if asset_pack_name else None
            results = scanner.scan_asset_pack_robust(
                pack_path=asset_pack_path,
                pack_name=pack_name,
                force_rescan=force_rescan
            )
            
            # Update properties with results (thread-safe)
            def update_results():
                try:
                    props = context.scene.my_tool_properties
                    props.total_assets_in_db = results.get('total_assets', 0)
                    
                    # Create detailed status message
                    stats = results.get('scan_stats', {})
                    processed = stats.get('files_processed', 0)
                    failed = stats.get('files_failed', 0)
                    duration = stats.get('duration_seconds', 0)
                    
                    props.scan_status = f"Complete! {processed} files processed, {failed} failed, {results.get('total_assets', 0)} assets found ({duration:.1f}s)"
                except Exception as e:
                    print(f"Error updating results: {e}")
                return None
            
            bpy.app.timers.register(update_results, first_interval=0.1)
            
            print("=== WORKING SCAN RESULTS ===")
            print(f"Files processed: {results.get('scan_stats', {}).get('files_processed', 0)}")
            print(f"Files failed: {results.get('scan_stats', {}).get('files_failed', 0)}")
            print(f"Total assets: {results.get('total_assets', 0)}")
            print(f"Categories: {results.get('category_breakdown', {})}")
            print(f"Duration: {results.get('scan_stats', {}).get('duration_seconds', 0):.1f} seconds")
            
        except Exception as e:
            error_message = f"Scan failed: {str(e)}"
            safe_update_status(error_message)
            print(f"Working scanner error: {e}")
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
    bl_description = "Test the working scanner with a single file"

    def execute(self, context):
        props = context.scene.my_tool_properties
        
        try:
            if not RobustAssetScanner:
                props.scan_status = "❌ Scanner not available"
                self.report({'ERROR'}, "RobustAssetScanner not available")
                return {'CANCELLED'}
            
            # Test the working scanner
            props.scan_status = "Testing working scanner..."
            
            # Create a simple test
            scanner = RobustAssetScanner()
            
            # Check Blender executable
            blender_path = scanner.blender_executable
            if os.path.exists(blender_path):
                props.scan_status = f"✅ Blender found at: {os.path.basename(blender_path)}"
                self.report({'INFO'}, f"Working scanner ready. Blender: {blender_path}")
            else:
                props.scan_status = f"❌ Blender not found: {blender_path}"
                self.report({'ERROR'}, f"Blender executable not found: {blender_path}")
            
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
            db = database.get_database()
            db.add_classification_pattern(
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