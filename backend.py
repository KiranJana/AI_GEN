# backend.py - Enhanced with robust asset loading

import bpy
import random
import json
import os
import sqlite3

# new commit 
import sys
import os
user_lib_path = os.path.join(os.path.expanduser("~"), "blender_python_libs")
if user_lib_path not in sys.path:
    sys.path.append(user_lib_path)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- Main Backend Logic ---

API_KEY = os.environ.get("GEMINI_API_KEY") # Make sure your key is pasted here


def call_ai_service_with_assets(prompt, style, count, available_assets=None):
    """
    AI service call with optional asset intelligence.
    If available_assets is provided, uses enhanced asset-aware generation.
    Otherwise, falls back to basic coordinate generation.
    """
    # Handle missing AI library
    if not genai:
        if available_assets:
            print("Google Generative AI library not found. Using asset-aware mock data.")
            return generate_asset_aware_mock_data(available_assets, count)
        else:
            print("Google Generative AI library not found. Returning basic mock data.")
            return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 0) for _ in range(count)]}

    # Handle missing API key
    if API_KEY == "YOUR_GEMINI_API_KEY" or not API_KEY:
        if available_assets:
            print("Gemini API Key not set. Using asset-aware mock data.")
            return generate_asset_aware_mock_data(available_assets, count)
        else:
            print("Gemini API Key not set. Returning basic mock data.")
            return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 0) for _ in range(count)]}

    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        generation_config = genai.GenerationConfig(response_mime_type="application/json")

        # Branch: Asset-aware generation
        if available_assets and len(available_assets) > 0:
            # Filter out character rig controls and other non-visual assets
            filtered_assets = filter_visual_assets(available_assets)

            if not filtered_assets:
                print("No suitable visual assets found, falling back to mock data")
                return generate_asset_aware_mock_data(available_assets, count)

            # Create asset information for the AI (limit to reasonable number, essential fields only)
            asset_info = []
            for asset in filtered_assets[:30]:  # Limit to first 30 good assets
                dims = extract_asset_dimensions(asset)
                asset_info.append({
                    'id': asset['id'],
                    'name': asset['name'],
                    'dimensions': [round(dims[0], 2), round(dims[1], 2), round(dims[2], 2)],  # Compact: [width, depth, height]
                    'category': asset['category']
                    # Removed: size_category, quality, complexity, polygons, style (not needed for positioning)
                })

            # Enhanced prompt with asset intelligence and spatial reasoning
            full_prompt = (
            "You are an expert Blender scene layout assistant specializing in realistic 3D spatial composition. "
            "You have access to a database of 3D assets with ACCURATE DIMENSIONS. Your PRIMARY goal is to create "
            "scenes with ZERO overlapping assets while maintaining visual appeal.\n"
            "\n"
            "CRITICAL RULES (MUST FOLLOW):\n"
            "1. NEVER OVERLAP ASSETS - Use dimensions to calculate proper spacing\n"
            "2. USE REALISTIC SPACING - Buildings 2m+ apart, vehicles 3m+ apart, props 0.5m+ apart\n"
            "3. GROUND PLACEMENT - Set Z=0 for ground objects (buildings, vehicles, streets)\n"
            "4. CONSIDER FOOTPRINTS - Large objects need proportionally more space\n"
            "5. VERIFY BEFORE OUTPUT - Check that no footprints overlap\n"
            "\n"
            "REQUIRED OUTPUT FORMAT:\n"
            "{\n"
            '  "locations": [[X, Y, Z], ...],\n'
            '  "rotations": [[0, 0, R], ...],  // R in radians around Z-axis\n'
            '  "selected_asset_ids": [123, ...],\n'
            '  "reasoning": "Brief explanation of layout strategy"\n'
            "}\n"
            "\n"
            "AVAILABLE ASSETS:\n"
            f"{json.dumps(asset_info, indent=2)}\n"
            "Format: {{id, name, dimensions: [width, depth, height], category}}\n"
            "\n"
            "SCENE REQUIREMENTS:\n"
            f"- Style: {style}\n"
            f"- User Prompt: {prompt}\n"
            f"- Asset Count: {count}\n"
            "\n"
            "PLACEMENT STRATEGY (Follow in order):\n"
            "1. ANALYZE - Review dimensions array: [width, depth, height] in meters\n"
            "2. PRIORITIZE - Place largest assets first (buildings, large structures)\n"
            "3. CALCULATE FOOTPRINT - For each asset: footprint = dimensions[0] × dimensions[1]\n"
            "4. MAINTAIN SPACING - Keep minimum distance based on category:\n"
            "   • Buildings/Architecture: 2m minimum spacing\n"
            "   • Vehicles: 3m minimum spacing (traffic flow)\n"
            "   • Props/Small objects: 0.5m minimum spacing\n"
            "5. FILL STRATEGICALLY - Add medium assets (vehicles), then small details\n"
            "6. VERIFY NO OVERLAPS - Check each asset against all previously placed assets\n"
            "\n"
            "HEIGHT ASSIGNMENT:\n"
            "- Ground objects (buildings, vehicles, roads, props): Z = 0\n"
            "- Elevated lights/signs: Z = 3 to 8m\n"
            "- Floating/aerial objects: Z = height/2\n"
            "\n"
            "ROTATION GUIDELINES (Z-axis, radians):\n"
            "- Buildings along streets: 0 or 3.14 (π) to face inward\n"
            "- Vehicles on roads: 0 to 0.3 for slight variation\n"
            "- Props/details: 0 to 6.28 (2π) for natural randomness\n"
            "\n"
            "SPACING CALCULATION EXAMPLE:\n"
            "Asset A: width=5m, depth=10m, placed at (0, 0, 0)\n"
            "Asset B: width=4m, depth=6m\n"
            "\n"
            "Valid positions for Asset B:\n"
            "  • X direction: (7, 0, 0) or further [5/2 + 4/2 + 2m spacing = 6.5m]\n"
            "  • Y direction: (0, 11, 0) or further [10/2 + 6/2 + 2m spacing = 10m]\n"
            "  • Diagonal: (6, 9, 0) or similar positions maintaining spacing\n"
            "\n"
            "INVALID position: (3, 0, 0) - WOULD OVERLAP!\n"
            "\n"
            "ASSET SELECTION:\n"
            "- Match categories to prompt keywords (e.g., 'street' → roads, vehicles, buildings)\n"
            "- Prefer 'medium' quality for balance\n"
            "- Mix asset sizes for visual interest\n"
            "- Ensure style consistency\n"
            "\n"
            "OUTPUT REQUIREMENTS:\n"
            f"- Select exactly {count} assets\n"
            "- ZERO overlapping footprints (verify using dimensions)\n"
            "- Realistic spatial distribution\n"
            "- Asset IDs as integers in selected_asset_ids array\n"
            "- Rotations in radians around Z-axis\n"
            "- Provide clear reasoning for layout choices\n"
        )
        
            response = model.generate_content(full_prompt, generation_config=generation_config)

            print("--- Enhanced AI Response with Asset IDs ---")
            print(response.text)
            print("-------------------------------------------")

            ai_response = json.loads(response.text)

            # Validate and enhance the response
            if 'locations' not in ai_response:
                raise ValueError("AI response missing 'locations' key")

            # Convert asset IDs to asset data for backward compatibility
            selected_asset_ids = ai_response.get('selected_asset_ids', [])
            selected_assets = []

            # Create ID lookup map for fast access
            asset_id_map = {asset['id']: asset for asset in filtered_assets}

            print(f"DEBUG: AI selected {len(selected_asset_ids)} asset IDs: {selected_asset_ids}")
            print(f"DEBUG: Available asset IDs in map: {list(asset_id_map.keys())}")

            for asset_id in selected_asset_ids:
                if asset_id in asset_id_map:
                    selected_assets.append(asset_id_map[asset_id])
                    print(f"  ✅ Matched asset ID {asset_id}: {asset_id_map[asset_id]['name']}")
                else:
                    # If AI provided invalid ID, select a random valid asset
                    replacement = random.choice(filtered_assets)
                    selected_assets.append(replacement)
                    print(f"  ⚠️  Replaced invalid asset ID {asset_id} with {replacement['name']} (ID: {replacement['id']})")

            # Ensure we have enough assets
            while len(selected_assets) < count:
                selected_assets.append(random.choice(filtered_assets))

            # Ensure locations and assets match in count
            locations = ai_response['locations']
            while len(locations) < count:
                locations.append([
                    random.uniform(-10, 10),
                    random.uniform(-10, 10),
                    0.0
                ])

            # Handle rotations (new field from enhanced AI)
            rotations = ai_response.get('rotations', [])
            while len(rotations) < count:
                # Generate default rotations based on category
                asset = selected_assets[len(rotations)] if len(rotations) < len(selected_assets) else selected_assets[0]
                category = asset.get('category', '').lower()
                if 'architecture' in category or 'building' in category:
                    rot = 0 if random.random() < 0.5 else 3.14159
                elif 'vehicle' in category:
                    rot = random.uniform(-0.2, 0.2)
                else:
                    rot = random.uniform(0, 6.28318)
                rotations.append([0, 0, rot])

            # Trim to exact count
            ai_response['locations'] = locations[:count]
            ai_response['rotations'] = rotations[:count]
            ai_response['selected_assets'] = selected_assets[:count]  # Full asset data, not just IDs

            print(f"DEBUG: Returning {len(ai_response['selected_assets'])} selected assets")
            return ai_response

        # No assets provided - return error instead of fallback
        else:
            print("❌ Error: No assets available for scene generation")
            return None

    except Exception as e:
        print(f"An error occurred with the AI service: {e}")
        if available_assets:
            print("Falling back to asset-aware mock data...")
            return generate_asset_aware_mock_data(available_assets, count)
        else:
            print("Falling back to basic mock data...")
            return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 0) for _ in range(count)]}


