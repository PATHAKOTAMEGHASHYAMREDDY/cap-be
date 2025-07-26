from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models.user import UserOperations
import logging
from datetime import datetime
import re

# Create blueprint
user_bp = Blueprint('users', __name__)
logger = logging.getLogger(__name__)

# Email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def validate_email(email):
    """Validate email format"""
    return EMAIL_REGEX.match(email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

def validate_name(name):
    """Validate name format"""
    if not name or len(name.strip()) < 2:
        return False, "Name must be at least 2 characters long"
    if not re.match(r'^[a-zA-Z\s\'-]+$', name):
        return False, "Name can only contain letters, spaces, hyphens, and apostrophes"
    return True, "Name is valid"

@user_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No data provided',
                'message': 'Request body must contain JSON data'
            }), 400
        
        # Extract required fields
        first_name = data.get('firstName', '').strip()
        last_name = data.get('lastName', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        confirm_password = data.get('confirmPassword', '')
        user_type = data.get('userType', 'healthcare').strip()
        agree_to_terms = data.get('agreeToTerms', False)
        
        # Validate required fields
        if not all([first_name, last_name, email, password]):
            return jsonify({
                'error': 'Missing required fields',
                'message': 'First name, last name, email, and password are required'
            }), 400
        
        # Validate terms agreement
        if not agree_to_terms:
            return jsonify({
                'error': 'Terms not accepted',
                'message': 'You must agree to the terms and conditions'
            }), 400
        
        # Validate password confirmation
        if password != confirm_password:
            return jsonify({
                'error': 'Password mismatch',
                'message': 'Password and confirm password do not match'
            }), 400
        
        # Validate first name
        is_valid, message = validate_name(first_name)
        if not is_valid:
            return jsonify({
                'error': 'Invalid first name',
                'message': message
            }), 400
        
        # Validate last name
        is_valid, message = validate_name(last_name)
        if not is_valid:
            return jsonify({
                'error': 'Invalid last name',
                'message': message
            }), 400
        
        # Validate email
        if not validate_email(email):
            return jsonify({
                'error': 'Invalid email',
                'message': 'Please provide a valid email address'
            }), 400
        
        # Validate password
        is_valid, message = validate_password(password)
        if not is_valid:
            return jsonify({
                'error': 'Invalid password',
                'message': message
            }), 400
        
        # Validate user type
        valid_user_types = ['healthcare', 'researcher', 'student', 'other']
        if user_type not in valid_user_types:
            return jsonify({
                'error': 'Invalid user type',
                'message': f'User type must be one of: {", ".join(valid_user_types)}'
            }), 400
        
        # Create user
        try:
            user = UserOperations.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                user_type=user_type
            )
            
            # Create access token
            access_token = create_access_token(identity=user.id)
            
            logger.info(f"User registered successfully: {email}")
            
            return jsonify({
                'message': 'User registered successfully',
                'user': user.to_dict(),
                'access_token': access_token
            }), 201
            
        except ValueError as e:
            if "already exists" in str(e):
                return jsonify({
                    'error': 'Email already registered',
                    'message': 'An account with this email already exists'
                }), 409
            else:
                return jsonify({
                    'error': 'Registration failed',
                    'message': str(e)
                }), 400
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred during registration'
        }), 500

