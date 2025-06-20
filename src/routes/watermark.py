from flask import Blueprint, request, jsonify, send_file, current_app
import os
import json
import uuid
import tempfile
import shutil
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import zipfile

watermark_bp = Blueprint('watermark', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'heic', 'heif', 'webp'}

def allowed_file(filename):
    """Check if file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@watermark_bp.route('/process', methods=['POST'])
def process_images():
    """
    Apply watermark to images.
    
    Expects:
    - files: Image files to process
    - watermark_type: 'text' or 'image'
    - watermark_text: Text to use as watermark (if type is 'text')
    - watermark_image: Image file to use as watermark (if type is 'image')
    - position: 'center', 'top_left', 'top_right', 'bottom_left', 'bottom_right'
    - opacity: Watermark opacity (0-100)
    - size: Watermark size percentage (1-100)
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
    
    # Get watermark parameters
    watermark_type = request.form.get('watermark_type', 'text')
    watermark_text = request.form.get('watermark_text', '')
    position = request.form.get('position', 'bottom_right')
    
    try:
        opacity = int(request.form.get('opacity', 50))
        size = int(request.form.get('size', 30))
        
        # Validate parameters
        if opacity < 0 or opacity > 100:
            opacity = 50
        if size < 1 or size > 100:
            size = 30
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
    
    # Handle watermark image if provided
    watermark_img = None
    if watermark_type == 'image' and 'watermark_image' in request.files:
        wm_file = request.files['watermark_image']
        if wm_file and allowed_file(wm_file.filename):
            wm_path = os.path.join(upload_folder, 'watermark_' + secure_filename(wm_file.filename))
            wm_file.save(wm_path)
            try:
                watermark_img = Image.open(wm_path).convert('RGBA')
            except Exception as e:
                print(f"Error loading watermark image: {str(e)}")
                return jsonify({'error': 'Invalid watermark image'}), 400
    
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
                # Convert to RGBA for watermarking
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Create watermark layer
                watermark_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
                
                if watermark_type == 'text' and watermark_text:
                    # Create text watermark
                    draw = ImageDraw.Draw(watermark_layer)
                    
                    # Try to load a font, fall back to default if not available
                    try:
                        # Calculate font size based on image dimensions and size parameter
                        font_size = int(min(img.width, img.height) * size / 100)
                        font = ImageFont.truetype("Arial", font_size)
                    except IOError:
                        # Use default font
                        font = ImageFont.load_default()
                    
                    # Get text size
                    text_width, text_height = draw.textsize(watermark_text, font=font)
                    
                    # Calculate position
                    if position == 'center':
                        x = (img.width - text_width) // 2
                        y = (img.height - text_height) // 2
                    elif position == 'top_left':
                        x, y = 10, 10
                    elif position == 'top_right':
                        x, y = img.width - text_width - 10, 10
                    elif position == 'bottom_left':
                        x, y = 10, img.height - text_height - 10
                    else:  # bottom_right
                        x, y = img.width - text_width - 10, img.height - text_height - 10
                    
                    # Draw text with shadow for better visibility
                    draw.text((x+2, y+2), watermark_text, font=font, fill=(0, 0, 0, int(255 * opacity / 100)))
                    draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, int(255 * opacity / 100)))
                
                elif watermark_type == 'image' and watermark_img:
                    # Resize watermark image based on size parameter
                    wm_width = int(img.width * size / 100)
                    wm_height = int(watermark_img.height * wm_width / watermark_img.width)
                    
                    # Ensure watermark isn't larger than the image
                    if wm_width > img.width:
                        wm_width = img.width
                        wm_height = int(watermark_img.height * wm_width / watermark_img.width)
                    if wm_height > img.height:
                        wm_height = img.height
                        wm_width = int(watermark_img.width * wm_height / watermark_img.height)
                    
                    resized_wm = watermark_img.resize((wm_width, wm_height), Image.LANCZOS)
                    
                    # Apply opacity
                    if opacity < 100:
                        alpha = resized_wm.split()[3]
                        alpha = alpha.point(lambda p: p * opacity / 100)
                        resized_wm.putalpha(alpha)
                    
                    # Calculate position
                    if position == 'center':
                        x = (img.width - wm_width) // 2
                        y = (img.height - wm_height) // 2
                    elif position == 'top_left':
                        x, y = 10, 10
                    elif position == 'top_right':
                        x, y = img.width - wm_width - 10, 10
                    elif position == 'bottom_left':
                        x, y = 10, img.height - wm_height - 10
                    else:  # bottom_right
                        x, y = img.width - wm_width - 10, img.height - wm_height - 10
                    
                    # Paste watermark onto layer
                    watermark_layer.paste(resized_wm, (x, y), resized_wm)
                
                # Composite the watermark layer with the original image
                watermarked_img = Image.alpha_composite(img, watermark_layer)
                
                # Convert back to RGB if saving as JPEG
                if output_format.lower() in ["jpeg", "jpg"]:
                    watermarked_img = watermarked_img.convert("RGB")
                
                # Save watermarked image
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(processed_folder, f"{base_name}.{output_format}")
                watermarked_img.save(output_path, output_format.upper())
                processed_files.append(output_path)
                
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    if not processed_files:
        return jsonify({'error': 'Failed to process any files'}), 500
    
    # Create a zip file if multiple files were processed
    if len(processed_files) > 1:
        zip_filename = f"watermarked_images_{session_id}.zip"
        zip_path = os.path.join(processed_folder, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in processed_files:
                zipf.write(file, os.path.basename(file))
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully watermarked {len(processed_files)} images',
            'download_url': f'/api/watermark/download/{session_id}/zip',
            'file_count': len(processed_files)
        })
    else:
        # Single file
        return jsonify({
            'status': 'success',
            'message': 'Successfully watermarked image',
            'download_url': f'/api/watermark/download/{session_id}/single',
            'file_count': 1
        })

@watermark_bp.route('/download/<session_id>/zip', methods=['GET'])
def download_zip(session_id):
    """Download processed images as a zip file."""
    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
    zip_path = os.path.join(processed_folder, f"watermarked_images_{session_id}.zip")
    
    if not os.path.exists(zip_path):
        return jsonify({'error': 'Zip file not found'}), 404
    
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"watermarked_images.zip",
        mimetype='application/zip'
    )

@watermark_bp.route('/download/<session_id>/single', methods=['GET'])
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

@watermark_bp.route('/cleanup/<session_id>', methods=['POST'])
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
