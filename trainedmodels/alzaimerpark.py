"""
AI Model utilities for Alzheimer's and Parkinson's Disease prediction
Core functionality extracted from Flask app for use in API routes
"""
import numpy as np
import cv2
from PIL import Image
import tensorflow as tf
import os
import io
import logging

logger = logging.getLogger(__name__)

# Model configuration
MODEL_PATH = os.path.join(os.path.dirname(__file__), "efficient_net_B0.h5")
MODEL = None

def load_model():
    """Load the AI model with compatibility fixes"""
    global MODEL
    try:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model file not found at: {MODEL_PATH}")
        
        # Custom DepthwiseConv2D class to handle the 'groups' parameter compatibility issue
        class CompatibleDepthwiseConv2D(tf.keras.layers.DepthwiseConv2D):
            def __init__(self, *args, **kwargs):
                # Remove the 'groups' parameter if it exists (not supported in older TF versions)
                kwargs.pop('groups', None)
                super().__init__(*args, **kwargs)
        
        # Create custom objects dictionary for loading
        custom_objects = {
            'DepthwiseConv2D': CompatibleDepthwiseConv2D
        }
        
        # Load model with custom objects
        MODEL = tf.keras.models.load_model(MODEL_PATH, custom_objects=custom_objects)
        print("✅ AI Model loaded successfully!")
        logger.info("AI Model loaded successfully!")
        return MODEL
    except Exception as e:
        error_msg = f"❌ Error loading model: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        MODEL = None
        return None

# Load model on import
load_model()

def validate_image_for_medical_scan(file_bytes):
    """
    Simple validation to reject obvious color photographs
    Only rejects clearly colorful images like photos of people, objects, etc.
    
    Args:
        file_bytes: Raw image file bytes
        
    Returns:
        dict: Validation result with is_valid boolean and reason
    """
    try:
        # Open image for analysis
        image = Image.open(io.BytesIO(file_bytes))
        image_array = np.array(image)
        
        # Only check if image is obviously colorful
        if len(image_array.shape) == 3:
            # Check if image has significant color variation (like photos)
            r, g, b = image_array[:,:,0], image_array[:,:,1], image_array[:,:,2]
            
            # Calculate color differences across the image
            color_diff = np.mean(np.abs(r.astype(float) - g.astype(float))) + \
                        np.mean(np.abs(g.astype(float) - b.astype(float))) + \
                        np.mean(np.abs(r.astype(float) - b.astype(float)))
            
            # If there's significant color difference, it's likely a colorful photo
            if color_diff > 20:  # Threshold for obvious color photos
                return {
                    'is_valid': False,
                    'reason': 'This appears to be a color photograph. Please upload a medical scan (MRI, CT, X-ray, etc.).'
                }
        
        # If it passes the basic color check, allow it
        return {
            'is_valid': True,
            'reason': 'Image accepted for analysis.'
        }
        
    except Exception as e:
        logger.error(f"Image validation error: {str(e)}")
        # If validation fails, allow the image to proceed
        return {
            'is_valid': True,
            'reason': 'Validation skipped due to error.'
        }

def preprocess_image_from_bytes(file_bytes):
    """
    Preprocess image from bytes for model prediction
    
    Args:
        file_bytes: Raw image file bytes
        
    Returns:
        numpy.ndarray: Preprocessed image array ready for prediction
    """
    try:
        # Simple validation to reject obvious color photos
        validation_result = validate_image_for_medical_scan(file_bytes)
        if not validation_result['is_valid']:
            raise ValueError(validation_result['reason'])
        
        image = Image.open(io.BytesIO(file_bytes)).resize((150, 150))
        image_array = np.array(image)

        # Handle different image formats
        if len(image_array.shape) == 2:
            image_array = cv2.cvtColor(image_array, cv2.COLOR_GRAY2RGB)
        elif image_array.shape[-1] == 4:
            image_array = cv2.cvtColor(image_array, cv2.COLOR_RGBA2RGB)

        image_array = np.expand_dims(image_array, axis=0)
        return image_array
    except Exception as e:
        logger.error(f"Image preprocessing error: {str(e)}")
        raise ValueError(f"Failed to preprocess image: {str(e)}")

def image_prediction(image_array):
    """
    Make prediction on preprocessed image array
    
    Args:
        image_array: Preprocessed image array from preprocess_image_from_bytes
        
    Returns:
        dict: Prediction results with class, confidence, and class_id
    """
    try:
        if MODEL is None:
            raise ValueError("Model not loaded")
        
        # Make prediction
        prd = MODEL.predict(image_array, verbose=0)
        class_id = np.argmax(prd, axis=1)[0]
        confidence = float(np.max(prd))
        
        # Map prediction to class names
        class_mapping = {
            0: "CONTROL",
            1: "AD",  # Alzheimer's Disease
            2: "PD"   # Parkinson's Disease
        }
        
        prediction = class_mapping.get(class_id, "Unknown")
        
        return {
            'prediction': prediction,
            'confidence': confidence,
            'class_id': int(class_id),
            'raw_probabilities': prd.tolist()
        }
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise ValueError(f"Prediction failed: {str(e)}")

def get_model_info():
    """
    Get information about the loaded model
    
    Returns:
        dict: Model information including status and properties
    """
    if MODEL is None:
        return {
            'loaded': False,
            'path': MODEL_PATH,
            'exists': os.path.exists(MODEL_PATH)
        }
    
    return {
        'loaded': True,
        'path': MODEL_PATH,
        'exists': os.path.exists(MODEL_PATH),
        'input_shape': str(MODEL.input_shape) if hasattr(MODEL, 'input_shape') else 'Unknown',
        'output_shape': str(MODEL.output_shape) if hasattr(MODEL, 'output_shape') else 'Unknown',
        'model_type': str(type(MODEL).__name__)
    }

# Utility functions for external use
def is_model_loaded():
    """Check if model is loaded"""
    return MODEL is not None

def reload_model():
    """Reload the model"""
    return load_model()

# Class mapping for external reference
CLASS_MAPPING = {
    0: "CONTROL",
    1: "AD",  # Alzheimer's Disease  
    2: "PD"   # Parkinson's Disease
}

# Supported image formats
SUPPORTED_FORMATS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}