# Backward compatibility alias
call_ai_service = call_ai_service_with_assets


# Utility Functions

def extract_asset_dimensions(asset):
    """
    Extract dimensions from asset data in standardized format.
    Returns [width, depth, height] as a list of floats.
    """
    dims = asset.get('dimensions', [1, 1, 1])
    if not isinstance(dims, list) or len(dims) < 3:
        dims = [
            asset.get('width', 1.0),
            asset.get('depth', 1.0),
            asset.get('height', 1.0)
        ]
    return dims




def filter_visual_assets(available_assets):
    """Filter out character rig controls and keep only visual 3D assets."""
    visual_assets = []
    
    # Words that indicate non-visual or rig assets
    exclude_keywords = [
        'cs_', 'ctrl', 'ik_', 'bone', 'rig', 'control', 'constraint',
        'driver', 'target', 'pole', 'helper', 'locator', 'null',
        'ankle_str', 'arm_ik', 'belly_ctrl', 'breath', 'brow_ctrl',
        'arm_toon', 'arm_scale'
    ]
    
    print(f"DEBUG: Filtering {len(available_assets)} assets...")
    
    for i, asset in enumerate(available_assets):
        asset_name = asset['name'].lower()
        skip_reasons = []
        
        # Skip if name contains exclude keywords
        if any(keyword in asset_name for keyword in exclude_keywords):
            skip_reasons.append("contains exclude keywords")
        
        # Skip if it has zero polygons (likely a control object)
        polygon_count = asset.get('polygon_count', 0)
        if polygon_count <= 0:
            skip_reasons.append(f"zero polygons ({polygon_count})")
        
        # Skip if dimensions are all zero
        dimensions = asset.get('dimensions', [0, 0, 0])
        if isinstance(dimensions, list) and len(dimensions) >= 3:
            width, height, depth = dimensions[:3]
        else:
            width = asset.get('width', 0)
            height = asset.get('height', 0) 
            depth = asset.get('depth', 0)
        
        if width == 0 and height == 0 and depth == 0:
            skip_reasons.append(f"zero dimensions ({width}, {height}, {depth})")
        
        # Debug first few assets
        if i < 5:
            print(f"  Asset {i}: '{asset['name']}' - polygons: {polygon_count}, dimensions: {dimensions}")
            if skip_reasons:
                print(f"    SKIPPED: {', '.join(skip_reasons)}")
            else:
                print(f"    INCLUDED")
        
        # Only skip if we have skip reasons
        if skip_reasons:
            continue
            
        visual_assets.append(asset)
    
    print(f"Filtered to {len(visual_assets)} visual assets from {len(available_assets)} total")
    
    # If we have no visual assets, be more permissive
    if len(visual_assets) == 0:
        print("No assets passed strict filtering, trying more permissive approach...")
        for asset in available_assets:
            # Only exclude obvious rig controls
            asset_name = asset['name'].lower()
            if not any(keyword in asset_name for keyword in ['cs_', 'ctrl', 'ik_', 'bone_']):
                visual_assets.append(asset)
                if len(visual_assets) >= 10:  # Take first 10
                    break
        
        print(f"Permissive filtering found {len(visual_assets)} assets")
    
    return visual_assets


