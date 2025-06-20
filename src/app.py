import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # DON'T CHANGE THIS !!!

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import json
import uuid
import shutil
import tempfile
import zipfile
import time
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image
import pillow_heif
import exiftool
import subprocess
import random
import math
import os.path
import piexif
import base64
from io import BytesIO

# Import routes
from src.routes.geotagging import geotagging_bp
from src.routes.conversion import conversion_bp
from src.routes.resizing import resizing_bp
from src.routes.watermark import watermark_bp
from src.routes.presets import presets_bp

# Create Flask app
app = Flask(__name__)

# Register blueprints
app.register_blueprint(geotagging_bp, url_prefix='/api/geotagging')
app.register_blueprint(conversion_bp, url_prefix='/api/conversion')
app.register_blueprint(resizing_bp, url_prefix='/api/resizing')
app.register_blueprint(watermark_bp, url_prefix='/api/watermark')
app.register_blueprint(presets_bp, url_prefix='/api/presets')

# Configure upload folder
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'image_processor_uploads')
app.config['MAX_CONTENT_LENGTH'] = 2048 * 1024 * 1024  # 2GB max upload size
app.config['SESSION_FOLDER'] = os.path.join(tempfile.gettempdir(), 'image_processor_sessions')
app.config['PROCESSED_FOLDER'] = os.path.join(tempfile.gettempdir(), 'image_processor_processed')

# Create necessary folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SESSION_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

# Ensure static data directory exists
static_data_dir = os.path.join(os.path.dirname(__file__), 'static', 'data')
os.makedirs(static_data_dir, exist_ok=True)

