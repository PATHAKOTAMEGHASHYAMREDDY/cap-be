import cloudinary
import os
from dotenv import load_dotenv

load_dotenv()

def configure_cloudinary():
    """Configure Cloudinary with credentials"""
    cloudinary.config(
        cloud_name="dktvtxucf",
        api_key="323414932774916",
        api_secret="QXMWwaknKWEjJ5hIAC6xKSxeq08",
        secure=True
    )

# Initialize Cloudinary configuration
configure_cloudinary() 