def generate_asset_aware_mock_data(available_assets, count):
    """Generate mock data that's aware of available assets."""
    # Filter for visual assets first
    filtered_assets = filter_visual_assets(available_assets)
    
    if not filtered_assets:
        print("No visual assets available, using basic mock data")
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 0) for _ in range(count)]}
    
    selected_assets = []
    locations = []
    
    for i in range(count):
        # Randomly select from filtered visual assets
        asset = random.choice(filtered_assets)
        selected_assets.append(asset)  # Store full asset data, not just name
        
        # Generate location based on asset type
        if asset['category'] == 'architecture':
            # Buildings should be on the ground and spaced out
            x = random.uniform(-15, 15)
            y = random.uniform(-15, 15)
            z = 0.0
        elif asset['category'] == 'vehicles':
            # Vehicles on roads/ground
            x = random.uniform(-10, 10)
            y = random.uniform(-8, 8)
            z = 0.0
        elif asset['category'] == 'lighting':
            # Lights can be elevated
            x = random.uniform(-12, 12)
            y = random.uniform(-12, 12)
            z = random.uniform(2, 8)
        else:
            # General props
            x = random.uniform(-8, 8)
            y = random.uniform(-8, 8)
            z = random.uniform(0, 2)
        
        locations.append([x, y, z])
    
    return {
        "locations": locations,
        "selected_assets": selected_assets,  # Full asset data
        "reasoning": f"Mock selection from {len(filtered_assets)} filtered visual assets with category-aware placement"
    }








