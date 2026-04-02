from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Existing variables
    SECRET_KEY: str 
    ALGORITHM: str 
    ACCESS_TOKEN_EXPIRE_MINUTES: int 
    DB_URL: str 
    
    # --- NEW GOOGLE OAUTH VARIABLES ---
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/callback" # We can just hardcode the local URL here!
    

    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "Metatix Support"

    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str 
    TWILIO_PHONE_NUMBER: str

    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    
    class Config:
        env_file = ".env"
  
settings = Settings()
