from flask import Blueprint, request, jsonify, send_file, current_app
import os
import json
import uuid
import tempfile
import shutil
from werkzeug.utils import secure_filename
from PIL import Image
import zipfile

conversion_bp = Blueprint('conversion', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'heic', 'heif', 'webp'}

def allowed_file(filename):
    """Check if file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@conversion_bp.route('/process', methods=['POST'])
def process_images():
    """
    Convert images to the specified format.
    
    Expects:
    - files: Image files to process
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
            
            # Open and convert image
            with Image.open(file_path) as img:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(processed_folder, f"{base_name}.{output_format}")
                
                # Convert RGBA to RGB if saving as JPEG
                if output_format.lower() in ["jpeg", "jpg"] and img.mode == "RGBA":
                    img = img.convert("RGB")
                
                # Save image
                img.save(output_path, output_format.upper())
                processed_files.append(output_path)
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    if not processed_files:
        return jsonify({'error': 'Failed to process any files'}), 500
    
    # Create a zip file if multiple files were processed
    if len(processed_files) > 1:
        zip_filename = f"converted_images_{session_id}.zip"
        zip_path = os.path.join(processed_folder, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in processed_files:
                zipf.write(file, os.path.basename(file))
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully converted {len(processed_files)} images',
            'download_url': f'/api/conversion/download/{session_id}/zip',
            'file_count': len(processed_files)
        })
    else:
        # Single file
        return jsonify({
            'status': 'success',
            'message': 'Successfully converted image',
            'download_url': f'/api/conversion/download/{session_id}/single',
            'file_count': 1
        })

@conversion_bp.route('/download/<session_id>/zip', methods=['GET'])
def download_zip(session_id):
    """Download processed images as a zip file."""
    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
    zip_path = os.path.join(processed_folder, f"converted_images_{session_id}.zip")
    
    if not os.path.exists(zip_path):
        return jsonify({'error': 'Zip file not found'}), 404
    
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"converted_images.zip",
        mimetype='application/zip'
    )

@conversion_bp.route('/download/<session_id>/single', methods=['GET'])
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

@conversion_bp.route('/cleanup/<session_id>', methods=['POST'])
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