def build_scene_from_instructions(instructions):
    """Simplified scene builder - trusts AI positioning completely."""
    # Clear existing mesh objects (fast direct API)
    for obj in list(bpy.context.scene.objects):
        if obj.type == 'MESH':
            bpy.data.objects.remove(obj, do_unlink=True)

    # Validate AI response
    if not instructions or not isinstance(instructions, dict) or "locations" not in instructions:
        print("❌ Error: Invalid AI response (missing 'locations' key)")
        return

    # Extract data from AI response
    locations = instructions["locations"]
    selected_assets = instructions.get("selected_assets", [])
    rotations = instructions.get("rotations", [[0, 0, 0] for _ in range(len(locations))])
    reasoning = instructions.get("reasoning", "No reasoning provided")

    print(f"\n📐 Scene Generation: {len(selected_assets)} assets")
    print(f"Reasoning: {reasoning}")

    # Check if we have assets to work with
    if not selected_assets:
        print("⚠️ No assets selected by AI")
        return

    # Load assets at AI-specified positions (ZERO modification)
    assets_by_file = group_assets_by_blend_file(selected_assets, locations, rotations)
    load_assets_optimized(assets_by_file)

    print("✅ Scene complete - AI positioning preserved")


def group_assets_by_blend_file(selected_assets, locations, rotations=None):
    """Group assets by their source .blend file for batch loading."""
    assets_by_file = {}

    if rotations is None:
        rotations = [[0, 0, 0] for _ in range(len(selected_assets))]

    for i, asset_data in enumerate(selected_assets):
        if not asset_data or i >= len(locations):
            continue

        location = locations[i]
        rotation = rotations[i] if i < len(rotations) else [0, 0, 0]

        # Validate location
        if not isinstance(location, (list, tuple)) or len(location) != 3:
            print(f"Skipping invalid location at index {i}: {location}")
            continue

        if not all(isinstance(item, (int, float)) for item in location):
            print(f"Skipping non-numeric location at index {i}: {location}")
            continue

        # Validate asset data
        if not all(field in asset_data for field in ['id', 'name', 'blend_file_path']):
            print(f"Skipping asset with missing data at index {i}: {asset_data.get('name', 'unknown')}")
            continue

        blend_file = asset_data['blend_file_path']

        # Validate file exists
        if not os.path.exists(blend_file):
            print(f"Skipping asset with missing file: {blend_file}")
            continue

        # Group by file
        if blend_file not in assets_by_file:
            assets_by_file[blend_file] = []

        assets_by_file[blend_file].append({
            'asset_data': asset_data,
            'location': location,
            'rotation': rotation,
            'index': i
        })

    print(f"📊 Grouped {len(selected_assets)} assets into {len(assets_by_file)} files:")
    for blend_file, assets in assets_by_file.items():
        print(f"   {os.path.basename(blend_file)}: {len(assets)} assets")

    return assets_by_file


