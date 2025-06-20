from flask import Blueprint, request, jsonify, current_app
import os
import json

presets_bp = Blueprint('presets', __name__)

@presets_bp.route('/city', methods=['GET'])
def get_city_presets():
    """
    Get all city presets.
    
    Returns:
    - JSON response with city presets
    """
    try:
        # Check if city_presets.json exists in the static/data folder
        presets_path = os.path.join(current_app.static_folder, 'data', 'city_presets.json')
        
        if not os.path.exists(presets_path):
            # Return empty presets if file doesn't exist
            return jsonify({
                'version': '1.0',
                'presets': []
            })
        
        # Read presets from file
        with open(presets_path, 'r') as f:
            presets = json.load(f)
        
        return jsonify(presets)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@presets_bp.route('/client', methods=['GET'])
def get_client_presets():
    """
    Get all client presets.
    
    Returns:
    - JSON response with client presets
    """
    try:
        # Check if client_presets.json exists in the static/data folder
        presets_path = os.path.join(current_app.static_folder, 'data', 'client_presets.json')
        
        if not os.path.exists(presets_path):
            # Return empty presets if file doesn't exist
            return jsonify({
                'version': '1.0',
                'presets': []
            })
        
        # Read presets from file
        with open(presets_path, 'r') as f:
            presets = json.load(f)
        
        return jsonify(presets)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@presets_bp.route('/city', methods=['POST'])
def update_city_presets():
    """
    Update city presets.
    
    Expects:
    - presets: JSON object with city presets
    
    Returns:
    - JSON response with status
    """
    try:
        # Get presets from request
        presets = request.json
        
        if not presets:
            return jsonify({'error': 'No presets provided'}), 400
        
        # Validate presets structure
        if 'version' not in presets or 'presets' not in presets:
            return jsonify({'error': 'Invalid presets format'}), 400
        
        # Save presets to file
        presets_path = os.path.join(current_app.static_folder, 'data', 'city_presets.json')
        
        with open(presets_path, 'w') as f:
            json.dump(presets, f, indent=2)
        
        return jsonify({'status': 'success', 'message': 'City presets updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@presets_bp.route('/client', methods=['POST'])
def update_client_presets():
    """
    Update client presets.
    
    Expects:
    - presets: JSON object with client presets
    
    Returns:
    - JSON response with status
    """
    try:
        # Get presets from request
        presets = request.json
        
        if not presets:
            return jsonify({'error': 'No presets provided'}), 400
        
        # Validate presets structure
        if 'version' not in presets or 'presets' not in presets:
            return jsonify({'error': 'Invalid presets format'}), 400
        
        # Save presets to file
        presets_path = os.path.join(current_app.static_folder, 'data', 'client_presets.json')
        
        with open(presets_path, 'w') as f:
            json.dump(presets, f, indent=2)
        
        return jsonify({'status': 'success', 'message': 'Client presets updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