# Main route
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/exif', methods=['GET', 'POST'])
def exif_viewer():
    if request.method == 'POST':
        if 'image' not in request.files:
            return render_template('exif.html', error='No image file provided')
        
        file = request.files['image']
        if file.filename == '':
            return render_template('exif.html', error='No selected file')
        
        if not allowed_file(file.filename):
            return render_template('exif.html', error='Invalid file type')
        
        temp_file_path = None # Initialize to None
        try:
            image_data = file.read()
            image_stream = BytesIO(image_data)

            # Open image with PIL for basic info and preview
            image = Image.open(image_stream)

            processed_metadata = {}
            error_messages = []

            # Get basic image information from PIL
            processed_metadata["Image Information (PIL)"] = {
                "Format": image.format,
                "Mode": image.mode,
                "Size": f"{image.size[0]}x{image.size[1]} pixels",
                "Width": f"{image.size[0]} pixels",
                "Height": f"{image.size[1]} pixels",
                "Filename": file.filename
            }
            
            # Attempt to extract comprehensive metadata using ExifTool
            exiftool_found_data = False
            try:
                # Create a temporary file in a controlled temporary directory
                # Use a specific session directory if possible, or app.config['UPLOAD_FOLDER']
                session_id = str(uuid.uuid4())
                temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
                os.makedirs(temp_dir, exist_ok=True)
                
                temp_file_path = os.path.join(temp_dir, secure_filename(file.filename or 'temp_image.jpg'))
                
                with open(temp_file_path, 'wb') as f:
                    f.write(image_data)
                
                # Run exiftool with JSON output, all tags, unknown tags, and grouped by family
                # -s: Short tag names
                # -G1: Group tags by family 1
                # -a: Allow duplicate tags
                # -u: Unknown tags
                result = subprocess.run(['exiftool', '-j', '-a', '-u', '-G1', '-s', temp_file_path],
                                         capture_output=True, text=True, check=False)
                
                if result.returncode == 0 and result.stdout:
                    exiftool_output = json.loads(result.stdout)[0]
                    
                    # Clean up internal ExifTool tags that are not useful for display
                    unwanted_tags = [
                        'SourceFile', 'ExifToolVersion', 'FileName', 'Directory',
                        'FileSize', 'FileModifyDate', 'FileAccessDate', 'FileCreateDate',
                        'MIMEType', 'CurrentIPTCDigest',
                        # Remove more specific, often redundant/technical tags
                        'ProfileDescription', 'ProfileCMMType', 'ProfileVersion', 'ProfileClass',
                        'ColorSpaceData', 'ProfileConnectionSpace', 'ProfileDateTime',
                        'ProfileFileSignature', 'PrimaryPlatform', 'CMMFlags', 'DeviceManufacturer',
                        'DeviceModel', 'DeviceAttributes', 'RenderingIntent', 'ConnectionSpaceIlluminant',
                        'ProfileCreator', 'ProfileID', 'ProfileCopyright', 'MediaWhitePoint',
                        'MediaBlackPoint', 'RedTRC', 'GreenTRC', 'BlueTRC', 'ViewingCondDesc',
                        'ViewingCondIlluminant', 'ViewingCondReflectivity', 'MeasurementObserver',
                        'MeasurementFlare', 'MeasurementIlluminant', 'JFIFVersion',
                        'YCbCrSubSampling', 'PhotoshopQuality', 'ProgressiveScans',
                        'XMPToolkit', 'Composite', 'RunTimeValue', 'RunTimeEpoch',
                        'RunTimeFlags', 'RunTimeUTC', 'IPTC-NAA', 'IFD0', 'ExifIFD',
                        'StripOffsets', 'ThumbnailLength', 'ThumbnailOffset', 'GPSVersionID',
                        'GPSLatitudeRef', 'GPSLongitudeRef', 'GPSAltitudeRef',
                        'GPSMeasureMode', # Raw values, we want the parsed ones
                        'XPKeywords', # Often duplicated by XMP-dc:Subject
                        'CreatorContactInfo', # These are parsed into sub-fields already
                        'XResolution', 'YResolution', 'ResolutionUnit', 'YCbCrPositioning',
                        'ImageSize', 'Megapixels',
                        'GPSDateTime' # We map GPSDateStamp and GPSTimeStamp separately
                    ]
                    
                    for tag_to_remove in unwanted_tags:
                        # Iterate over a copy of keys to allow modification during iteration
                        for group_key in list(exiftool_output.keys()): 
                            full_tag_name = f'{group_key}:{tag_to_remove}'
                            if full_tag_name in exiftool_output:
                                exiftool_output.pop(full_tag_name, None)
                            elif tag_to_remove in exiftool_output: # For tags without a group prefix
                                exiftool_output.pop(tag_to_remove, None)
                    
                    # Initialize structured metadata dictionary
                    structured_data = {
                        "GPS Data": {},
                        "Location": {},
                        "Artist/Source/Description": {},
                        "Categories/Keywords": {},
                        "Contact": {},
                        "Date/Time": {},
                        "Other ExifTool Tags": {} # For anything not specifically categorized
                    }

                    # Define mapping from ExifTool TagGroup:TagName to structured_data categories
                    # This mapping is based on typical ExifTool output and your screenshot
                    tag_map = {
                        # GPS Data
                        "GPS:GPSLatitude": ("GPS Data", "Latitude"),
                        "GPS:GPSLongitude": ("GPS Data", "Longitude"),
                        "GPS:GPSAltitude": ("GPS Data", "Altitude [m]"),
                        "GPS:ImageDirection": ("GPS Data", "Image Direction [°]"),
                        "XMP-exif:GPSLatitude": ("GPS Data", "Latitude"),
                        "XMP-exif:GPSLongitude": ("GPS Data", "Longitude"),
                        "GPS:GPSDateStamp": ("Date/Time", "GPS Date Stamp"),
                        "GPS:GPSTimeStamp": ("Date/Time", "GPS Time Stamp"),
                        
                        # Location
                        "IPTC:Country-PrimaryLocationName": ("Location", "Country"),
                        "IPTC:Province-State": ("Location", "State/Province"),
                        "IPTC:City": ("Location", "City"),
                        "IPTC:Sub-location": ("Location", "Sublocation"), # Corrected tag name
                        "XMP-iptcCore:CreatorCity": ("Location", "City"),
                        "XMP-iptcCore:CreatorRegion": ("Location", "State/Province"),
                        "XMP-iptcCore:CreatorCountry": ("Location", "Country"),
                        "XMP-iptcCore:Location": ("Location", "Sublocation"), # Often holds sublocation
                        "XMP-photoshop:City": ("Location", "City"),
                        "XMP-photoshop:State": ("Location", "State/Province"),
                        "XMP-photoshop:Country": ("Location", "Country"),

                        # Artist/Source/Description
                        "IFD0:Artist": ("Artist/Source/Description", "Artist"),
                        "IPTC:Writer-Editor": ("Artist/Source/Description", "Caption Writer"),
                        "IPTC:Credit": ("Artist/Source/Description", "Credit"),
                        "IPTC:Source": ("Artist/Source/Description", "Source"),
                        "Photoshop:URL": ("Artist/Source/Description", "URL"), # Direct URL from Photoshop
                        "XMP-tiff:Artist": ("Artist/Source/Description", "Artist"),
                        "XMP-dc:Creator": ("Artist/Source/Description", "Artist"),
                        "XMP-photoshop:Credit": ("Artist/Source/Description", "Credit"),
                        "XMP-photoshop:Source": ("Artist/Source/Description", "Source"),
                        "XMP-photoshop:CaptionWriter": ("Artist/Source/Description", "Caption Writer"),
                        "XMP-xmp:BaseURL": ("Artist/Source/Description", "URL"), # Another URL source
                        "IPTC:ObjectName": ("Artist/Source/Description", "Object Name"),
                        "XMP-photoshop:Headline": ("Artist/Source/Description", "Headline"),
                        "IPTC:Caption-Abstract": ("Artist/Source/Description", "Caption"),
                        "XMP-dc:Description": ("Artist/Source/Description", "Caption"),
                        "IFD0:Copyright": ("Artist/Source/Description", "Copyright"),
                        "IPTC:CopyrightNotice": ("Artist/Source/Description", "Copyright"),
                        "XMP-dc:Rights": ("Artist/Source/Description", "Copyright"),
                        "XMP-xmp:Rating": ("Artist/Source/Description", "Rating"), # XMP rating
                        "IFD0:Rating": ("Artist/Source/Description", "Rating"), # EXIF rating
                        "XMP-microsoft:RatingPercent": ("Artist/Source/Description", "Rating Percent"), # Microsoft rating
                        "XMP-xmp:Instructions": ("Artist/Source/Description", "Special Instructions"),

                        # Categories/Keywords
                        "IPTC:Category": ("Categories/Keywords", "Category"),
                        "IPTC:SupplementalCategories": ("Categories/Keywords", "Supplemental Categories"),
                        "IPTC:Keywords": ("Categories/Keywords", "Keywords"),
                        "XMP-dc:Subject": ("Categories/Keywords", "Keywords"),

                        # Contact
                        "IPTC:By-line": ("Contact", "Contact Byline"),
                        "IPTC:By-lineTitle": ("Contact", "Contact Byline Title"),
                        "IPTC:ContactInfoAddress": ("Contact", "Contact Address"),
                        "IPTC:ContactInfoCity": ("Contact", "Contact City"),
                        "IPTC:ContactInfoPostalCode": ("Contact", "Contact PostalCode"),
                        "IPTC:ContactInfoStateProvince": ("Contact", "Contact State/Province"),
                        "IPTC:ContactInfoCountry": ("Contact", "Contact Country"),
                        "IPTC:ContactInfoPhone": ("Contact", "Contact Phone"),
                        "IPTC:ContactInfoEmail": ("Contact", "Contact E-Mail"),
                        "IPTC:ContactInfoWebURL": ("Contact", "Contact URL"),
                        "XMP-iptcCore:CreatorWorkEmail": ("Contact", "Contact E-Mail"), # Key mapping for email
                        "XMP-iptcCore:CreatorWorkTelephone": ("Contact", "Contact Phone"), # Key mapping for phone
                        "XMP-iptcCore:CreatorWorkURL": ("Contact", "Contact URL"), # Key mapping for contact URL
                        "XMP-iptcCore:CreatorCity": ("Contact", "Contact City"),
                        "XMP-iptcCore:CreatorRegion": ("Contact", "Contact State/Province"),
                        "XMP-iptcCore:CreatorCountry": ("Contact", "Contact Country"),
                        "XMP-iptcCore:CreatorPostalCode": ("Contact", "Contact PostalCode"),

                        # Date/Time
                        "EXIF:DateTimeOriginal": ("Date/Time", "Taken Date"),
                        "EXIF:CreateDate": ("Date/Time", "Creation Date"),
                        "EXIF:ModifyDate": ("Date/Time", "Modification Date"),
                        "XMP-xmp:CreateDate": ("Date/Time", "Creation Date"), # XMP version of create date
                        "XMP-xmp:ModifyDate": ("Date/Time", "Modification Date"),
                        "XMP-exif:GPSDateTime": ("Date/Time", "GPS Date Time") # Combined date/time
                    }

                    # Process ExifTool output
                    for exiftool_tag, value in exiftool_output.items():
                        # Convert lists/tuples to string for display if needed
                        if isinstance(value, (list, tuple)):
                            value = ", ".join(map(str, value))
                        elif isinstance(value, bytes):
                            value = value.decode('utf-8', errors='ignore')

                        if exiftool_tag in tag_map:
                            category, field_name = tag_map[exiftool_tag]
                            # Prefer more specific tags or non-empty values
                            if field_name not in structured_data[category] or (value and not structured_data[category].get(field_name)): 
                                structured_data[category][field_name] = value
                        else:
                            # Add remaining tags to "Other ExifTool Tags" for inspection
                            # Avoid adding very technical/redundant tags here that were missed in unwanted_tags
                            # Only add if the value is not empty
                            if value and not any(unwanted_prefix in exiftool_tag for unwanted_prefix in ['ICC_Profile', 'APP1', 'MakerNotes', 'Preview', 'JpgFromRaw', 'RawData', 'EXIFTool', 'XMPToolkit', 'CurrentIPTCDigest', 'ColorSpace', 'OffsetTime', 'SubSecTime']):
                                group_key = exiftool_tag.split(':')[0] if ':' in exiftool_tag else "Other Metadata"
                                if group_key not in structured_data["Other ExifTool Tags"]:
                                    structured_data["Other ExifTool Tags"][group_key] = {}
                                structured_data["Other ExifTool Tags"][group_key][exiftool_tag.split(':')[-1]] = value
                    
                    # Consolidate and clean up empty categories
                    final_metadata = {}
                    for category, data in structured_data.items():
                        if data: # Only add categories that have data
                            final_metadata[category] = data
                    
                    if final_metadata:
                        processed_metadata["Comprehensive Metadata (ExifTool)"] = final_metadata
                        exiftool_found_data = True
                    else:
                        error_messages.append("ExifTool returned data but no relevant tags were found after processing. Check ExifTool output in console for raw data.")

                else:
                    error_messages.append(f"ExifTool command failed: {result.stderr.strip() or 'No error output'}")
            except FileNotFoundError:
                error_messages.append("ExifTool is not installed or not in system PATH. Please install it to get comprehensive metadata.")
            except json.JSONDecodeError as e:
                error_messages.append(f"ExifTool returned invalid JSON: {e}. Raw output: {result.stdout[:500]}...")
            except Exception as e:
                error_messages.append(f"Unexpected error running ExifTool: {str(e)}")
            finally:
                # Clean up the temporary file and directory
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    temp_dir = os.path.dirname(temp_file_path)
                    if os.path.exists(temp_dir): # Remove the temp directory if it's empty
                        try:
                            os.rmdir(temp_dir)
                        except OSError: # Directory might not be empty if other files were created
                            pass

            if not exiftool_found_data:
                # Fallback to piexif if exiftool is not available or failed
                try:
                    exif_dict = piexif.load(image_data)
                    if exif_dict is not None:
                        piexif_processed = {}
                        for section in ['0th', 'Exif', 'GPS', '1st', 'thumbnail']:
                            if section in exif_dict and exif_dict[section]:
                                piexif_processed[section] = {}
                                for tag, value in exif_dict[section].items():
                                    try:
                                        if isinstance(value, bytes):
                                            value = value.decode('utf-8', errors='ignore')
                                        piexif_processed[section][piexif.TAGS[section][tag]["name"]] = str(value)
                                    except:
                                        piexif_processed[section][f"Unknown Tag {tag}"] = str(value)
                        processed_metadata["EXIF Data (Piexif Fallback)"] = piexif_processed
                    else:
                        processed_metadata["EXIF Data (Piexif Fallback)"] = {"Message": "No EXIF data found in the image using Piexif"}
                except Exception as e:
                    processed_metadata["EXIF Data (Piexif Fallback)"] = {"Error": f"Error loading EXIF with Piexif: {str(e)}"}
            
            # Create a preview image (re-read from stream to ensure it's at the beginning)
            image_stream.seek(0)
            image = Image.open(image_stream)
            buffered = BytesIO()
            # Convert to RGB before saving as JPEG if it's not (e.g., some PNGs or GIFs might be RGBA/P)
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            preview_url = f"data:image/jpeg;base64,{img_str}"
            
            return render_template('exif.html', exif_data=processed_metadata, preview_url=preview_url, error=error_messages)
            
        except Exception as e:
            return render_template('exif.html', error=f'Error processing image: {str(e)}')
    
    return render_template('exif.html')