def load_assets_optimized(assets_by_file):
    """Load assets in batches by file for optimal performance."""
    total_loaded = 0
    total_failed = 0
    
    for blend_file, asset_entries in assets_by_file.items():
        print(f"\n🔄 Processing file: {os.path.basename(blend_file)} ({len(asset_entries)} assets)")
        
        try:
            loaded, failed = load_assets_from_single_file(blend_file, asset_entries)
            total_loaded += loaded
            total_failed += failed
            
        except Exception as e:
            print(f"❌ Failed to process file {blend_file}: {e}")
            # Create cube fallbacks for all assets in this file
            for entry in asset_entries:
                create_cube_fallback(entry['asset_data'], entry['location'], entry['index'])
            total_failed += len(asset_entries)
    
    print(f"\n📊 Asset loading complete: {total_loaded} loaded, {total_failed} failed")


def load_assets_from_single_file(blend_file, asset_entries):
    """Load multiple assets from a single .blend file efficiently."""
    loaded_count = 0
    failed_count = 0
    
    # Separate collection-based and mesh-based assets
    collection_assets = []
    mesh_assets = []
    
    for entry in asset_entries:
        asset_data = entry['asset_data']
        if asset_data.get('collection_name'):
            collection_assets.append(entry)
        else:
            mesh_assets.append(entry)
    
    # Load collections in batch
    if collection_assets:
        collections_loaded, collections_failed = load_collections_batch(blend_file, collection_assets)
        loaded_count += collections_loaded
        failed_count += collections_failed
    
    # Load meshes in batch
    if mesh_assets:
        meshes_loaded, meshes_failed = load_meshes_batch(blend_file, mesh_assets)
        loaded_count += meshes_loaded
        failed_count += meshes_failed
    
    return loaded_count, failed_count


