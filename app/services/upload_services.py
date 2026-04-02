import cloudinary
import cloudinary.uploader
from app.core.config import settings

# Configure Cloudinary with your .env keys
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)

def upload_profile_pic(file_object, user_id: int):
    """Uploads a file and returns the secure URL."""
    try:
        result = cloudinary.uploader.upload(
            file_object,
            folder="metatix/profiles",
            public_id=f"user_{user_id}", # Overwrites if they upload a new one
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"}
            ]
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"Cloudinary Error: {e}")
        return None