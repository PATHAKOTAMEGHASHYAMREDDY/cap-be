#!/usr/bin/env python3
"""
Medical AI Application Backend Server
Flask application with user authentication and database integration
"""

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

# Import routes
from routes.user_routes import user_bp
from routes.prediction_routes import prediction_bp

# Import models for database initialization
from models.user import create_tables, test_connection

# Load environment variables
load_dotenv()

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    app.config['JWT_ALGORITHM'] = 'HS256'
    
    # CORS configuration
    CORS(app, origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ], supports_credentials=True)
    
    # JWT Manager
    jwt = JWTManager(app)
    
    # JWT Error Handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': 'Token expired',
            'message': 'The token has expired. Please log in again.'
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'error': 'Invalid token',
            'message': 'The token is invalid. Please log in again.'
        }), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'error': 'Authorization required',
            'message': 'Request does not contain an access token.'
        }), 401
    
    # Register blueprints
    app.register_blueprint(user_bp, url_prefix='/api/users')
    app.register_blueprint(prediction_bp, url_prefix='/api/predictions')
    
    # Static file serving for downloads
    @app.route('/static/uploads/<filename>')
    def download_file(filename):
        """Serve uploaded files and reports"""
        import os
        uploads_dir = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
        return send_from_directory(uploads_dir, filename)
    
    # Root route
    @app.route('/')
    def root():
        return jsonify({
            'message': 'Medical AI Application Backend API',
            'version': '1.0.0',
            'status': 'running',
            'timestamp': datetime.utcnow().isoformat(),
            'endpoints': {
                'users': '/api/users',
                'predictions': '/api/predictions',
                'health': '/api/health'
            }
        })
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        """Application health check"""
        try:
            # Test database connection
            db_status = test_connection()
            
            # Test AI model status
            from trainedmodels.alzaimerpark import is_model_loaded
            model_status = is_model_loaded()
            
            overall_status = db_status and model_status
            
            return jsonify({
                'status': 'healthy' if overall_status else 'unhealthy',
                'database': 'connected' if db_status else 'disconnected',
                'ai_model': 'loaded' if model_status else 'not_loaded',
                'timestamp': datetime.utcnow().isoformat(),
                'version': '1.0.0'
            }), 200 if overall_status else 503
            
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'database': 'error',
                'ai_model': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 503
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not found',
            'message': 'The requested resource was not found.'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred.'
        }), 500
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad request',
            'message': 'The request could not be understood by the server.'
        }), 400
    
    return app

def setup_logging():
    """Setup application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log')
        ]
    )
    
    # Set specific loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

def initialize_database():
    """Initialize database tables"""
    try:
        print("Initializing database...")
        
        # Test connection first
        if not test_connection():
            print("❌ Database connection failed!")
            return False
        
        print("✅ Database connection successful!")
        
        # Create tables
        create_tables()
        print("✅ Database tables initialized!")
        
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

# Create Flask app
app = create_app()

if __name__ == '__main__':
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("=" * 50)
    print("🏥 Medical AI Application Backend")
    print("=" * 50)
    
    # Initialize database
    if not initialize_database():
        print("❌ Failed to initialize database. Exiting...")
        exit(1)
    
    # Get configuration from environment
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    print(f"🚀 Starting server on {host}:{port}")
    print(f"🔧 Debug mode: {debug}")
    print(f"🌐 CORS enabled for frontend development")
    print("=" * 50)
    
    try:
        # Run the Flask application
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        print(f"❌ Server error: {e}")