def load_collections_batch(blend_file, collection_assets):
    """Load multiple collections from a single file in one operation."""
    print(f"   Loading {len(collection_assets)} collections...")

    # Extract collection names needed
    collection_names = [entry['asset_data']['collection_name'] for entry in collection_assets]

    try:
        # Single file open operation for all collections
        with bpy.data.libraries.load(blend_file, link=False) as (data_from, data_to):
            available_collections = list(data_from.collections)
            collections_to_load = []

            for collection_name in collection_names:
                # Ensure the collection name is a valid string
                if collection_name and isinstance(collection_name, str) and collection_name in available_collections:
                    collections_to_load.append(collection_name)
                else:
                    print(f"     ⚠️  Collection '{collection_name}' not found or is invalid")

            # Load all valid collections at once
            if collections_to_load:
                data_to.collections = collections_to_load
                print(f"     📦 Loading {len(collections_to_load)} collections in batch")
            else:
                print("     No valid collections to load.")
        
        # Create instances for successfully loaded collections
        loaded_count = 0
        failed_count = 0
        
        for entry in collection_assets:
            asset_data = entry['asset_data']
            collection_name = asset_data['collection_name']
            rotation = entry.get('rotation', [0, 0, 0])

            if collection_name in bpy.data.collections:
                # Create collection instance with rotation
                create_collection_instance(asset_data, entry['location'], rotation)
                loaded_count += 1
                print(f"     ✅ {asset_data['name']}")
            else:
                # Create fallback cube
                create_cube_fallback(asset_data, entry['location'], entry['index'])
                failed_count += 1
                print(f"     ❌ {asset_data['name']} (collection not loaded)")
        
        return loaded_count, failed_count
        
    except Exception as e:
        print(f"     ❌ Batch collection loading failed: {e}")
        # Create fallbacks for all
        for entry in collection_assets:
            create_cube_fallback(entry['asset_data'], entry['location'], entry['index'])
        return 0, len(collection_assets)


def load_meshes_batch(blend_file, mesh_assets):
    """Load multiple objects (preferably) or meshes from a single file in one operation."""
    print(f"   Loading {len(mesh_assets)} meshes/objects...")

    try:
        # Open the .blend file and list available objects and meshes
        with bpy.data.libraries.load(blend_file, link=False) as (data_from, data_to):
            available_objects = list(data_from.objects)
            available_meshes = list(data_from.meshes)
            objects_to_load = []
            meshes_to_load = []
            asset_object_map = {}
            asset_mesh_map = {}

            for entry in mesh_assets:
                asset_data = entry['asset_data']
                asset_name = asset_data['name']
                object_name = asset_data.get('object_name')
                # Prefer loading the object if available
                if object_name and object_name in available_objects:
                    objects_to_load.append(object_name)
                    asset_object_map[asset_data['id']] = object_name
                    print(f"     🔗 {asset_name} -> OBJECT: {object_name}")
                else:
                    # Fallback to mesh loading
                    matching_meshes = find_matching_mesh_names(asset_name, available_meshes)
                    if matching_meshes:
                        selected_mesh = matching_meshes[0]
                        meshes_to_load.append(selected_mesh)
                        asset_mesh_map[asset_data['id']] = selected_mesh
                        print(f"     🔗 {asset_name} -> MESH: {selected_mesh}")
                    else:
                        print(f"     ⚠️  No object or mesh found for {asset_name}")

            # Load all objects and meshes at once
            data_to.objects = list(set(objects_to_load))
            data_to.meshes = list(set(meshes_to_load))
            # Materials load automatically with objects/meshes - no need to pre-load

        # Link loaded objects to the scene and set location
        loaded_count = 0
        failed_count = 0

        for entry in mesh_assets:
            asset_data = entry['asset_data']
            asset_id = asset_data['id']
            location = entry['location']
            rotation = entry.get('rotation', [0, 0, 0])

            # If object was loaded, link it
            if asset_id in asset_object_map:
                object_name = asset_object_map[asset_id]
                if object_name in bpy.data.objects:
                    obj = bpy.data.objects[object_name]
                    # Create instance (shares mesh data for performance)
                    new_obj = obj.copy()
                    new_obj.data = obj.data  # Instancing: share mesh data (90% memory reduction)
                    bpy.context.collection.objects.link(new_obj)
                    new_obj.location = location

                    # Apply rotation
                    if rotation and len(rotation) >= 3:
                        new_obj.rotation_euler = rotation

                    # Apply scale variation
                    category = asset_data.get('category', '').lower()
                    if 'architecture' not in category and 'building' not in category:
                        scale_factor = random.uniform(0.95, 1.05)
                        new_obj.scale = (scale_factor, scale_factor, scale_factor)

                    new_obj.name = f"{asset_data['name']}_{asset_id}"
                    new_obj["asset_id"] = asset_id
                    new_obj["asset_name"] = asset_data['name']
                    loaded_count += 1
                    print(f"     ✅ {asset_data['name']} (object)")
                else:
                    create_cube_fallback(asset_data, location, entry['index'])
                    failed_count += 1
                    print(f"     ❌ {asset_data['name']} (object not loaded)")
            # Else, fallback to mesh loading
            elif asset_id in asset_mesh_map:
                mesh_name = asset_mesh_map[asset_id]
                if mesh_name in bpy.data.meshes:
                    create_mesh_object(asset_data, location, mesh_name, rotation)
                    loaded_count += 1
                    print(f"     ✅ {asset_data['name']} (mesh)")
                else:
                    create_cube_fallback(asset_data, location, entry['index'])
                    failed_count += 1
                    print(f"     ❌ {asset_data['name']} (mesh not loaded)")
            else:
                create_cube_fallback(asset_data, location, entry['index'])
                failed_count += 1

        return loaded_count, failed_count

    except Exception as e:
        print(f"     ❌ Batch mesh/object loading failed: {e}")
        for entry in mesh_assets:
            create_cube_fallback(entry['asset_data'], entry['location'], entry['index'])
        return 0, len(mesh_assets)


