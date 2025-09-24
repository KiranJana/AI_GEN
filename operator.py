# operator.py

import bpy
from . import backend
from . import limit_manager
from datetime import datetime # Import datetime to help with counting

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

        instructions = backend.call_ai_service(props.prompt_input, props.scene_style, props.object_count)
        
        if instructions:
            usage_data = limit_manager.log_request(usage_data)
            limit_manager.save_usage_data(usage_data)
            
            # --- THIS IS THE NEW LINE ---
            # After a successful call, update the daily count property
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

def register():
    bpy.utils.register_class(WM_OT_generate_scene_operator)

def unregister():
    bpy.utils.unregister_class(WM_OT_generate_scene_operator)