"""
Flask REST API Server
Provides endpoints for:
- File upload with hash verification
- File download
- Keyboard emulation for process control
"""

import os
import hashlib
import logging
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import keyboard emulation module
try:
    from keyboard_emulator import KeyboardEmulator
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    logging.warning("Keyboard emulation not available - evdev module not found")

# Import process manager module
try:
    from process_manager import ProcessManager
    PROCESS_MANAGER_AVAILABLE = True
except ImportError:
    PROCESS_MANAGER_AVAILABLE = False
    logging.warning("Process manager not available - psutil module not found")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB max file size
ALLOWED_EXTENSIONS = set()  # Allow all extensions

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload folder exists
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

# Initialize keyboard emulator if available
keyboard_emulator = None
if KEYBOARD_AVAILABLE:
    try:
        keyboard_emulator = KeyboardEmulator()
        logger.info("Keyboard emulator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize keyboard emulator: {e}")

# Initialize process manager if available
process_manager = None
if PROCESS_MANAGER_AVAILABLE:
    try:
        process_manager = ProcessManager()
        logger.info("Process manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize process manager: {e}")


def calculate_file_hash(filepath, algorithm='sha256'):
    """Calculate hash of a file."""
    hash_func = hashlib.new(algorithm)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def verify_hash(filepath, expected_hash, algorithm='sha256'):
    """Verify file hash matches expected value."""
    actual_hash = calculate_file_hash(filepath, algorithm)
    return actual_hash.lower() == expected_hash.lower()


