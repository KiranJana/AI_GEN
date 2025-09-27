# backend.py

import bpy
import random
import json

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
    """Enhanced AI service call that uses asset intelligence."""
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
        
        # Create asset information for the AI
        asset_info = []
        for asset in available_assets[:20]:  # Limit to first 20 assets for prompt size
            asset_info.append({
                'name': asset['name'],
                'category': asset['category'],
                'quality': asset['quality_tier'],
                'complexity': asset['complexity_score'],
                'dimensions': [asset['width'], asset['height'], asset['depth']],
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
            '  "selected_assets": ["asset_name_1", "asset_name_2", ...],\n'
            '  "reasoning": "Brief explanation of asset choices and layout"\n'
            "}\n"
            "\n"
            "AVAILABLE ASSETS:\n"
            f"{json.dumps(asset_info, indent=2)}\n"
            "\n"
            "SCENE REQUIREMENTS:\n"
            f"- Style: {style}\n"
            f"- User Prompt: {prompt}\n"
            f"- Number of Objects: {count}\n"
            "\n"
            "INSTRUCTIONS:\n"
            "1. Select appropriate assets from the available list that match the style and prompt\n"
            "2. Create realistic 3D coordinates for each selected asset\n"
            "3. Consider asset dimensions for proper spacing\n"
            "4. Ensure the layout makes sense for the requested scene type\n"
            "5. Provide brief reasoning for your choices\n"
            "\n"
            "The Z coordinates should be appropriate for the asset type (e.g., buildings on ground = 0, floating objects higher)."
        )
        
        response = model.generate_content(full_prompt, generation_config=generation_config)
        
        print("--- Enhanced AI Response with Assets ---")
        print(response.text)
        print("----------------------------------------")
        
        ai_response = json.loads(response.text)
        
        # Validate and enhance the response
        if 'locations' not in ai_response:
            raise ValueError("AI response missing 'locations' key")
        
        if 'selected_assets' not in ai_response:
            ai_response['selected_assets'] = [f"asset_{i}" for i in range(len(ai_response['locations']))]
        
        # Ensure we have the right number of objects
        locations = ai_response['locations']
        selected_assets = ai_response['selected_assets']
        
        # Pad or trim to match requested count
        while len(locations) < count:
            # Add more locations with random selection from available assets
            random_asset = random.choice(available_assets)
            locations.append([
                random.uniform(-10, 10),
                random.uniform(-10, 10),
                0.0
            ])
            selected_assets.append(random_asset['name'])
        
        # Trim if too many
        ai_response['locations'] = locations[:count]
        ai_response['selected_assets'] = selected_assets[:count]
        
        return ai_response
        
    except Exception as e:
        print(f"An error occurred with the enhanced Gemini API: {e}")
        print("Falling back to asset-aware mock data...")
        return generate_asset_aware_mock_data(available_assets, count)


def generate_asset_aware_mock_data(available_assets, count):
    """Generate mock data that's aware of available assets."""
    if not available_assets:
        return {"locations": [(random.uniform(-5, 5), random.uniform(-5, 5), 0) for _ in range(count)]}
    
    selected_assets = []
    locations = []
    
    for i in range(count):
        # Randomly select from available assets
        asset = random.choice(available_assets)
        selected_assets.append(asset['name'])
        
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
        "selected_assets": selected_assets,
        "reasoning": f"Mock selection from {len(available_assets)} available assets with category-aware placement"
    }


def build_scene_from_instructions(instructions):
    """Enhanced scene builder that can use asset intelligence."""
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
        print(f"Selected Assets: {selected_assets}")

    for i, loc in enumerate(locations):
        if not isinstance(loc, (list, tuple)) or len(loc) != 3:
            print(f"Safeguard: Skipping invalid location at index {i}. Expected 3 coordinates, but got {loc}")
            continue
        
        if not all(isinstance(item, (int, float)) for item in loc):
            print(f"Safeguard: Skipping invalid location at index {i}. Contains non-numeric values: {loc}")
            continue
        
        # Create object (for now still using cubes, but could be enhanced to load actual assets)
        bpy.ops.mesh.primitive_cube_add(location=loc)
        
        # Name the object based on selected asset if available
        if i < len(selected_assets) and selected_assets[i]:
            obj = bpy.context.active_object
            obj.name = f"{selected_assets[i]}_{i}"
            
            # Add custom properties to track asset info
            obj["asset_name"] = selected_assets[i]
            obj["asset_index"] = i
        
        print(f"Placed object at: {loc}" + (f" (Asset: {selected_assets[i]})" if i < len(selected_assets) else ""))


def load_actual_asset(asset_data, location):
    """
    Future enhancement: Load actual asset from blend file.
    This would replace the cube creation with actual asset loading.
    """
    # This is a placeholder for future asset loading functionality
    # Would involve:
    # 1. Opening the asset's blend file
    # 2. Appending/linking the asset
    # 3. Positioning it at the specified location
    # 4. Applying any material variations
    
    asset_path = asset_data.get('blend_file_path')
    collection_name = asset_data.get('collection_name')
    
    if asset_path and collection_name:
        try:
            # Example of how asset loading might work:
            # bpy.ops.wm.append(
            #     filepath=os.path.join(asset_path, "Collection", collection_name),
            #     directory=os.path.join(asset_path, "Collection"),
            #     filename=collection_name
            # )
            
            # Position the loaded asset
            # if bpy.context.selected_objects:
            #     obj = bpy.context.selected_objects[0]
            #     obj.location = location
            
            print(f"Would load asset: {collection_name} from {asset_path}")
            
        except Exception as e:
            print(f"Failed to load asset {collection_name}: {e}")
            # Fallback to cube
            bpy.ops.mesh.primitive_cube_add(location=location)
    else:
        # Fallback to cube
        bpy.ops.mesh.primitive_cube_add(location=location)


def get_asset_recommendations(prompt, style, available_assets, count):
    """
    Get AI recommendations for which assets to use without generating the full scene.
    Useful for preview functionality.
    """
    if not available_assets:
        return []
    
    # Simple keyword-based matching as fallback
    keywords = prompt.lower().split()
    style_lower = style.lower()
    
    scored_assets = []
    
    for asset in available_assets:
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
        
        # Prefer higher quality assets
        quality_scores = {'low': 1, 'medium': 2, 'high': 3, 'ultra': 4}
        score += quality_scores.get(asset.get('quality_tier', 'medium'), 2)
        
        scored_assets.append((asset, score))
    
    # Sort by score and return top assets
    scored_assets.sort(key=lambda x: x[1], reverse=True)
    return [asset for asset, score in scored_assets[:count * 2]]  # Return more options than needed

