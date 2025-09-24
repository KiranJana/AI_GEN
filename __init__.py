bl_info = {
    "name": "AI Scene Generator",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > AI Gen",
    "description": "Generates 3D scenes from text prompts.",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

import bpy

# --- 1. DEFINE ALL CLASSES FIRST ---

class MySceneProperties(bpy.types.PropertyGroup):
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

class VIEW3D_PT_ai_scene_generator(bpy.types.Panel):
    # --- Metadata for Blender ---
    
    # --- THIS LINE WAS CHANGED ---
    bl_label = "AI Scene Generator v1.1" # Changed for reload test
    
    bl_idname = "VIEW3D_PT_ai_scene_gen"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'AI Gen'

    # --- The UI Drawing Code ---
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        my_tool_props = scene.my_tool_properties

        # --- Main Prompt Section ---
        main_box = layout.box()
        main_box.label(text="1. Describe Your Scene:")
        
        # Make the prompt input box larger
        main_box.scale_y = 1.5
        main_box.prop(my_tool_props, "prompt_input", text="")
        
        # --- Settings Section ---
        settings_box = layout.box()
        settings_box.label(text="2. Adjust Settings:")
        
        # Use a row to place label and property side-by-side
        row = settings_box.row()
        row.label(text="Style:")
        row.prop(my_tool_props, "scene_style", text="")
        
        # Another row for the object count
        row = settings_box.row()
        row.label(text="Object Count:")
        row.prop(my_tool_props, "object_count", text="")
        
        # --- Effects Section ---
        effects_box = layout.box()
        effects_box.label(text="3. Add Effects:")
        effects_box.prop(my_tool_props, "add_rain_effect")

        # --- Generate Button & Status ---
        generate_box = layout.box()
        
        # Make the generate button larger
        generate_box.scale_y = 2.0
        generate_box.operator("wm.generate_scene_operator", text="Generate Scene", icon='PLAY')
        
        # Add a status bar at the bottom
        row = generate_box.row(align=True)
        row.label(text="Status:")
        row.label(text=my_tool_props.status_text, icon='INFO')

class WM_OT_generate_scene_operator(bpy.types.Operator):
    # --- Metadata for Blender ---
    bl_label = "Generate Scene"
    bl_idname = "wm.generate_scene_operator"
    bl_description = "Starts the scene generation process"

    # --- The Action Code ---
    def execute(self, context):
        scene = context.scene
        props = scene.my_tool_properties
        
        # --- Update Status ---
        props.status_text = "Processing..."
        
        # --- 1. Validation ---
        if props.prompt_input == "":
            self.report({'WARNING'}, "Prompt cannot be empty.")
            props.status_text = "Error: Prompt is empty"
            return {'CANCELLED'}

        # --- 2. Read all the properties ---
        prompt = props.prompt_input
        count = props.object_count
        style = props.scene_style
        add_rain = props.add_rain_effect
        
        print("-" * 20)
        print("Starting Scene Generation...")
        print(f"  Prompt: {prompt}")
        print(f"  Style: {style}")
        print(f"  Object Count: {count}")
        print(f"  Add Rain: {add_rain}")
        print("-" * 20)

        # --- 3. (Future) Backend Logic Goes Here ---
        # This is where you would call your AI and scene building functions.

        # --- 4. Final Status Update ---
        props.status_text = "Generation Complete!"
        
        self.report({'INFO'}, "Scene generation finished.")
        return {'FINISHED'}

# --- 2. GROUP CLASSES FOR REGISTRATION ---

classes = (
    MySceneProperties,
    VIEW3D_PT_ai_scene_generator,
    WM_OT_generate_scene_operator,
)

# --- 3. DEFINE REGISTER/UNREGISTER FUNCTIONS ---

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.my_tool_properties = bpy.props.PointerProperty(type=MySceneProperties)
    print("AI Scene Generator Addon: Registered")

def unregister():
    # Unregister in reverse order to prevent errors
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.my_tool_properties
    print("AI Scene Generator Addon: Unregistered")