def find_matching_mesh_names(asset_name, available_meshes):
    """Find meshes that match the asset name using multiple strategies."""
    asset_name_lower = asset_name.lower()
    matches = []
    
    # Strategy 1: Exact match
    for mesh_name in available_meshes:
        if mesh_name == asset_name:
            matches.insert(0, mesh_name)  # Prioritize exact matches
    
    # Strategy 2: Contains asset name
    for mesh_name in available_meshes:
        mesh_lower = mesh_name.lower()
        if asset_name_lower in mesh_lower and mesh_name not in matches:
            matches.append(mesh_name)
    
    # Strategy 3: Asset name contains mesh name
    for mesh_name in available_meshes:
        mesh_lower = mesh_name.lower()
        if mesh_lower in asset_name_lower and mesh_name not in matches:
            matches.append(mesh_name)
    
    # Strategy 4: Prefix matching with DATA_ handling
    for mesh_name in available_meshes:
        # Handle DATA_ prefix common in Blender exports
        clean_mesh = mesh_name.replace('DATA_', '').lower()
        if clean_mesh == asset_name_lower and mesh_name not in matches:
            matches.append(mesh_name)
    
    return matches


def create_collection_instance(asset_data, location, rotation=[0, 0, 0], scale_variation=True):
    """Create a collection instance object with rotation and scale variation."""
    collection_name = asset_data['collection_name']
    collection = bpy.data.collections[collection_name]

    # Create empty object to instance the collection (fast direct API)
    empty_obj = bpy.data.objects.new(f"{asset_data['name']}_instance_{asset_data['id']}", None)
    bpy.context.collection.objects.link(empty_obj)
    empty_obj.location = location

    # Set up collection instancing
    empty_obj.instance_type = 'COLLECTION'
    empty_obj.instance_collection = collection

    # Apply rotation
    if rotation and len(rotation) >= 3:
        empty_obj.rotation_euler = rotation

    # Apply subtle scale variation for realism (except for buildings)
    if scale_variation:
        category = asset_data.get('category', '').lower()
        if 'architecture' not in category and 'building' not in category:
            scale_factor = random.uniform(0.95, 1.05)
            empty_obj.scale = (scale_factor, scale_factor, scale_factor)

    # Store metadata
    empty_obj["asset_id"] = asset_data['id']
    empty_obj["asset_name"] = asset_data['name']
    empty_obj["collection_name"] = collection_name


