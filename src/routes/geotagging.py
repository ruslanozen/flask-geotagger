from flask import Blueprint, request, jsonify, send_file, current_app, url_for
import os
import json
import uuid
import tempfile
import shutil
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError
import piexif
import datetime
import subprocess
import zipfile
import random
import pillow_heif
import threading

geotagging_bp = Blueprint('geotagging', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'heic', 'heif', 'webp'}

# Helper to flatten nested ExifTool JSON output for easier processing
def flatten_exiftool_metadata(exiftool_dict):
    """Flattens the grouped ExifTool metadata into a single dictionary with Group:TagName keys."""
    flattened = {}
    if not isinstance(exiftool_dict, dict):
        return flattened

    for group, tags in exiftool_dict.items():
        if isinstance(tags, dict):
            for tag_name, value in tags.items():
                flattened[f"{group}:{tag_name}"] = value
        # Handle cases where a group might directly contain a list (e.g., 'Keywords' under 'IPTC' sometimes)
        elif isinstance(tags, list):
            # ExifTool expects multi-valued tags like 'Keywords' to be specified multiple times with '-tag=value'
            # For simplicity, we'll store them as a list here and handle the iteration during exiftool_args generation
            flattened[group] = tags 
        else: # For single tags directly under root, if any (less common with -G1 output)
            flattened[group] = tags
    return flattened

def allowed_file(filename):
    """Check if file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_coordinate(value, precision=10):
    """Format coordinate value with high precision."""
    return f"{value:.{precision}f}"

def is_point_in_quadrilateral(point, quad):
    """
    Check if a point is inside a quadrilateral using the ray casting algorithm.
    Improved version with better handling of edge cases.
    
    Args:
        point (tuple): (lat, lng) of the point to check
        quad (list): List of (lat, lng) tuples representing the quadrilateral vertices
        
    Returns:
        bool: True if the point is inside the quadrilateral, False otherwise
    """
    lat, lng = point
    n = len(quad)
    
    # Handle edge cases
    if n < 3:  # Need at least 3 points to form a polygon
        return False
        
    inside = False
    j = n - 1
    
    for i in range(n):
        if ((quad[i][0] > lat) != (quad[j][0] > lat) and
            (lng < (quad[j][1] - quad[i][1]) * (lat - quad[i][0]) /
             (quad[j][0] - quad[i][0]) + quad[i][1])):
            inside = not inside
        j = i
        
    return inside

def generate_random_coordinates_in_quadrilateral(preset):
    """
    Generate random coordinates strictly within the quadrilateral defined by the preset boundaries.
    Uses rejection sampling to ensure points are inside the quadrilateral.
    
    Args:
        preset (dict): City preset with boundary coordinates
        
    Returns:
        tuple: (latitude, longitude) or (None, None) if boundaries not found
    """
    import random
    
    if not preset or "boundaries" not in preset:
        return None, None
        
    boundaries = preset["boundaries"]
    
    # Extract the four corners of the quadrilateral
    quad = [
        (boundaries["top_left"]["lat"], boundaries["top_left"]["lng"]),
        (boundaries["top_right"]["lat"], boundaries["top_right"]["lng"]),
        (boundaries["bottom_right"]["lat"], boundaries["bottom_right"]["lng"]),
        (boundaries["bottom_left"]["lat"], boundaries["bottom_left"]["lng"])
    ]
    
    # Find the bounding box of the quadrilateral
    lat_min = min(point[0] for point in quad)
    lat_max = max(point[0] for point in quad)
    lng_min = min(point[1] for point in quad)
    lng_max = max(point[1] for point in quad)
    
    # Use rejection sampling to find a point inside the quadrilateral
    max_attempts = 1000  # Increased from 100 to 1000 for better coverage
    for _ in range(max_attempts):
        # Generate a random point within the bounding box
        random_lat = random.uniform(lat_min, lat_max)
        random_lng = random.uniform(lng_min, lng_max)
        
        # Check if the point is inside the quadrilateral
        if is_point_in_quadrilateral((random_lat, random_lng), quad):
            # Add a small random offset to avoid always getting points near the edges
            random_lat += random.uniform(-0.0001, 0.0001)
            random_lng += random.uniform(-0.0001, 0.0001)
            return random_lat, random_lng
    
    # If we couldn't find a point after max_attempts, use the center as fallback
    # but add a small random offset to avoid always using the exact center
    center_lat = preset["center"]["lat"]
    center_lng = preset["center"]["lng"]
    return (
        center_lat + random.uniform(-0.0001, 0.0001),
        center_lng + random.uniform(-0.0001, 0.0001)
    )

def process_image_with_exiftool(input_path, output_path, exif_data):
    """
    Process a single image file with ExifTool to add EXIF data.

    Args:
        input_path (str): Path to the input image file
        output_path (str): Path to save the processed image
        exif_data (dict): Flattened dictionary of ExifTool tags (e.g., {"GPS:GPSLatitude": 12.34})
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Copy the file first to the output path to modify it in place with exiftool
        shutil.copy2(input_path, output_path)
        
        # Base exiftool command with overwrite_original and UTF8 options
        # -m: ignore minor warnings
        exif_args = ["exiftool", "-overwrite_original", "-codedcharacterset=utf8", "-m"]
        
        # Add metadata arguments based on the structured exif_data
        for exiftool_tag, value in exif_data.items():
            # Skip if value is None, empty string, or empty list
            if value is None or (isinstance(value, (str, list)) and not value):
                continue

            # Special handling for multi-value tags (like Keywords, Subject)
            if isinstance(value, list):
                for item in value:
                    exif_args.append(f"-{exiftool_tag}={item}")
            else:
                exif_args.append(f"-{exiftool_tag}={value}")
        
        # Add the output file path as the last argument
        exif_args.append(output_path)
        
        current_app.logger.info(f"Executing ExifTool command: {' '.join(exif_args)}")
        # Execute the exiftool command
        process = subprocess.run(exif_args, capture_output=True, text=True, check=False, encoding='utf-8')
        
        if process.returncode != 0:
            current_app.logger.error(f"ExifTool write error (return code {process.returncode}): {process.stderr.strip()}")
            current_app.logger.error(f"ExifTool stdout: {process.stdout.strip()}")
            return False
        
        current_app.logger.info(f"ExifTool write successful for {output_path}")
        current_app.logger.info(f"ExifTool stdout: {process.stdout.strip()}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error processing image with ExifTool: {e}")
        return False