# Serve static files
@app.route('/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)

# Download processed files
@app.route('/download/<session_id>')
def download_file(session_id):
    session_dir = os.path.join(app.config['SESSION_FOLDER'], session_id)
    
    if not os.path.exists(session_dir):
        return jsonify({'error': 'Session not found'}), 404
    
    # Check if there's a zip file already
    zip_path = os.path.join(session_dir, 'processed.zip')
    
    if not os.path.exists(zip_path):
        # Create a zip file of all processed files
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(session_dir):
                if root == session_dir:
                    continue
                    
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, session_dir)
                    zipf.write(file_path, arcname)
    
    return send_file(zip_path, as_attachment=True, download_name='processed_images.zip')

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500

# Helper functions for all routes
def allowed_file(filename):
    """Check if file has an allowed extension."""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'gif', 'heic', 'heif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def create_session():
    """Create a new session directory and return its ID."""
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(app.config['SESSION_FOLDER'], session_id)
    os.makedirs(session_dir, exist_ok=True)
    return session_id, session_dir

def cleanup_old_sessions():
    """Clean up sessions older than 1 hour."""
    now = time.time()
    for session_id in os.listdir(app.config['SESSION_FOLDER']):
        session_dir = os.path.join(app.config['SESSION_FOLDER'], session_id)
        if os.path.isdir(session_dir) and (now - os.path.getmtime(session_dir)) > 3600:
            shutil.rmtree(session_dir, ignore_errors=True)

# Run cleanup on startup
cleanup_old_sessions()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
