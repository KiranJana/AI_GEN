# properties.py

import bpy

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

    requests_today: bpy.props.IntProperty(
        name="Requests Today",
        default=0
    )
    
    cooldown_timer: bpy.props.IntProperty(
        name="Cooldown",
        default=0
    )

def register():
    bpy.utils.register_class(MySceneProperties)

def unregister():
    bpy.utils.unregister_class(MySceneProperties)