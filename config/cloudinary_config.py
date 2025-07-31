import cloudinary
import os
from dotenv import load_dotenv

load_dotenv()

def configure_cloudinary():
    """Configure Cloudinary with credentials"""
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "dktvtxucf"),
        api_key=os.getenv("CLOUDINARY_API_KEY", "323414932774916"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET", "QXMWwaknKWEjJ5hIAC6xKSxeq08"),
        secure=True
    )

# Initialize Cloudinary configuration
configure_cloudinary() 