progress_lock = threading.Lock()

def set_progress(session_id, percent):
    progress_file = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id, 'progress.json')
    with progress_lock:
        with open(progress_file, 'w') as f:
            json.dump({'progress': percent}, f)

def get_progress(session_id):
    progress_file = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id, 'progress.json')
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            try:
                data = json.load(f)
                return data.get('progress', 0)
            except Exception:
                return 0
    return 0

@geotagging_bp.route('/progress/<session_id>', methods=['GET'])
def get_progress_endpoint(session_id):
    percent = get_progress(session_id)
    return jsonify({'progress': percent})

@geotagging_bp.route('/process', methods=['POST'])
def process_images():
    """
    Process images with geotagging information.
    
    Expects:
    - files: Image files to process
    - exif_data: JSON string with EXIF data to apply (from geotagging form)
    - all_metadata: JSON string with comprehensive metadata from the /exif page (optional)
    - output_format: Output format (jpeg, png, tiff)
    
    Returns:
    - JSON response with status and download URL
    """
    try:
        # Check if files were uploaded
        if 'files[]' not in request.files:
            return jsonify({
                'error': 'No files provided',
                'details': 'The request did not contain any files'
            }), 400
        
        files = request.files.getlist('files[]')
        file_paths = request.form.getlist('file_paths[]')

        if not files or files[0].filename == '':
            return jsonify({
                'error': 'No files selected',
                'details': 'The file list is empty or the first file has no filename'
            }), 400

        # Ensure the number of files and paths match
        if len(files) != len(file_paths):
            return jsonify({
                'error': 'Mismatch between number of files and paths',
                'details': f'Received {len(files)} files but {len(file_paths)} paths'
            }), 400

        # Get EXIF data from form (this is the data from the geotagging form itself)
        exif_data_str = request.form.get('exif_data', '{}')
        try:
            exif_data = json.loads(exif_data_str)
        except json.JSONDecodeError as e:
            return jsonify({
                'error': 'Invalid EXIF data format',
                'details': str(e)
            }), 400
        
        # Get output format
        output_format = request.form.get('output_format', 'jpeg').lower()
        if output_format not in ['jpeg', 'png', 'tiff']:
            output_format = 'jpeg'
        
        # Create a unique session ID for this batch
        session_id = str(uuid.uuid4())
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], session_id)
        processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
        
        # Create the base session directories
        try:
            os.makedirs(upload_folder, exist_ok=True)
            os.makedirs(processed_folder, exist_ok=True)
        except Exception as e:
            return jsonify({
                'error': 'Failed to create session directories',
                'details': str(e)
            }), 500
        
        # Save uploaded files while preserving folder structure
        saved_files_with_paths = []
        for i, file in enumerate(files):
            if file and allowed_file(file.filename):
                try:
                    # Use the provided relative path (original folder structure)
                    original_relative_path = file_paths[i]
                    original_filename = file.filename

                    # Generate a unique, short filename for the temporary uploaded file
                    # This avoids issues with long paths and special characters in temp dir
                    unique_temp_filename = f"{uuid.uuid4()}{os.path.splitext(original_filename)[1].lower()}"
                    upload_path = os.path.join(upload_folder, unique_temp_filename)
                    
                    # Create parent directories if they don't exist (for the session_id folder)
                    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                    
                    # Save the file
                    file.save(upload_path)
                    current_app.logger.info(f"Saved uploaded file to: {upload_path}. Exists: {os.path.exists(upload_path)}")
                    saved_files_with_paths.append({
                        'original_relative_path': original_relative_path, # Store original path for later reference
                        'uploaded_temp_path': upload_path, # Path to the temporarily saved file
                        'original_filename': original_filename # Store original filename
                    })
                except Exception as e:
                    current_app.logger.error(f"Error saving file {file.filename}: {str(e)}")
                    continue
        
        if not saved_files_with_paths:
            return jsonify({
                'error': 'No valid image files provided',
                'details': 'None of the uploaded files could be saved successfully'
            }), 400
        
        # Process files while preserving folder structure
        processed_files_with_paths = []
        processing_errors = []
        
        # Check if using random coordinates for bulk processing
        use_random = exif_data.get("use_random_coordinates", False)
        
        total_files = len(saved_files_with_paths)
        for idx, item in enumerate(saved_files_with_paths):
            original_relative_path = item['original_relative_path']
            uploaded_file_path = item['uploaded_temp_path']
            original_filename = item['original_filename']
            temp_jpeg_path = None # Initialize for cleanup

            try:
                # Initialize current file's random lat/lng, even if not used, to prevent NameError
                current_file_random_lat = None
                current_file_random_lng = None

                # Determine coordinates based on input (explicit lat/lng take precedence over preset)
                # Note: `lat` and `lng` are from the form for the whole batch.
                # If individual lat/lng are needed per image, the frontend must provide them.
                # For now, assuming batch lat/lng or preset applies to all.
                if exif_data.get('GPSLatitude') is not None and exif_data.get('GPSLongitude') is not None:
                    try:
                        current_file_random_lat = float(exif_data['GPSLatitude'])
                        current_file_random_lng = float(exif_data['GPSLongitude'])
                    except ValueError:
                        processing_errors.append(f'Invalid latitude or longitude format for {original_filename}.')
                        continue # Skip this file
                elif use_random and exif_data.get("preset"): # Use preset if random is enabled
                    current_file_random_lat, current_file_random_lng = generate_random_coordinates_in_quadrilateral(exif_data["preset"])
                    current_app.logger.info(f"Generated random coordinates for {original_filename}: {current_file_random_lat}, {current_file_random_lng}")

                # Prepare EXIF data for writing for the current file
                # This will be a flattened dictionary of ExifTool-compatible tags
                exif_data_to_write = {}

                # Extract existing metadata if provided from the frontend (from /exif page)
                all_metadata_str = request.form.get('all_metadata')
                if all_metadata_str:
                    try:
                        incoming_metadata = json.loads(all_metadata_str)
                        
                        # Prioritize comprehensive ExifTool data if available
                        if "Comprehensive Metadata (ExifTool)" in incoming_metadata:
                            # Flatten the "Other ExifTool Tags" section
                            other_exiftool_tags = incoming_metadata["Comprehensive Metadata (ExifTool)"].get("Other ExifTool Tags", {})
                            exif_data_to_write.update(flatten_exiftool_metadata(other_exiftool_tags))

                            # Process top-level ExifTool categories (e.g., GPS Data, Location, Contact)
                            for category_name, category_data in incoming_metadata["Comprehensive Metadata (ExifTool)"].items():
                                if category_name not in ["Image Information (PIL)", "Other ExifTool Tags"] and isinstance(category_data, dict):
                                    for friendly_field_name, value in category_data.items():
                                        # Attempt to map the friendly name to ExifTool tags for writing
                                        mapped_tags = friendly_to_exiftool_tag_map.get(friendly_field_name)
                                        if mapped_tags:
                                            if not isinstance(mapped_tags, list):
                                                mapped_tags = [mapped_tags]
                                            for tag in mapped_tags:
                                                exif_data_to_write[tag] = value
                                        elif ':' in friendly_field_name: # If it's already a Group:TagName format
                                            exif_data_to_write[friendly_field_name] = value
                                        else:
                                            current_app.logger.debug(f"Comprehensive metadata field '{friendly_field_name}' from category '{category_name}' not mapped for writing.")

                    except json.JSONDecodeError as e:
                        current_app.logger.error(f"Error decoding all_metadata JSON for {original_filename}: {e}")
                        processing_errors.append(f'Invalid metadata provided for {original_filename}: {e}')
                        continue # Skip this file

                # Define mapping from frontend friendly names to ExifTool tags
                # This mapping should be exhaustive for all fields we want to write
                friendly_to_exiftool_tag_map = {
                    # GPS Data (handled separately for Lat/Lng Ref, but can include other GPS tags)
                    # Note: GPSLatitude/Longitude are special-cased for writing format
                    "GPSVersionID": "GPS:GPSVersionID",
                    "GPSMapDatum": "GPS:GPSMapDatum",

                    # Location (using common IPTC/XMP tags)
                    "Country": ["IPTC:Country-PrimaryLocationName", "XMP-iptcCore:CountryName"],
                    "State": ["IPTC:Province-State", "XMP-iptcCore:ProvinceState"],
                    "City": ["IPTC:City", "XMP-iptcCore:City"],
                    "Sublocation": ["IPTC:Sub-location", "XMP-iptcCore:Location"],

                    # Artist/Source/Description
                    "Creator": ["IFD0:Artist", "XMP-tiff:Artist", "XMP-dc:Creator"],
                    "CreatorTitle": ["IPTC:By-lineTitle", "XMP-photoshop:CaptionWriter"],
                    "Credit": ["IPTC:Credit", "XMP-photoshop:Credit"],
                    "Source": ["IPTC:Source", "XMP-photoshop:Source"],
                    "URL": ["Photoshop:URL", "XMP-xmp:BaseURL"], # General URLs
                    "ObjectName": "IPTC:ObjectName",
                    "Headline": "XMP-photoshop:Headline",
                    "Caption": ["IPTC:Caption-Abstract", "XMP-dc:Description"],
                    "Copyright": ["IFD0:Copyright", "IPTC:CopyrightNotice", "XMP-dc:Rights"],
                    "Rating": ["IFD0:Rating", "XMP-xmp:Rating"],
                    "RatingPercent": "XMP-microsoft:RatingPercent",
                    "SpecialInstructions": "XMP-xmp:Instructions",

                    # Categories/Keywords
                    "Category": "IPTC:Category",
                    "SupplementalCategories": "IPTC:SupplementalCategories",
                    "Keywords": ["IPTC:Keywords", "XMP-dc:Subject"], # These should be multi-valued tags

                    # Contact Information
                    # These are keys from the geotagging form (e.g., from client presets)
                    "Address": ["IPTC:ContactInfoAddress", "XMP-iptcCore:CreatorWorkAddress"],
                    "PostalCode": ["IPTC:ContactInfoPostalCode", "XMP-iptcCore:CreatorPostalCode"],
                    "Phone": ["IPTC:ContactInfoPhone", "XMP-iptcCore:CreatorWorkTelephone"],
                    "Email": ["IPTC:ContactInfoEmail", "XMP-iptcCore:CreatorWorkEmail"],
                    "URL": ["Photoshop:URL", "XMP-xmp:BaseURL"], # General URLs from form
                    
                    # These are keys from the Comprehensive Metadata (ExifTool) from the /exif page
                    "Contact Byline": ["IPTC:By-line", "XMP-dc:Creator"], # Re-use Creator mapping
                    "Contact Byline Title": ["IPTC:By-lineTitle", "XMP-photoshop:CaptionWriter"], # Re-use CreatorTitle mapping
                    "Contact Address": ["IPTC:ContactInfoAddress", "XMP-iptcCore:CreatorWorkAddress"],
                    "Contact City": ["IPTC:ContactInfoCity", "XMP-iptcCore:CreatorCity"],
                    "Contact PostalCode": ["IPTC:ContactInfoPostalCode", "XMP-iptcCore:CreatorPostalCode"],
                    "Contact State/Province": ["IPTC:ContactInfoStateProvince", "XMP-iptcCore:CreatorRegion"],
                    "Contact Country": ["IPTC:ContactInfoCountry", "XMP-iptcCore:CreatorCountry"],
                    "Contact Phone": ["IPTC:ContactInfoPhone", "XMP-iptcCore:CreatorWorkTelephone"],
                    "Contact E-Mail": ["IPTC:ContactInfoEmail", "XMP-iptcCore:CreatorWorkEmail"],
                    "Contact URL": ["IPTC:ContactInfoWebURL", "XMP-iptcCore:CreatorWorkURL"], # Specific Contact URL

                    # Location fields from /exif page (if they come as top-level category keys)
                    "Sublocation": ["IPTC:Sub-location", "XMP-iptcCore:Location"],
                    
                    # Date/Time
                    "GPSDateStamp": "GPS:GPSDateStamp", # Direct GPS tag
                    "GPSTimeStamp": "GPS:GPSTimeStamp", # Direct GPS tag
                    "GPS Date Time": "XMP:GPSDateTime", # XMP equivalent
                    "Creation Date": ["EXIF:CreateDate", "XMP-xmp:CreateDate"],
                    "Modification Date": ["EXIF:ModifyDate", "XMP-xmp:ModifyDate"],
                    "Taken Date": ["EXIF:DateTimeOriginal", "XMP-xmp:CreateDate"], # Often maps to DateTimeOriginal
                }

                # --- OVERWRITE / ADD DATA FROM GEOTAGGING FORM (`exif_data` from request.form) ---
                # Process incoming form data and map to ExifTool tags, prioritizing these.
                for form_friendly_name, form_value in exif_data.items():
                    # Only process if value is not None or empty (string/list)
                    if form_value is None or (isinstance(form_value, (str, list)) and not form_value):
                        continue

                    # Special handling for coordinates (latitude/longitude from form/preset)
                    if form_friendly_name == "GPSLatitude" and form_value is not None:
                        try:
                            lat_float = float(form_value)
                            exif_data_to_write["GPS:GPSLatitude"] = lat_float
                            exif_data_to_write["GPS:GPSLatitudeRef"] = "N" if lat_float >= 0 else "S"
                        except ValueError:
                            current_app.logger.warning(f"Invalid GPSLatitude value from form: {form_value}")
                    elif form_friendly_name == "GPSLongitude" and form_value is not None:
                        try:
                            lon_float = float(form_value)
                            exif_data_to_write["GPS:GPSLongitude"] = lon_float
                            exif_data_to_write["GPS:GPSLongitudeRef"] = "E" if lon_float >= 0 else "W"
                        except ValueError:
                            current_app.logger.warning(f"Invalid GPSLongitude value from form: {form_value}")
                    # Special handling for datetime from the form (it's a single field 'datetime')
                    elif form_friendly_name == "datetime" and form_value:
                        try:
                            # datetime from frontend is like '2025-06-16T12:49'
                            dt = datetime.datetime.fromisoformat(form_value)
                            # Update GPS date/time tags
                            exif_data_to_write["GPS:GPSDateStamp"] = dt.strftime("%Y:%m:%d")
                            exif_data_to_write["GPS:GPSTimeStamp"] = dt.strftime("%H:%M:%S")
                            exif_data_to_write["XMP:GPSDateTime"] = dt.isoformat(timespec='seconds') + "Z"
                            # Also update general date/time tags
                            exif_data_to_write["EXIF:DateTimeOriginal"] = dt.strftime("%Y:%m:%d %H:%M:%S")
                            exif_data_to_write["EXIF:CreateDate"] = dt.strftime("%Y:%m:%d %H:%M:%S")
                            exif_data_to_write["EXIF:ModifyDate"] = dt.strftime("%Y:%m:%d %H:%M:%S")
                            exif_data_to_write["XMP-xmp:CreateDate"] = dt.isoformat(timespec='seconds') # No Z for XMP CreateDate
                            exif_data_to_write["XMP-xmp:ModifyDate"] = dt.isoformat(timespec='seconds') # No Z for XMP ModifyDate
                        except ValueError:
                            current_app.logger.warning(f"Invalid datetime format from form: {form_value}")
                    # Special handling for keywords (can be list or comma-separated string)
                    elif form_friendly_name == "Keywords":
                        keywords_list = []
                        if isinstance(form_value, list):
                            keywords_list = form_value
                        elif isinstance(form_value, str):
                            keywords_list = [k.strip() for k in form_value.split(',') if k.strip()]
                        
                        # Store as list in exif_data_to_write; process_image_with_exiftool handles multi-value
                        exif_data_to_write["IPTC:Keywords"] = keywords_list
                        exif_data_to_write["XMP-dc:Subject"] = keywords_list
                    # Handle preset for random coordinates (only if use_random is true)
                    elif form_friendly_name == "preset" and form_value and use_random:
                        random_lat, random_lng = generate_random_coordinates_in_quadrilateral(form_value) # form_value is the preset object
                        if random_lat is not None and random_lng is not None:
                            exif_data_to_write["GPS:GPSLatitude"] = random_lat
                            exif_data_to_write["GPS:GPSLatitudeRef"] = "N" if random_lat >= 0 else "S"
                            exif_data_to_write["GPS:GPSLongitude"] = random_lng
                            exif_data_to_write["GPS:GPSLongitudeRef"] = "E" if random_lng >= 0 else "W"
                            exif_data_to_write["GPS:GPSMapDatum"] = "WGS-84"
                            current_app.logger.info(f"Applied random coordinates from preset: {random_lat}, {random_lng}")

                            # --- ALWAYS OVERRIDE LOCATION FIELDS WITH CITY PRESET IF PRESENT ---
                            if exif_data.get("preset"):
                                city_preset = exif_data["preset"]
                                preset_country = city_preset.get("country", "")
                                preset_state_province = city_preset.get("state_province", "")
                                preset_city = city_preset.get("name", "")
                                preset_sublocation = city_preset.get("sublocation", "")

                                # Write to all relevant tags for maximum compatibility
                                for tag in [
                                    "IPTC:Country-PrimaryLocationName",
                                    "XMP-iptcCore:CreatorCountry",
                                    "XMP-iptcCore:CountryName",
                                    "XMP-photoshop:Country"
                                ]:
                                    exif_data_to_write[tag] = preset_country
                                for tag in [
                                    "IPTC:Province-State",
                                    "XMP-iptcCore:CreatorRegion",
                                    "XMP-iptcCore:ProvinceState",
                                    "XMP-photoshop:State"
                                ]:
                                    exif_data_to_write[tag] = preset_state_province
                                for tag in [
                                    "IPTC:City",
                                    "XMP-iptcCore:CreatorCity",
                                    "XMP-iptcCore:City",
                                    "XMP-photoshop:City"
                                ]:
                                    exif_data_to_write[tag] = preset_city
                                for tag in [
                                    "IPTC:Sub-location",
                                    "XMP-iptcCore:Location"
                                ]:
                                    exif_data_to_write[tag] = preset_sublocation
                    # Explicit handling for general location fields
                    elif form_friendly_name == "Country":
                        for tag in ["IPTC:Country-PrimaryLocationName", "XMP-iptcCore:CountryName"]:
                            exif_data_to_write[tag] = form_value
                    elif form_friendly_name == "State":
                        for tag in ["IPTC:Province-State", "XMP-iptcCore:ProvinceState"]:
                            exif_data_to_write[tag] = form_value
                    elif form_friendly_name == "City":
                        for tag in ["IPTC:City", "XMP-iptcCore:City"]:
                            exif_data_to_write[tag] = form_value
                    # Explicit handling for contact info fields
                    elif form_friendly_name == "ContactCountry":
                        for tag in ["IPTC:ContactInfoCountry", "XMP-iptcCore:CreatorCountry"]:
                            exif_data_to_write[tag] = form_value
                    elif form_friendly_name == "ContactState":
                        for tag in ["IPTC:ContactInfoStateProvince", "XMP-iptcCore:CreatorRegion"]:
                            exif_data_to_write[tag] = form_value
                    elif form_friendly_name == "ContactCity":
                        for tag in ["IPTC:ContactInfoCity", "XMP-iptcCore:CreatorCity"]:
                            exif_data_to_write[tag] = form_value
                    elif form_friendly_name == "ContactURL":
                        for tag in ["IPTC:ContactInfoWebURL", "XMP-iptcCore:CreatorWorkURL"]:
                            exif_data_to_write[tag] = form_value
                    elif form_friendly_name == "Creator":
                        for tag in ["IFD0:Artist", "XMP-tiff:Artist", "XMP-dc:Creator"]:
                            exif_data_to_write[tag] = form_value
                    else:
                        # For other friendly names, map them to their ExifTool tags
                        mapped_tags = friendly_to_exiftool_tag_map.get(form_friendly_name)
                        if mapped_tags:
                            if not isinstance(mapped_tags, list):
                                mapped_tags = [mapped_tags] # Ensure it's always a list for consistent iteration
                            for tag in mapped_tags:
                                exif_data_to_write[tag] = form_value
                        else:
                            # If the form field name itself is an ExifTool tag (e.g., from client presets),
                            # add it directly if it contains a colon.
                            if ':' in form_friendly_name:
                                exif_data_to_write[form_friendly_name] = form_value
                            else:
                                current_app.logger.debug(f"Frontend field '{form_friendly_name}' not explicitly mapped or a direct ExifTool tag for writing.")

                # After processing all form fields, set contact address if present
                if 'address' in exif_data and exif_data['address']:
                    exif_data_to_write['IPTC:ContactInfoAddress'] = exif_data['address']

                # Clean up any undesirable tags that might have come from the read operation
                # These are tags ExifTool adds for info but are not meant for writing or might cause conflicts
                unwanted_write_tags = [
                    # System/File Info (read-only from ExifTool)
                    "ExifTool:ExifToolVersion", "System:FileName", "System:Directory", 
                    "System:FileSize", "System:FileModifyDate", "System:FileAccessDate", 
                    "System:FileCreateDate", "System:FilePermissions", "File:FileType", 
                    "File:FileTypeExtension", "File:MIMEType", 
                    
                    # Image characteristics that ExifTool might derive but are not directly writable in this context
                    "File:ExifByteOrder", "File:ImageWidth", "File:ImageHeight", 
                    "File:EncodingProcess", "File:BitsPerSample", "File:ColorComponents", 
                    "File:YCbCrSubSampling", 

                    # Composite tags that are derived and not directly writable
                    "Composite:ImageSize", "Composite:Megapixels", 
                    "Composite:GPSDateTime", "Composite:GPSLatitude", "Composite:GPSLongitude", 
                    "Composite:GPSLatitudeRef", "Composite:GPSLongitudeRef", "Composite:GPSPosition",

                    # Other potentially problematic tags that should not be written directly
                    "SourceFile", # This is a meta-tag from ExifTool output, not a writable tag
                    # Add any other tags identified as problematic during testing here
                ]
                # Remove unwanted tags. Iterate over a copy of keys to allow modification during iteration.
                for tag_key in list(exif_data_to_write.keys()):
                    # Check if the tag_key (e.g., 'File:FileName') starts with any of the unwanted tags or is an exact match
                    for unwanted_prefix in unwanted_write_tags:
                        if tag_key.startswith(unwanted_prefix):
                            exif_data_to_write.pop(tag_key, None)
                            break # Break inner loop, as this tag_key is handled

                current_app.logger.info(f"Final exif_data_to_write for {original_filename}: {json.dumps(exif_data_to_write, indent=2)}")

                # --- Image Format Handling & Conversion to JPEG for ExifTool ---
                # ExifTool works best with JPEG for writing, and PIL can handle various inputs.
                # We will convert input to JPEG in a temp file if it's not already.
                file_to_process_for_exiftool = uploaded_file_path # Default to original
                original_ext = os.path.splitext(original_filename)[1].lower()

                # Open the image first to check its mode or convert if necessary
                img = None # Initialize img to None
                try:
                    current_app.logger.info(f"Attempting to open image: {uploaded_file_path}. Exists: {os.path.exists(uploaded_file_path)}")
                    img = Image.open(uploaded_file_path)

                    if original_ext not in ['.jpg', '.jpeg'] or img.mode != 'RGB': # Use img.mode here
                        # Create a temp JPEG for ExifTool if conversion is needed
                        temp_filename_for_exiftool = f"{uuid.uuid4()}.jpg"
                        temp_dir_for_conversion = os.path.join(processed_folder, os.path.dirname(original_relative_path))
                        os.makedirs(temp_dir_for_conversion, exist_ok=True)
                        temp_jpeg_path = os.path.join(temp_dir_for_conversion, temp_filename_for_exiftool)
                        
                        current_app.logger.info(f"Converting {original_filename} to JPEG for ExifTool: {temp_jpeg_path}")
                        img.convert('RGB').save(temp_jpeg_path, 'JPEG', quality=95) # Save as high quality JPEG
                        file_to_process_for_exiftool = temp_jpeg_path
                except UnidentifiedImageError as img_ident_error:
                    current_app.logger.error(f"Cannot identify image file {original_filename}: {img_ident_error}")
                    processing_errors.append(f"Cannot identify image file {original_filename}. Please ensure it's a valid image file.")
                    continue # Skip this file
                except Exception as img_open_conv_error:
                    current_app.logger.error(f"Error opening or converting image {original_filename} to JPEG for ExifTool: {img_open_conv_error}")
                    processing_errors.append(f"Error processing {original_filename}: {img_open_conv_error}")
                    continue # Skip this file
                finally:
                    if img: # Ensure image is closed
                        img.close()

                # Determine the final output path preserving the folder structure
                # Ensure the original directory structure is maintained within the processed_folder
                # by joining processed_folder with the original_relative_path's directory.
                base_name = os.path.splitext(os.path.basename(original_relative_path))[0]
                processed_relative_dir = os.path.dirname(original_relative_path)
                final_output_dir = os.path.join(processed_folder, processed_relative_dir)
                os.makedirs(final_output_dir, exist_ok=True)  # Ensure output directory exists
                
                # Always save the final geotagged image as JPEG for broad compatibility
                final_output_path = os.path.join(final_output_dir, f"{base_name}.jpg")

                current_app.logger.info(f"Processing {original_filename}. Input: {file_to_process_for_exiftool}, Output: {final_output_path}")

                # Process the image with updated metadata using ExifTool
                if process_image_with_exiftool(file_to_process_for_exiftool, final_output_path, exif_data_to_write):
                    # Store info for successful files
                    base_filename_no_ext = os.path.splitext(os.path.basename(original_relative_path))[0]
                    processed_relative_dir_for_zip = os.path.dirname(original_relative_path)
                    # Use the original relative path's structure but enforce .jpg extension
                    arcname_in_zip = os.path.join(processed_relative_dir_for_zip, f"{base_filename_no_ext}.jpg")

                    processed_files_with_paths.append({
                        'original_name': original_filename,
                        'processed_path': final_output_path,
                        'arcname_in_zip': arcname_in_zip,
                        'url': url_for('geotagging.download_single', session_id=session_id, filename=os.path.basename(final_output_path)) # Direct URL to base filename
                    })
                    current_app.logger.info(f"Successfully processed and added {original_filename} to processed_files_with_paths.")
                else:
                    processing_errors.append(f"Error processing {original_filename}: Geotagging failed during ExifTool write.")
                    current_app.logger.error(f"Failed to process {original_filename} with ExifTool.")

                # At the end of each file processing (success or fail):
                percent = int(((idx + 1) / total_files) * 100)
                set_progress(session_id, percent)

            except Exception as e:
                error_msg = f"Unhandled error processing {original_filename}: {str(e)}"
                current_app.logger.error(error_msg)
                processing_errors.append(error_msg)
            finally:
                # Clean up the temporary JPEG file created for ExifTool processing, if it exists
                if temp_jpeg_path and os.path.exists(temp_jpeg_path):
                    os.remove(temp_jpeg_path)
                    current_app.logger.info(f"Cleaned up temporary JPEG: {temp_jpeg_path}")
                # Clean up the original uploaded temp file after processing each file
                if os.path.exists(uploaded_file_path):
                    os.remove(uploaded_file_path)
                    current_app.logger.info(f"Cleaned up uploaded file: {uploaded_file_path}")

        
        if not processed_files_with_paths:
            return jsonify({
                'error': 'Failed to process any files',
                'details': 'No files were successfully geotagged or converted. Errors:\n' + '\n'.join(processing_errors)
            }), 500
        
        # Create a zip file preserving folder structure
        try:
            zip_filename = f"geotagged_images_{session_id}.zip"
            zip_path = os.path.join(processed_folder, zip_filename)

            current_app.logger.info(f"Creating zip file: {zip_path}")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for item in processed_files_with_paths:
                    current_app.logger.info(f"Adding {item['processed_path']} to zip as {item['arcname_in_zip']}")
                    zipf.write(item['processed_path'], item['arcname_in_zip'])
            current_app.logger.info(f"Successfully created zip file.")
        except Exception as e:
            current_app.logger.error(f"Failed to create zip file: {e}")
            return jsonify({
                'error': 'Failed to create zip file',
                'details': str(e)
            }), 500

        # After all processing is done, ensure progress is 100%
        set_progress(session_id, 100)

        return jsonify({
            'status': 'success',
            'message': f'Successfully processed {len(processed_files_with_paths)} images',
            'download_url': f'/api/geotagging/download/{session_id}/zip',
            'processed_files': processed_files_with_paths, # Return details of processed files
            'errors': processing_errors if processing_errors else None, # Return any individual file errors
            'session_id': session_id
        })
        
    except Exception as e:
        current_app.logger.error(f"Unexpected error in process_images route: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred',
            'details': str(e)
        }), 500

