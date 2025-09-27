# __init__.py

bl_info = {
    "name": "AI Scene Generator (Modular)",
    "author": "Your Name",
    "version": (2, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > AI Gen",
    "description": "A robust, modular add-on to generate scenes from text prompts with asset intelligence.",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

import bpy
from . import properties
from . import ui_panel
from . import operator
from . import database
from . import asset_scanner
from . import backend
from . import limit_manager

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
    
    # Initialize the asset intelligence database
    try:
        db = database.get_database()
        print("Asset Intelligence Database initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize asset database: {e}")

def unregister():
    for mod in reversed(modules):
        mod.unregister()
        
    del bpy.types.Scene.my_tool_properties
    
    # Reset database instance
    database.reset_database()