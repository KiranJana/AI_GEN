# properties.py

import bpy

class MySceneProperties(bpy.types.PropertyGroup):
    # Original scene generation properties
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
    
    # New Asset Intelligence Properties
    asset_pack_path: bpy.props.StringProperty(
        name="Asset Pack Path",
        description="Path to the BMS asset pack directory",
        subtype='DIR_PATH',
        default=""
    )
    
    asset_pack_name: bpy.props.StringProperty(
        name="Pack Name",
        description="Name for the asset pack (auto-detected if empty)",
        default=""
    )
    
    scan_status: bpy.props.StringProperty(
        name="Scan Status",
        description="Current status of asset scanning",
        default="Not Started"
    )
    
    total_assets_in_db: bpy.props.IntProperty(
        name="Total Assets",
        description="Total number of assets in database",
        default=0
    )
    
    scan_force_rescan: bpy.props.BoolProperty(
        name="Force Rescan",
        description="Force rescan of existing assets",
        default=False
    )
    
    scan_max_workers: bpy.props.IntProperty(
        name="Max Workers",
        description="Maximum number of concurrent scanning workers",
        default=2,
        min=1,
        max=8
    )
    
    # Asset selection properties for scene generation
    use_asset_intelligence: bpy.props.BoolProperty(
        name="Use Asset Intelligence",
        description="Use asset database for intelligent scene generation",
        default=False
    )
    
    filter_category: bpy.props.EnumProperty(
        name="Category Filter",
        description="Filter assets by category",
        items=[
            ('ALL', "All Categories", "Use all available categories"),
            ('ARCHITECTURE', "Architecture", "Buildings, walls, structures"),
            ('VEHICLES', "Vehicles", "Cars, trucks, bikes"),
            ('LIGHTING', "Lighting", "Lights, lamps, neon signs"),
            ('PROPS', "Props", "Various props and objects"),
            ('FURNITURE', "Furniture", "Tables, chairs, etc."),
            ('ELECTRONICS', "Electronics", "Computers, screens, devices"),
        ],
        default='ALL'
    )
    
    filter_quality: bpy.props.EnumProperty(
        name="Quality Filter",
        description="Filter assets by quality tier",
        items=[
            ('ALL', "All Quality", "Use all quality levels"),
            ('LOW', "Low", "Low polygon count assets"),
            ('MEDIUM', "Medium", "Medium polygon count assets"),
            ('HIGH', "High", "High polygon count assets"),
            ('ULTRA', "Ultra", "Ultra high polygon count assets"),
        ],
        default='ALL'
    )
    
    max_complexity: bpy.props.FloatProperty(
        name="Max Complexity",
        description="Maximum complexity score for selected assets",
        default=10.0,
        min=0.0,
        max=10.0
    )

def register():
    bpy.utils.register_class(MySceneProperties)

def unregister():
    bpy.utils.unregister_class(MySceneProperties)