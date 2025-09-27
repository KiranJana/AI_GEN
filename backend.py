# backend.py - Enhanced with robust asset loading

import bpy
import random
import json
import os

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

API_KEY = "" # Make sure your key is pasted here

def call_ai_service(prompt, style, count):
    """Original AI service call for basic scene generation."""
    if not genai:
        print("Google Generative AI library not found. Returning mock data.")
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 1) for _ in range(count)]}
    if API_KEY == "YOUR_GEMINI_API_KEY" or not API_KEY:
        print("Gemini API Key not set. Please add it to the script.")
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 1) for _ in range(count)]}

    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        generation_config = genai.GenerationConfig(response_mime_type="application/json")
        
        # Improved prompt with examples and a recipe for success
        full_prompt = (
            "You are an expert Blender scene layout assistant. Your task is to generate a list of 3D coordinates in a JSON format. "
            "The JSON object must contain a single key: 'locations'. The value of 'locations' must be a list of coordinate arrays. "
            "Each coordinate array MUST be in the format [X, Y, Z], and the Z value should always be 1.0. "
            "\n"
            "Analyze the user's prompt to determine the best spatial arrangement. "
            "For example, for a 'circle', the coordinates should be arranged evenly around a central point. You can calculate circular coordinates using the formula: "
            "X = radius * cos(angle), Y = radius * sin(angle). "
            "For a 'line' or 'street', they should be arranged along an axis. For a 'forest', they should be scattered with some randomness. "
            "\n"
            f"User Request: Create a '{style}' scene based on the prompt '{prompt}' with exactly {count} objects."
        )
        
        response = model.generate_content(full_prompt, generation_config=generation_config)
        
        print("--- Raw AI Response ---"); print(response.text); print("-----------------------")
        
        return json.loads(response.text)
    except Exception as e:
        print(f"An error occurred with the Gemini API: {e}")
        return None