@geotagging_bp.route('/download/<session_id>/zip', methods=['GET'])
def download_zip(session_id):
    """Download processed images as a zip file."""
    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
    zip_path = os.path.join(processed_folder, f"geotagged_images_{session_id}.zip")
    
    if not os.path.exists(zip_path):
        current_app.logger.error(f"Zip file not found for session {session_id}: {zip_path}")
        return jsonify({'error': 'Zip file not found'}), 404
    
    current_app.logger.info(f"Serving zip file: {zip_path}")
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"geotagged_images.zip",
        mimetype='application/zip'
    )

@geotagging_bp.route('/download/<session_id>/single', methods=['GET'])
def download_single(session_id):
    """Download a single processed image."""
    # This endpoint needs the actual filename (e.g., base.jpg) and session_id
    # The URL generated for single files used os.path.basename(final_output_path)
    filename = request.args.get('filename')
    if not filename:
        current_app.logger.error(f"Filename not provided for single download in session {session_id}")
        return jsonify({'error': 'Filename not provided'}), 400

    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)
    
    # We need to search for the file within the session's processed folder, as it might be in a subdirectory
    found_file_path = None
    for root, _, files in os.walk(processed_folder):
        if filename in files:
            found_file_path = os.path.join(root, filename)
            break

    if not found_file_path or not os.path.exists(found_file_path):
        current_app.logger.error(f"File {filename} not found in session {session_id}. Searched in {processed_folder}")
        return jsonify({'error': f'File {filename} not found in session {session_id}'}), 404

    mimetype = f'image/{os.path.splitext(filename)[1][1:].lower()}'
    if mimetype == 'image/': # Default to jpeg if extension is weird or missing
        mimetype = 'image/jpeg'

    current_app.logger.info(f"Serving single file: {found_file_path} with mimetype {mimetype}")
    return send_file(
        found_file_path,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype
    )

@geotagging_bp.route('/cleanup/<session_id>', methods=['POST'])
def cleanup_session(session_id):
    """Clean up temporary files for a session."""
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], session_id)
    processed_folder = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id)

    # Clean up upload folder and its contents
    if os.path.exists(upload_folder):
        try:
            shutil.rmtree(upload_folder)
            current_app.logger.info(f"Cleaned up upload folder: {upload_folder}")
        except Exception as e:
            current_app.logger.warning(f"Error cleaning up upload folder {upload_folder}: {e}")

    # Clean up processed folder and its contents
    if os.path.exists(processed_folder):
        try:
            shutil.rmtree(processed_folder)
            current_app.logger.info(f"Cleaned up processed folder: {processed_folder}")
        except Exception as e:
            current_app.logger.warning(f"Error cleaning up processed folder {processed_folder}: {e}")

    # Remove progress file if exists
    progress_file = os.path.join(current_app.config['PROCESSED_FOLDER'], session_id, 'progress.json')
    if os.path.exists(progress_file):
        try:
            os.remove(progress_file)
        except Exception:
            pass

    return jsonify({'status': 'success', 'message': 'Session cleaned up'})
