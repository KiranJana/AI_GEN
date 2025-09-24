# ui_panel.py
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

        main_box = layout.box()
        main_box.label(text="1. Describe Your Scene:")
        main_box.scale_y = 1.5
        main_box.prop(props, "prompt_input", text="")
        
        settings_box = layout.box()
        settings_box.label(text="2. Adjust Settings:")
        row = settings_box.row(); row.label(text="Style:"); row.prop(props, "scene_style", text="")
        row = settings_box.row(); row.label(text="Object Count:"); row.prop(props, "object_count", text="")
        
        effects_box = layout.box()
        effects_box.label(text="3. Add Effects:")
        effects_box.prop(props, "add_rain_effect")

        generate_box = layout.box()
        generate_box.scale_y = 2.0
        generate_box.operator("wm.generate_scene_operator", text="Generate Scene", icon='PLAY')
        
        status_box = layout.box()
        row = status_box.row(align=True)
        row.label(text="Status:")
        row.label(text=props.status_text, icon='INFO')
        
        # --- THIS SECTION IS NOW SIMPLIFIED ---
        # The UI now only READS the property, it doesn't write it.
        usage_box = layout.box()
        row = usage_box.row()
        row.label(text="Daily Usage:")
        row.label(text=f"{props.requests_today} / {limit_manager.RPD_LIMIT}")

        if props.cooldown_timer > 0:
            row = usage_box.row()
            row.label(text="Cooldown:")
            row.label(text=f"{props.cooldown_timer} seconds", icon='TIME')

def register():
    bpy.utils.register_class(VIEW3D_PT_ai_scene_generator)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_ai_scene_generator)