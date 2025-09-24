# __init__.py

bl_info = {
    "name": "AI Scene Generator (Modular)",
    "author": "Your Name",
    "version": (2, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > AI Gen",
    "description": "A robust, modular add-on to generate scenes from text prompts.",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

import bpy
from . import properties
from . import ui_panel
from . import operator

# A list of all modules that contain classes to register
modules = (
    properties,
    ui_panel,
    operator,
)

def register():
    for mod in modules:
        mod.register()
    
    bpy.types.Scene.my_tool_properties = bpy.props.PointerProperty(type=properties.MySceneProperties)

def unregister():
    for mod in reversed(modules):
        mod.unregister()
        
    del bpy.types.Scene.my_tool_properties