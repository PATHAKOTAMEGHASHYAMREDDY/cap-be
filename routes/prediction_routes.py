from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
import json
from config.cloudinary_config import configure_cloudinary

# Import AI model functions
from trainedmodels.alzaimerpark import (
    preprocess_image_from_bytes,
    image_prediction,
    is_model_loaded,
    get_model_info,
    SUPPORTED_FORMATS,
    MODEL
)

# Create blueprint
prediction_bp = Blueprint('predictions', __name__)
logger = logging.getLogger(__name__)

# Ensure Cloudinary is configured
configure_cloudinary()

@prediction_bp.route('/predict', methods=['POST'])
@jwt_required()
def predict():
    """Make prediction on uploaded image"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if model is loaded
        if not is_model_loaded():
            return jsonify({
                'error': 'Model not available',
                'message': 'AI model is not loaded. Please contact support.'
            }), 503
        
        # Check if file is present
        if 'image' not in request.files:
            return jsonify({
                'error': 'No file uploaded',
                'message': 'Please upload an image file'
            }), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select an image file'
            }), 400
        
        # Validate file type
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_extension not in SUPPORTED_FORMATS:
            return jsonify({
                'error': 'Invalid file type',
                'message': f'Allowed file types: {", ".join(SUPPORTED_FORMATS)}'
            }), 400
        
        try:
            # Process the image
            file_bytes = file.read()
            
            # Upload to Cloudinary
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cloudinary_folder = "medical_ai/scans"
            upload_result = cloudinary.uploader.upload(
                file_bytes,
                folder=cloudinary_folder,
                public_id=f"{timestamp}_{secure_filename(file.filename)}",
                resource_type="image"
            )
            
            # Store the Cloudinary URL
            image_url = upload_result['secure_url']
            logger.info(f"Image uploaded to Cloudinary: {image_url}")
            
            # Preprocess and predict
            image_array = preprocess_image_from_bytes(file_bytes)
            raw_prediction = image_prediction(image_array)
            
            # Map prediction to detailed information
            prediction_class = raw_prediction['prediction']
            raw_probs = raw_prediction.get('raw_probabilities', [[0, 0, 0]])[0]
            
            # Create detailed prediction info based on class
            prediction_details = {
                'CONTROL': {
                    'name': 'CONTROL',
                    'full_name': 'Normal Brain Scan',
                    'description': 'The brain scan appears normal with no signs of neurological disorders.',
                    'recommendation': 'Continue regular health monitoring. Maintain a healthy lifestyle with proper diet, exercise, and mental stimulation.'
                },
                'AD': {
                    'name': 'AD',
                    'full_name': 'Alzheimer\'s Disease',
                    'description': 'The scan shows patterns consistent with Alzheimer\'s disease, characterized by brain tissue changes.',
                    'recommendation': 'Consult with a neurologist for comprehensive evaluation and potential treatment options. Early intervention may help manage symptoms.'
                },
                'PD': {
                    'name': 'PD',
                    'full_name': 'Parkinson\'s Disease',
                    'description': 'The scan indicates patterns associated with Parkinson\'s disease, affecting movement and motor functions.',
                    'recommendation': 'Schedule an appointment with a movement disorder specialist. Physical therapy and medication may help manage symptoms.'
                }
            }
            
            current_prediction = prediction_details.get(prediction_class, prediction_details['CONTROL'])
            
            # Get user information
            from models.user import UserOperations
            user = UserOperations.get_user_by_id(current_user_id)
            username = f"{user.first_name} {user.last_name}" if user else f"User {current_user_id}"
            
            # Prepare response
            response_data = {
                'success': True,
                'prediction': {
                    'name': current_prediction['name'],
                    'full_name': current_prediction['full_name'],
                    'description': current_prediction['description'],
                    'recommendation': current_prediction['recommendation'],
                    'confidence': {
                        'control': round(float(raw_probs[0]) * 100, 2),
                        'alzheimer': round(float(raw_probs[1]) * 100, 2),
                        'parkinson': round(float(raw_probs[2]) * 100, 2)
                    },
                    'primary_confidence': round(raw_prediction['confidence'] * 100, 2)
                },
                'metadata': {
                    'filename': file.filename,
                    'timestamp': datetime.utcnow().isoformat(),
                    'user_id': username,
                    'model_version': 'EfficientNetB0',
                    'processing_time': 'N/A'
                },
                'image_url': image_url,
                'disclaimer': 'This AI analysis is for informational purposes only and should not replace professional medical diagnosis. Please consult with a qualified healthcare provider for proper medical evaluation.'
            }
            
            logger.info(f"Prediction made for user {current_user_id}: {prediction_class}")
            return jsonify(response_data), 200
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return jsonify({
                'error': 'Processing failed',
                'message': f'Failed to process image: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.error(f"Prediction endpoint error: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@prediction_bp.route('/generate-report', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)
def generate_report():
    """Generate PDF report for prediction results"""
    
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        current_user_id = get_jwt_identity()
        
        if not current_user_id:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Please log in to generate reports'
            }), 401
        
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No data provided',
                'message': 'Request body must contain analysis results'
            }), 400
        
        # Extract report data
        results = data.get('results')
        filename = data.get('filename', 'analysis_report.pdf')
        
        if not results:
            return jsonify({
                'error': 'Missing results',
                'message': 'Analysis results are required to generate report'
            }), 400
        
        try:
            # Get user information
            from models.user import UserOperations
            user = UserOperations.get_user_by_id(current_user_id)
            
            # Generate PDF report
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
            import io as io_module
            
            # Create PDF buffer
            buffer = io_module.BytesIO()
            
            # Create PDF document with compression
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                topMargin=0.5*inch,
                compress=True
            )
            
            styles = getSampleStyleSheet()
            
            # Simplified styles for better performance
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=20,
                alignment=TA_CENTER,
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                spaceAfter=10,
                spaceBefore=15,
            )
            
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=5,
                alignment=TA_JUSTIFY
            )
            
            # Build PDF content
            story = []
            
            # Header with Model Version
            story.append(Paragraph("Medical AI Analysis Report", title_style))
            story.append(Paragraph("Model: EfficientNetB0", heading_style))
            story.append(Spacer(1, 10))
            
            # Patient/User Information
            story.append(Paragraph("Patient Information", heading_style))
            patient_data = [
                ['Patient Name:', f"{user.first_name} {user.last_name}" if user else "Unknown"],
                ['Email:', user.email if user else "Unknown"],
                ['Analysis Date:', datetime.now().strftime("%B %d, %Y at %I:%M %p")]
            ]
            
            patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
            patient_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ]))
            story.append(patient_table)
            story.append(Spacer(1, 15))
            
            # Analysis Results
            story.append(Paragraph("Analysis Results", heading_style))
            
            # Primary diagnosis
            story.append(Paragraph(f"<b>Primary Diagnosis:</b> {results['full_name']}", normal_style))
            story.append(Paragraph(f"<b>Confidence Level:</b> {results['primary_confidence']:.1f}%", normal_style))
            story.append(Spacer(1, 10))
            
            # Description
            story.append(Paragraph(f"<b>Description:</b> {results['description']}", normal_style))
            story.append(Spacer(1, 10))
            
            # Detailed confidence scores
            story.append(Paragraph("Detailed Confidence Scores", heading_style))
            confidence_data = [
                ['Condition', 'Confidence'],
                ['Normal/Control', f"{results['confidence']['control']:.1f}%"],
                ['Alzheimer\'s Disease', f"{results['confidence']['alzheimer']:.1f}%"],
                ['Parkinson\'s Disease', f"{results['confidence']['parkinson']:.1f}%"]
            ]
            
            confidence_table = Table(confidence_data, colWidths=[3*inch, 3*inch])
            confidence_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ]))
            story.append(confidence_table)
            story.append(Spacer(1, 15))
            
            # Recommendations
            story.append(Paragraph("Medical Recommendations", heading_style))
            story.append(Paragraph(results['recommendation'], normal_style))
            story.append(Spacer(1, 15))
            
            # Disclaimer
            story.append(Paragraph("Important Disclaimer", heading_style))
            disclaimer_text = 'This AI analysis is for informational purposes only and should not replace professional medical diagnosis. Please consult with a qualified healthcare provider for proper medical evaluation.'
            story.append(Paragraph(disclaimer_text, normal_style))
            
            # Footer
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                alignment=TA_CENTER,
            )
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
            story.append(Paragraph("Generated by Medical AI Analysis System - EfficientNetB0", footer_style))
            
            # Get PDF data
            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            # Upload PDF to Cloudinary
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"medical_report_{timestamp}.pdf"
            
            # Save PDF temporarily
            temp_pdf_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'temp', report_filename)
            os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)
            
            with open(temp_pdf_path, 'wb') as f:
                f.write(pdf_data)
            
            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                temp_pdf_path,
                folder="medical_ai/reports",
                public_id=f"{timestamp}_{secure_filename(filename)}",
                resource_type="raw",
                format="pdf"
            )
            
            # Clean up temporary file
            try:
                os.remove(temp_pdf_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary PDF file: {e}")
            
            logger.info(f"PDF report uploaded to Cloudinary: {upload_result['secure_url']}")
            
            return jsonify({
                'success': True,
                'message': 'Report generated successfully',
                'download_url': upload_result['secure_url'],
                'filename': report_filename,
                'content_type': 'application/pdf'
            }), 200
            
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            return jsonify({
                'error': 'PDF Generation failed',
                'message': str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        return jsonify({
            'error': 'Report generation failed',
            'message': str(e)
        }), 500

@prediction_bp.route('/health', methods=['GET'])
def prediction_health():
    """Health check for prediction service"""
    try:
        model_loaded = is_model_loaded()
        health_status = {
            'status': 'healthy' if model_loaded else 'unhealthy',
            'service': 'prediction_service',
            'model_loaded': model_loaded,
            'upload_folder_exists': os.path.exists(UPLOAD_FOLDER),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        status_code = 200 if model_loaded else 503
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.error(f"Prediction health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'prediction_service',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Test endpoint to verify routes are working
@prediction_bp.route('/test', methods=['GET'])
def test_route():
    """Test endpoint to verify prediction routes are working"""
    return jsonify({
        'message': 'Prediction routes are working',
        'timestamp': datetime.utcnow().isoformat(),
        'endpoints': [
            '/predict',
            '/generate-report',
            '/model-status',
            '/health'
        ]
    }), 200

# Model is automatically loaded when alzaimerpark module is imported