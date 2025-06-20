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
import sqlite3
import logging
from werkzeug.serving import run_simple

# Import routes
from src.routes.geotagging import geotagging_bp
from src.routes.conversion import conversion_bp
from src.routes.resizing import resizing_bp
from src.routes.watermark import watermark_bp
from src.routes.presets import presets_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Configure app
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'image_processor_uploads')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB max upload size (reduced from 2GB)
app.config['SESSION_FOLDER'] = os.path.join(tempfile.gettempdir(), 'image_processor_sessions')
app.config['PROCESSED_FOLDER'] = os.path.join(tempfile.gettempdir(), 'image_processor_processed')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for file downloads
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session lifetime

# Register blueprints
app.register_blueprint(geotagging_bp, url_prefix='/api/geotagging')
app.register_blueprint(conversion_bp, url_prefix='/api/conversion')
app.register_blueprint(resizing_bp, url_prefix='/api/resizing')
app.register_blueprint(watermark_bp, url_prefix='/api/watermark')
app.register_blueprint(presets_bp, url_prefix='/api/presets')

# Create necessary folders with proper permissions
for folder in [app.config['UPLOAD_FOLDER'], app.config['SESSION_FOLDER'], app.config['PROCESSED_FOLDER']]:
    try:
        os.makedirs(folder, exist_ok=True)
        # Ensure the folder is writable
        test_file = os.path.join(folder, '.test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except Exception as e:
        logger.error(f"Error creating/verifying folder {folder}: {e}")
        raise

# Ensure static data directory exists
static_data_dir = os.path.join(os.path.dirname(__file__), 'static', 'data')
os.makedirs(static_data_dir, exist_ok=True)

# Main route
@app.route('/')
def index():
    return render_template('index.html')

# Serve static files with proper caching headers
@app.route('/<path:filename>')
def serve_static(filename):
    response = app.send_static_file(filename)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Download processed files with proper error handling
@app.route('/download/<session_id>')
def download_file(session_id):
    try:
        session_dir = os.path.join(app.config['SESSION_FOLDER'], session_id)
        
        if not os.path.exists(session_dir):
            logger.error(f"Session directory not found: {session_dir}")
            return jsonify({'error': 'Session not found'}), 404
        
        # Check if there's a zip file already
        zip_path = os.path.join(session_dir, 'processed.zip')
        
        if not os.path.exists(zip_path):
            # Create a zip file of all processed files
            try:
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for root, _, files in os.walk(session_dir):
                        if root == session_dir:
                            continue
                            
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, session_dir)
                            zipf.write(file_path, arcname)
            except Exception as e:
                logger.error(f"Error creating zip file: {e}")
                return jsonify({'error': 'Failed to create zip file'}), 500
        
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name='processed_images.zip',
            mimetype='application/zip'
        )
        
        # Add headers to prevent caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Error in download_file: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Error handlers with logging
@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 error: {request.url}")
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"500 error: {str(error)}")
    return jsonify({'error': 'Server error'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

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

# Snake game routes
@app.route('/snake')
def snake_game():
    return render_template('snake.html')

@app.route('/api/snake/scores', methods=['GET'])
def get_snake_scores():
    try:
        country = request.args.get('country')
        state = request.args.get('state')
        city = request.args.get('city')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT s.username, s.score, l.country, l.state_province, l.city
            FROM snake_scores s
            JOIN locations l ON s.location_id = l.id
            WHERE 1=1
        '''
        params = []
        
        if country:
            query += ' AND l.country = ?'
            params.append(country)
        if state:
            query += ' AND l.state_province = ?'
            params.append(state)
        if city:
            query += ' AND l.city = ?'
            params.append(city)
            
        query += '''
            GROUP BY s.username, l.country, l.state_province, l.city
            ORDER BY s.score DESC
            LIMIT 10
        '''
        
        cursor.execute(query, params)
        scores = [{
            'username': row[0],
            'score': row[1],
            'country': row[2],
            'state': row[3],
            'city': row[4]
        } for row in cursor.fetchall()]
        
        conn.close()
        return jsonify(scores)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snake/scores', methods=['POST'])
def save_snake_score():
    try:
        data = request.get_json()
        username = data.get('username')
        score = data.get('score')
        country = data.get('country')
        state = data.get('state')
        city = data.get('city')
        
        if not username or not isinstance(score, (int, float)) or not country:
            return jsonify({'error': 'Invalid data'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get or create location
        cursor.execute('''
            INSERT OR IGNORE INTO locations (country, state_province, city)
            VALUES (?, ?, ?)
        ''', (country, state, city))
        
        cursor.execute('''
            SELECT id FROM locations 
            WHERE country = ? AND state_province = ? AND city = ?
        ''', (country, state, city))
        
        location_id = cursor.fetchone()[0]
        
        # Save score
        cursor.execute('''
            INSERT INTO snake_scores (username, score, location_id, timestamp)
            VALUES (?, ?, ?, datetime('now'))
        ''', (username, score, location_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/snake/locations', methods=['GET'])
def get_locations():
    try:
        # Load the city presets file
        with open('src/static/data/city_presets.json', 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect('snake_scores.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create snake_scores table if it doesn't exist
def init_snake_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create locations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            state_province TEXT,
            city TEXT,
            UNIQUE(country, state_province, city)
        )
    ''')
    
    # Create snake_scores table with location reference
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS snake_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            score INTEGER NOT NULL,
            location_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES locations (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize snake database
init_snake_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