def create_mesh_object(asset_data, location, mesh_name, rotation=[0, 0, 0], scale_variation=True):
    """Create a mesh object with rotation and scale variation."""
    mesh = bpy.data.meshes[mesh_name]
    obj = bpy.data.objects.new(f"{asset_data['name']}_{asset_data['id']}", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = location

    # Apply rotation
    if rotation and len(rotation) >= 3:
        obj.rotation_euler = rotation

    # Apply subtle scale variation for realism (except for buildings)
    if scale_variation:
        category = asset_data.get('category', '').lower()
        if 'architecture' not in category and 'building' not in category:
            scale_factor = random.uniform(0.95, 1.05)
            obj.scale = (scale_factor, scale_factor, scale_factor)

    # Store metadata
    obj["asset_id"] = asset_data['id']
    obj["asset_name"] = asset_data['name']
    obj["mesh_name"] = mesh_name


def create_cube_fallback(asset_data, location, index):
    """Create a cube fallback when asset loading fails (fast direct API)."""
    # Define cube geometry
    vertices = [
        (-1, -1, -1), (-1, -1, 1), (-1, 1, -1), (-1, 1, 1),
        (1, -1, -1), (1, -1, 1), (1, 1, -1), (1, 1, 1)
    ]
    edges = []
    faces = [
        (0, 1, 3, 2), (2, 3, 7, 6), (6, 7, 5, 4),
        (4, 5, 1, 0), (2, 6, 4, 0), (7, 3, 1, 5)
    ]

    # Create mesh and object
    mesh = bpy.data.meshes.new(f"Fallback_Cube_{index}")
    mesh.from_pydata(vertices, edges, faces)
    mesh.update()

    obj = bpy.data.objects.new(f"{asset_data['name']}_cube_{index}", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = location

    # Store metadata
    obj["asset_id"] = asset_data['id']
    obj["asset_name"] = asset_data['name']
    obj["asset_index"] = index


def get_asset_recommendations(prompt, style, available_assets, count):
    """
    Get AI recommendations for which assets to use without generating the full scene.
    Enhanced to filter visual assets and use asset IDs.
    """
    # Filter for visual assets first
    filtered_assets = filter_visual_assets(available_assets)
    
    if not filtered_assets:
        return []
    
    # Simple keyword-based matching as fallback
    keywords = prompt.lower().split()
    style_lower = style.lower()
    
    scored_assets = []
    
    for asset in filtered_assets:
        score = 0
        
        # Score based on name matching keywords
        asset_name = asset['name'].lower()
        for keyword in keywords:
            if keyword in asset_name:
                score += 2
        
        # Score based on category relevance
        if any(keyword in asset['category'].lower() for keyword in keywords):
            score += 3
        
        # Score based on style matching
        if asset.get('primary_style') and style_lower in asset['primary_style'].lower():
            score += 5
        
        # Prefer higher quality assets but not exclusively
        quality_scores = {'low': 1, 'medium': 2, 'high': 3, 'ultra': 4}
        score += quality_scores.get(asset.get('quality_tier', 'medium'), 2)
        
        # Prefer assets with reasonable polygon counts (not too simple, not too complex)
        poly_count = asset.get('polygon_count', 0)
        if 100 <= poly_count <= 5000:
            score += 2
        elif poly_count > 5000:
            score += 1
        
        scored_assets.append((asset, score))
    
    # Sort by score and return top assets
    scored_assets.sort(key=lambda x: x[1], reverse=True)
    return [asset for asset, score in scored_assets[:count * 2]]  # Return more options than needed