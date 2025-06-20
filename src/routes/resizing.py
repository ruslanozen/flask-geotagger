from flask import Blueprint, request, jsonify, send_file, current_app
import os
import json
import uuid
import tempfile
import shutil
from werkzeug.utils import secure_filename
from PIL import Image
import zipfile

resizing_bp = Blueprint('resizing', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'heic', 'heif', 'webp'}

def allowed_file(filename):
    """Check if file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@resizing_bp.route('/process', methods=['POST'])
def process_images():
    """
    Resize images to the specified dimensions.
    
    Expects:
    - files: Image files to process
    - width: New width (optional)
    - height: New height (optional)
    - resize_mode: 'exact', 'fit', 'fill', or 'percentage'
    - percentage: Scale percentage if resize_mode is 'percentage'
    - output_format: Output format (jpeg, png, tiff)
    
    Returns:
    - JSON response with status and download URL
    """
    # Check if files were uploaded
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files[]')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    # Get resize parameters
    try:
        width = request.form.get('width')
        height = request.form.get('height')
        resize_mode = request.form.get('resize_mode', 'fit')
        percentage = request.form.get('percentage')
        
        # Convert to integers if provided
        width = int(width) if width else None
        height = int(height) if height else None
        percentage = int(percentage) if percentage else 100
        
        if resize_mode not in ['exact', 'fit', 'fill', 'percentage']:
            resize_mode = 'fit'
            
        # Validate parameters based on resize mode
        if resize_mode == 'percentage':
            if percentage <= 0 or percentage > 1000:
                return jsonify({'error': 'Percentage must be between 1 and 1000'}), 400
        elif resize_mode in ['exact', 'fit', 'fill']:
            if not width and not height:
                return jsonify({'error': 'Width or height must be provided'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid numeric parameters'}), 400
    
    # Get output format
    output_format = request.form.get('output_format', 'jpeg').lower()
    if output_format not in ['jpeg', 'png', 'tiff']:
        output_format = 'jpeg'
    
    # Create a unique session ID for this batch
    session_id = str(uuid.uuid4())
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], session_id)
    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
    
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(processed_folder, exist_ok=True)
    
    # Save uploaded files
    saved_files = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            saved_files.append(file_path)
    
    if not saved_files:
        return jsonify({'error': 'No valid image files provided'}), 400
    
    # Process files
    processed_files = []
    
    for file_path in saved_files:
        try:
            # Register HEIF opener if needed
            if file_path.lower().endswith(('.heic', '.heif')):
                try:
                    import pillow_heif
                    pillow_heif.register_heif_opener()
                except ImportError:
                    return jsonify({'error': 'HEIF/HEIC support not available'}), 500
            
            # Open image
            with Image.open(file_path) as img:
                # Get original dimensions
                orig_width, orig_height = img.size
                
                # Calculate new dimensions based on resize mode
                if resize_mode == 'percentage':
                    new_width = int(orig_width * percentage / 100)
                    new_height = int(orig_height * percentage / 100)
                elif resize_mode == 'exact':
                    new_width = width if width else orig_width
                    new_height = height if height else orig_height
                elif resize_mode == 'fit':
                    # Maintain aspect ratio, fit within dimensions
                    if width and height:
                        ratio = min(width / orig_width, height / orig_height)
                        new_width = int(orig_width * ratio)
                        new_height = int(orig_height * ratio)
                    elif width:
                        ratio = width / orig_width
                        new_width = width
                        new_height = int(orig_height * ratio)
                    elif height:
                        ratio = height / orig_height
                        new_width = int(orig_width * ratio)
                        new_height = height
                    else:
                        new_width, new_height = orig_width, orig_height
                elif resize_mode == 'fill':
                    # Maintain aspect ratio, fill dimensions (may crop)
                    if width and height:
                        ratio = max(width / orig_width, height / orig_height)
                        new_width = int(orig_width * ratio)
                        new_height = int(orig_height * ratio)
                    elif width:
                        ratio = width / orig_width
                        new_width = width
                        new_height = int(orig_height * ratio)
                    elif height:
                        ratio = height / orig_height
                        new_width = int(orig_width * ratio)
                        new_height = height
                    else:
                        new_width, new_height = orig_width, orig_height
                
                # Resize image
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # If fill mode and both dimensions specified, crop to fit
                if resize_mode == 'fill' and width and height:
                    left = (new_width - width) / 2
                    top = (new_height - height) / 2
                    right = (new_width + width) / 2
                    bottom = (new_height + height) / 2
                    resized_img = resized_img.crop((left, top, right, bottom))
                
                # Convert RGBA to RGB if saving as JPEG
                if output_format.lower() in ["jpeg", "jpg"] and resized_img.mode == "RGBA":
                    resized_img = resized_img.convert("RGB")
                
                # Save resized image
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(processed_folder, f"{base_name}.{output_format}")
                resized_img.save(output_path, output_format.upper())
                processed_files.append(output_path)
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    if not processed_files:
        return jsonify({'error': 'Failed to process any files'}), 500
    
    # Create a zip file if multiple files were processed
    if len(processed_files) > 1:
        zip_filename = f"resized_images_{session_id}.zip"
        zip_path = os.path.join(processed_folder, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in processed_files:
                zipf.write(file, os.path.basename(file))
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully resized {len(processed_files)} images',
            'download_url': f'/api/resizing/download/{session_id}/zip',
            'file_count': len(processed_files)
        })
    else:
        # Single file
        return jsonify({
            'status': 'success',
            'message': 'Successfully resized image',
            'download_url': f'/api/resizing/download/{session_id}/single',
            'file_count': 1
        })

@resizing_bp.route('/download/<session_id>/zip', methods=['GET'])
def download_zip(session_id):
    """Download processed images as a zip file."""
    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
    zip_path = os.path.join(processed_folder, f"resized_images_{session_id}.zip")
    
    if not os.path.exists(zip_path):
        return jsonify({'error': 'Zip file not found'}), 404
    
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"resized_images.zip",
        mimetype='application/zip'
    )

@resizing_bp.route('/download/<session_id>/single', methods=['GET'])
def download_single(session_id):
    """Download a single processed image."""
    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
    
    # Find the first file in the processed folder
    files = os.listdir(processed_folder)
    image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.tif'))]
    
    if not image_files:
        return jsonify({'error': 'Processed image not found'}), 404
    
    file_path = os.path.join(processed_folder, image_files[0])
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=image_files[0],
        mimetype=f'image/{os.path.splitext(image_files[0])[1][1:].lower()}'
    )

@resizing_bp.route('/cleanup/<session_id>', methods=['POST'])
def cleanup_session(session_id):
    """Clean up temporary files for a session."""
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], session_id)
    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
    
    # Clean up upload folder
    if os.path.exists(upload_folder):
        shutil.rmtree(upload_folder)
    
    # Clean up processed folder
    if os.path.exists(processed_folder):
        shutil.rmtree(processed_folder)
    
    return jsonify({'status': 'success', 'message': 'Session cleaned up'})