@user_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return access token"""
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No data provided',
                'message': 'Request body must contain JSON data'
            }), 400
        
        # Extract credentials
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        remember_me = data.get('rememberMe', False)
        
        # Validate required fields
        if not email or not password:
            return jsonify({
                'error': 'Missing credentials',
                'message': 'Email and password are required'
            }), 400
        
        # Validate email format
        if not validate_email(email):
            return jsonify({
                'error': 'Invalid email',
                'message': 'Please provide a valid email address'
            }), 400
        
        # Authenticate user
        try:
            user = UserOperations.authenticate_user(email, password)
        except Exception as auth_error:
            logger.error(f"Authentication error for {email}: {auth_error}")
            return jsonify({
                'error': 'Authentication failed',
                'message': 'Database error during authentication'
            }), 500
        
        if not user:
            logger.warning(f"Failed login attempt for email: {email}")
            return jsonify({
                'error': 'Invalid credentials',
                'message': 'Email or password is incorrect'
            }), 401
        
        if not user.is_active:
            return jsonify({
                'error': 'Account deactivated',
                'message': 'Your account has been deactivated. Please contact support.'
            }), 401
        
        # Create access token with extended expiry if remember me is checked
        expires_delta = None
        if remember_me:
            from datetime import timedelta
            expires_delta = timedelta(days=30)  # 30 days for remember me
        
        access_token = create_access_token(
            identity=user.id,
            expires_delta=expires_delta
        )
        
        logger.info(f"User logged in successfully: {email}")
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred during login'
        }), 500

@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    try:
        # Get current user ID from JWT
        current_user_id = get_jwt_identity()
        
        # Get user from database
        user = UserOperations.get_user_by_id(current_user_id)
        
        if not user:
            return jsonify({
                'error': 'User not found',
                'message': 'User account no longer exists'
            }), 404
        
        if not user.is_active:
            return jsonify({
                'error': 'Account deactivated',
                'message': 'Your account has been deactivated'
            }), 401
        
        return jsonify({
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred while fetching profile'
        }), 500

@user_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update current user profile"""
    try:
        # Get current user ID from JWT
        current_user_id = get_jwt_identity()
        
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No data provided',
                'message': 'Request body must contain JSON data'
            }), 400
        
        # Extract updatable fields
        updates = {}
        
        if 'firstName' in data:
            first_name = data['firstName'].strip()
            is_valid, message = validate_name(first_name)
            if not is_valid:
                return jsonify({
                    'error': 'Invalid first name',
                    'message': message
                }), 400
            updates['first_name'] = first_name
        
        if 'lastName' in data:
            last_name = data['lastName'].strip()
            is_valid, message = validate_name(last_name)
            if not is_valid:
                return jsonify({
                    'error': 'Invalid last name',
                    'message': message
                }), 400
            updates['last_name'] = last_name
        
        if 'userType' in data:
            user_type = data['userType'].strip()
            valid_user_types = ['healthcare', 'researcher', 'student', 'other']
            if user_type not in valid_user_types:
                return jsonify({
                    'error': 'Invalid user type',
                    'message': f'User type must be one of: {", ".join(valid_user_types)}'
                }), 400
            updates['user_type'] = user_type
        
        if not updates:
            return jsonify({
                'error': 'No valid fields to update',
                'message': 'Please provide at least one field to update'
            }), 400
        
        # Update user
        user = UserOperations.update_user(current_user_id, **updates)
        
        logger.info(f"User profile updated: {user.email}")
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({
            'error': 'Update failed',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred while updating profile'
        }), 500

@user_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        # Get current user ID from JWT
        current_user_id = get_jwt_identity()
        
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No data provided',
                'message': 'Request body must contain JSON data'
            }), 400
        
        # Extract password fields
        old_password = data.get('oldPassword', '')
        new_password = data.get('newPassword', '')
        confirm_password = data.get('confirmPassword', '')
        
        # Validate required fields
        if not all([old_password, new_password, confirm_password]):
            return jsonify({
                'error': 'Missing required fields',
                'message': 'Old password, new password, and confirm password are required'
            }), 400
        
        # Validate password confirmation
        if new_password != confirm_password:
            return jsonify({
                'error': 'Password mismatch',
                'message': 'New password and confirm password do not match'
            }), 400
        
        # Validate new password
        is_valid, message = validate_password(new_password)
        if not is_valid:
            return jsonify({
                'error': 'Invalid new password',
                'message': message
            }), 400
        
        # Change password
        try:
            UserOperations.change_password(current_user_id, old_password, new_password)
            
            logger.info(f"Password changed for user ID: {current_user_id}")
            
            return jsonify({
                'message': 'Password changed successfully'
            }), 200
            
        except ValueError as e:
            return jsonify({
                'error': 'Password change failed',
                'message': str(e)
            }), 400
        
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred while changing password'
        }), 500

@user_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token removal)"""
    try:
        current_user_id = get_jwt_identity()
        logger.info(f"User logged out: {current_user_id}")
        
        return jsonify({
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred during logout'
        }), 500

# Health check for user routes
@user_bp.route('/health', methods=['GET'])
def user_health():
    """Health check for user routes"""
    try:
        # Test database connection
        from models.user import get_session
        from sqlalchemy import text
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        
        return jsonify({
            'status': 'healthy',
            'service': 'user_routes',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'user_routes',
            'database': 'disconnected',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Debug endpoint to check database status
@user_bp.route('/debug/db-status', methods=['GET'])
def debug_db_status():
    """Debug endpoint to check database status"""
    try:
        from models.user import get_session, User
        
        session = get_session()
        
        # Test basic query
        user_count = session.query(User).count()
        session.close()
        
        return jsonify({
            'database_status': 'connected',
            'user_count': user_count,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Database debug check failed: {e}")
        return jsonify({
            'database_status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500