def call_ai_service_with_assets(prompt, style, count, available_assets):
    """Enhanced AI service call that uses asset intelligence with ID-based selection."""
    if not genai:
        print("Google Generative AI library not found. Using asset-aware mock data.")
        return generate_asset_aware_mock_data(available_assets, count)
    
    if API_KEY == "YOUR_GEMINI_API_KEY" or not API_KEY:
        print("Gemini API Key not set. Using asset-aware mock data.")
        return generate_asset_aware_mock_data(available_assets, count)

    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        generation_config = genai.GenerationConfig(response_mime_type="application/json")
        
        # Filter out character rig controls and other non-visual assets
        filtered_assets = filter_visual_assets(available_assets)
        
        if not filtered_assets:
            print("No suitable visual assets found, falling back to mock data")
            return generate_asset_aware_mock_data(available_assets, count)
        
        # Create asset information for the AI (limit to reasonable number)
        asset_info = []
        for asset in filtered_assets[:30]:  # Limit to first 30 good assets
            asset_info.append({
                'id': asset['id'],  # Include asset ID for robust lookup
                'name': asset['name'],
                'category': asset['category'],
                'quality': asset['quality_tier'],
                'complexity': asset['complexity_score'],
                'polygons': asset['polygon_count'],
                'style': asset.get('primary_style', 'unknown')
            })
        
        # Enhanced prompt with asset intelligence
        full_prompt = (
            "You are an expert Blender scene layout assistant with access to a database of 3D assets. "
            "Your task is to generate a scene layout in JSON format that intelligently uses available assets. "
            "\n"
            "REQUIRED OUTPUT FORMAT:\n"
            "{\n"
            '  "locations": [[X, Y, Z], [X, Y, Z], ...],\n'
            '  "selected_asset_ids": [123, 456, 789, ...],\n'
            '  "reasoning": "Brief explanation of asset choices and layout"\n'
            "}\n"
            "\n"
            "AVAILABLE ASSETS (these are actual 3D objects, vehicles, props, and lighting):\n"
            f"{json.dumps(asset_info, indent=2)}\n"
            "\n"
            "SCENE REQUIREMENTS:\n"
            f"- Style: {style}\n"
            f"- User Prompt: {prompt}\n"
            f"- Number of Objects: {count}\n"
            "\n"
            "INSTRUCTIONS:\n"
            "1. Select ONLY from the available assets listed above using their ID numbers\n"
            "2. Choose assets that make sense for the scene (avoid character controls, rigs, etc.)\n"
            "3. Create realistic 3D coordinates for each selected asset\n"
            "4. Consider asset complexity for proper spacing\n"
            "5. Ensure the layout makes sense for the requested scene type\n"
            "6. Z coordinates should be appropriate (ground objects = 0, elevated objects higher)\n"
            "7. Focus on vehicles, props, lighting, and architecture assets\n"
            "8. Return asset IDs in selected_asset_ids array, not names\n"
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
        
        for asset_id in selected_asset_ids:
            if asset_id in asset_id_map:
                selected_assets.append(asset_id_map[asset_id])
            else:
                # If AI provided invalid ID, select a random valid asset
                replacement = random.choice(filtered_assets)
                selected_assets.append(replacement)
                print(f"Replaced invalid asset ID {asset_id} with {replacement['name']} (ID: {replacement['id']})")
        
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
        
        # Trim to exact count
        ai_response['locations'] = locations[:count]
        ai_response['selected_assets'] = selected_assets[:count]  # Full asset data, not just IDs
        
        return ai_response
        
    except Exception as e:
        print(f"An error occurred with the enhanced Gemini API: {e}")
        print("Falling back to asset-aware mock data...")
        return generate_asset_aware_mock_data(available_assets, count)


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
    """Optimized scene builder with batched asset loading for performance."""
    # Clear existing mesh objects
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.select_by_type(type='MESH')
    bpy.ops.object.delete()

    if not instructions or not isinstance(instructions, dict) or "locations" not in instructions:
        print("Safeguard: AI response was missing the 'locations' key or was not a dictionary.")
        return

    locations = instructions["locations"]
    selected_assets = instructions.get("selected_assets", [])
    reasoning = instructions.get("reasoning", "No reasoning provided")

    if not isinstance(locations, list):
        print(f"Safeguard: AI returned 'locations' as a {type(locations)}, but it must be a list.")
        return

    print(f"AI Reasoning: {reasoning}")
    
    if selected_assets:
        print(f"Building scene with {len(selected_assets)} selected assets...")
        
        # PERFORMANCE OPTIMIZATION: Group assets by blend file
        assets_by_file = group_assets_by_blend_file(selected_assets, locations)
        
        # Load assets in batches by file for optimal performance
        load_assets_optimized(assets_by_file)
    else:
        # Fallback to cubes if no assets
        for i, loc in enumerate(locations):
            if isinstance(loc, (list, tuple)) and len(loc) == 3:
                bpy.ops.mesh.primitive_cube_add(location=loc)
                obj = bpy.context.active_object
                obj.name = f"object_{i}"
                print(f"📦 Created cube at: {loc}")


def group_assets_by_blend_file(selected_assets, locations):
    """Group assets by their source .blend file for batch loading."""
    assets_by_file = {}
    
    for i, asset_data in enumerate(selected_assets):
        if not asset_data or i >= len(locations):
            continue
            
        location = locations[i]
        
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
                if collection_name in available_collections:
                    collections_to_load.append(collection_name)
                else:
                    print(f"     ⚠️  Collection '{collection_name}' not found")
            
            # Load all valid collections at once
            data_to.collections = collections_to_load
            print(f"     📦 Loading {len(collections_to_load)} collections in batch")
        
        # Create instances for successfully loaded collections
        loaded_count = 0
        failed_count = 0
        
        for entry in collection_assets:
            asset_data = entry['asset_data']
            collection_name = asset_data['collection_name']
            
            if collection_name in bpy.data.collections:
                # Create collection instance
                create_collection_instance(asset_data, entry['location'])
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
    """Load multiple meshes from a single file in one operation."""
    print(f"   Loading {len(mesh_assets)} meshes...")
    
    try:
        # Single file open operation for all meshes
        with bpy.data.libraries.load(blend_file, link=False) as (data_from, data_to):
            available_meshes = list(data_from.meshes)
            meshes_to_load = []
            asset_mesh_map = {}  # Map asset to mesh name
            
            # Find matching meshes for each asset
            for entry in mesh_assets:
                asset_data = entry['asset_data']
                asset_name = asset_data['name']
                
                # Find best matching mesh
                matching_meshes = find_matching_mesh_names(asset_name, available_meshes)
                
                if matching_meshes:
                    selected_mesh = matching_meshes[0]  # Take best match
                    meshes_to_load.append(selected_mesh)
                    asset_mesh_map[asset_data['id']] = selected_mesh
                    print(f"     🔗 {asset_name} -> {selected_mesh}")
                else:
                    print(f"     ⚠️  No mesh found for {asset_name}")
            
            # Load all meshes and materials at once
            data_to.meshes = list(set(meshes_to_load))  # Remove duplicates
            data_to.materials = data_from.materials
            print(f"     📦 Loading {len(set(meshes_to_load))} unique meshes in batch")
        
        # Create objects for successfully loaded meshes
        loaded_count = 0
        failed_count = 0
        
        for entry in mesh_assets:
            asset_data = entry['asset_data']
            asset_id = asset_data['id']
            
            if asset_id in asset_mesh_map:
                mesh_name = asset_mesh_map[asset_id]
                if mesh_name in bpy.data.meshes:
                    # Create mesh object
                    create_mesh_object(asset_data, entry['location'], mesh_name)
                    loaded_count += 1
                    print(f"     ✅ {asset_data['name']}")
                else:
                    create_cube_fallback(asset_data, entry['location'], entry['index'])
                    failed_count += 1
                    print(f"     ❌ {asset_data['name']} (mesh not loaded)")
            else:
                create_cube_fallback(asset_data, entry['location'], entry['index'])
                failed_count += 1
        
        return loaded_count, failed_count
        
    except Exception as e:
        print(f"     ❌ Batch mesh loading failed: {e}")
        # Create fallbacks for all
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


def create_collection_instance(asset_data, location):
    """Create a collection instance object."""
    collection_name = asset_data['collection_name']
    collection = bpy.data.collections[collection_name]
    
    # Create empty object to instance the collection
    bpy.ops.object.empty_add(location=location)
    empty_obj = bpy.context.active_object
    empty_obj.name = f"{asset_data['name']}_instance_{asset_data['id']}"
    
    # Set up collection instancing
    empty_obj.instance_type = 'COLLECTION'
    empty_obj.instance_collection = collection
    
    # Store metadata
    empty_obj["asset_id"] = asset_data['id']
    empty_obj["asset_name"] = asset_data['name']
    empty_obj["collection_name"] = collection_name


def create_mesh_object(asset_data, location, mesh_name):
    """Create a mesh object."""
    mesh = bpy.data.meshes[mesh_name]
    obj = bpy.data.objects.new(f"{asset_data['name']}_{asset_data['id']}", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    
    # Store metadata
    obj["asset_id"] = asset_data['id']
    obj["asset_name"] = asset_data['name']
    obj["mesh_name"] = mesh_name


def create_cube_fallback(asset_data, location, index):
    """Create a cube fallback when asset loading fails."""
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = f"{asset_data['name']}_cube_{index}"
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