@app.route('/')
def index():
    """Root endpoint - API information."""
    return jsonify({
        'name': 'Flask REST API',
        'version': '1.0.0',
        'endpoints': {
            '/': 'API information',
            '/upload': 'POST - Upload file with hash verification',
            '/download/<filename>': 'GET - Download file',
            '/files': 'GET - List uploaded files',
            '/keyboard': 'POST - Send keyboard input',
            '/health': 'GET - Health check'
        },
        'keyboard_emulation': KEYBOARD_AVAILABLE
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'keyboard_emulation': KEYBOARD_AVAILABLE
    })


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload a file with optional hash verification.
    
    Form data:
    - file: The file to upload
    - hash: (optional) Expected hash value for verification
    - algorithm: (optional) Hash algorithm (default: sha256)
    
    Returns:
        JSON response with upload status and file hash
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Secure the filename
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save the file
        file.save(filepath)
        logger.info(f"File saved: {filename}")
        
        # Calculate file hash
        algorithm = request.form.get('algorithm', 'sha256')
        try:
            file_hash = calculate_file_hash(filepath, algorithm)
        except Exception as e:
            os.remove(filepath)
            return jsonify({'error': f'Hash calculation failed: {str(e)}'}), 500
        
        # Verify hash if provided
        expected_hash = request.form.get('hash')
        hash_verified = None
        
        if expected_hash:
            hash_verified = verify_hash(filepath, expected_hash, algorithm)
            if not hash_verified:
                os.remove(filepath)
                return jsonify({
                    'error': 'Hash verification failed',
                    'expected_hash': expected_hash,
                    'actual_hash': file_hash
                }), 400
            logger.info(f"Hash verified successfully for {filename}")
        
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename,
            'size': os.path.getsize(filepath),
            'hash': file_hash,
            'algorithm': algorithm,
            'hash_verified': hash_verified
        }), 201
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>')
def download_file(filename):
    """
    Download a file.
    
    Args:
        filename: Name of the file to download
        
    Returns:
        File content or error message
    """
    try:
        # Secure the filename
        filename = secure_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        # Calculate hash for response header
        file_hash = calculate_file_hash(filepath)
        
        response = send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
        
        # Add hash to response headers
        response.headers['X-File-Hash'] = file_hash
        response.headers['X-Hash-Algorithm'] = 'sha256'
        
        logger.info(f"File downloaded: {filename}")
        return response
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/files')
def list_files():
    """
    List all uploaded files with their metadata.
    
    Returns:
        JSON list of files with size and hash
    """
    try:
        files = []
        upload_dir = Path(app.config['UPLOAD_FOLDER'])
        
        for filepath in upload_dir.glob('*'):
            if filepath.is_file():
                files.append({
                    'filename': filepath.name,
                    'size': filepath.stat().st_size,
                    'modified': filepath.stat().st_mtime,
                    'hash': calculate_file_hash(str(filepath))
                })
        
        return jsonify({
            'count': len(files),
            'files': sorted(files, key=lambda x: x['modified'], reverse=True)
        })
        
    except Exception as e:
        logger.error(f"List files error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/keyboard', methods=['POST'])
def keyboard_input():
    """
    Send keyboard input to emulate keypresses.
    
    JSON body:
    {
        "text": "string to type",
        "keys": ["KEY_A", "KEY_ENTER"],
        "delay": 0.1
    }
    
    Returns:
        JSON response with status
    """
    if not KEYBOARD_AVAILABLE or keyboard_emulator is None:
        return jsonify({
            'error': 'Keyboard emulation not available',
            'message': 'evdev module not installed or keyboard device not initialized'
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        text = data.get('text')
        keys = data.get('keys', [])
        delay = data.get('delay', 0.1)
        
        if not text and not keys:
            return jsonify({'error': 'Either "text" or "keys" must be provided'}), 400
        
        # Type text if provided
        if text:
            keyboard_emulator.type_text(text, delay)
            logger.info(f"Typed text: {text[:50]}...")
        
        # Send specific keys if provided
        if keys:
            for key in keys:
                keyboard_emulator.send_key(key, delay)
            logger.info(f"Sent keys: {keys}")
        
        return jsonify({
            'message': 'Keyboard input sent successfully',
            'text': text if text else None,
            'keys': keys if keys else None
        })
        
    except Exception as e:
        logger.error(f"Keyboard input error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error."""
    return jsonify({
        'error': 'File too large',
        'max_size': f'{MAX_CONTENT_LENGTH / (1024*1024)} MB'
    }), 413


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


@app.route('/process/start', methods=['POST'])
def start_process():
    """
    Start a process and check if it's already running.
    
    JSON body:
    {
        "command": "command to run" or ["command", "arg1", "arg2"],
        "check_running": true (optional, default true),
        "cwd": "/path/to/working/dir" (optional),
        "env": {"VAR": "value"} (optional)
    }
    
    Returns:
        JSON response with process status
    """
    if not PROCESS_MANAGER_AVAILABLE or process_manager is None:
        return jsonify({
            'error': 'Process management not available',
            'message': 'psutil module not installed'
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        command = data.get('command')
        if not command:
            return jsonify({'error': '"command" is required'}), 400
        
        check_running = data.get('check_running', True)
        cwd = data.get('cwd')
        env = data.get('env')
        
        result = process_manager.start_process(
            command=command,
            check_running=check_running,
            cwd=cwd,
            env=env
        )
        
        return jsonify(result)
        
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Process start error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/process/stop', methods=['POST'])
def stop_process():
    """
    Stop a running process.
    
    JSON body:
    {
        "process": "process name or command"
    }
    
    Returns:
        JSON response with status
    """
    if not PROCESS_MANAGER_AVAILABLE or process_manager is None:
        return jsonify({
            'error': 'Process management not available',
            'message': 'psutil module not installed'
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        process_name = data.get('process')
        if not process_name:
            return jsonify({'error': '"process" is required'}), 400
        
        result = process_manager.stop_process(process_name)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Process stop error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/process/status/<process_name>', methods=['GET'])
def get_process_status(process_name):
    """
    Get status of a process.
    
    Args:
        process_name: Name of the process
        
    Returns:
        JSON response with process status
    """
    if not PROCESS_MANAGER_AVAILABLE or process_manager is None:
        return jsonify({
            'error': 'Process management not available',
            'message': 'psutil module not installed'
        }), 503
    
    try:
        result = process_manager.get_process_status(process_name)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Process status error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/process/list', methods=['GET'])
def list_processes():
    """
    List all managed processes.
    
    Returns:
        JSON response with list of processes
    """
    if not PROCESS_MANAGER_AVAILABLE or process_manager is None:
        return jsonify({
            'error': 'Process management not available',
            'message': 'psutil module not installed'
        }), 503
    
    try:
        processes = process_manager.list_managed_processes()
        return jsonify({
            'processes': processes,
            'count': len(processes)
        })
        
    except Exception as e:
        logger.error(f"Process list error: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Run the server
    # For production, use a proper WSGI server like gunicorn
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Flask REST API on {host}:{port}")
    logger.info(f"Upload folder: {UPLOAD_FOLDER}")
    logger.info(f"Keyboard emulation: {'enabled' if KEYBOARD_AVAILABLE else 'disabled'}")
    logger.info(f"Process management: {'enabled' if PROCESS_MANAGER_AVAILABLE else 'disabled'}")
    
    app.run(host=host, port=port, debug=debug)
