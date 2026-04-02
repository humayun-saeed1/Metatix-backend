import requests
from fastapi import APIRouter, Depends, HTTPException, status , BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.models import models
from app.models.database import get_db
from app import schema
from app.services import user_services , email_services , sms_services
from app.core import security
from app.api import deps
from app.core.security import verify_password, get_password_hash
from app.services.email_services import send_reset_password_email

# Import your settings to access the Google Client ID & Secret
from app.core.config import settings 

router = APIRouter()

# --- 1. REGISTER ---
@router.post("/registeration", response_model=schema.UserResponse)
def create_user(user: schema.UserCreate,background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    db_user = user_services.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = user_services.create_user(db=db, user=user)
    background_tasks.add_task(email_services.send_welcome_email, new_user.email, new_user.name)
    if new_user.phone_number:
        background_tasks.add_task(sms_services.send_welcome_sms, new_user.phone_number, new_user.name)   
    return new_user

# --- 2. LOGIN ---
@router.post("/login", response_model=schema.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    

    user = user_services.authenticate_user(db, form_data.username, form_data.password)

  

    if not user:
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = security.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# --- 3. CHANGE PASSWORD ---
@router.patch("/change-password")
def change_password(
    password_data: schema.ChangePasswordRequest, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Verifies old password and sets the new one.
    """
    # A. Verify Old Password
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    # B. Prevent reusing the same password
    if password_data.old_password == password_data.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be the same as old password")

    # C. Hash & Save
    current_user.password_hash = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}


# ==========================================
# --- 4. GOOGLE OAUTH 2.0 LOGIC ---
# ==========================================

@router.get("/google/login")
def google_login():
    """
    Step 1: Redirects the user to Google's consent screen.
    """
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
    )
    return RedirectResponse(url=google_auth_url)


@router.get("/callback")
def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Step 2: Google redirects here with an authorization code.
    We exchange it for a token, get user info, and log them in.
    """
    # A. Exchange the code for an Access Token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_res = requests.post(token_url, data=token_data)
    token_json = token_res.json()
  
    access_token = token_json.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to get access token from Google")

    # B. Use the Access Token to fetch the user's Google Profile
    user_info_res = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_info = user_info_res.json()

    email = user_info.get("email")
    name = user_info.get("name")
    picture = user_info.get("picture") # The profile picture URL!

    if not email:
        raise HTTPException(status_code=400, detail="Google did not provide an email address.")

    # C. Find or Create the User in your Database
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        # New user! Create them in the database.
        user = models.User(
            email=email,
            name=name,
            profile_pic_url=picture,  # Save the Google profile picture
            role=models.UserRole.CUSTOMER, # Default role for new signups
            is_active=True,
            password_hash=None, # No local password for Google users
            auth_provider="google"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Existing user! Update their profile picture to keep it fresh
        user.profile_pic_url = picture
        db.commit()

    # D. Generate your own Metatix Access Token
    metatix_token = security.create_access_token(data={"sub": user.email})

    # E. Send the user back to your React frontend with the token
    # React will grab this token from the URL and save it to localStorage
    frontend_redirect_url = f"http://localhost:5173/login-success?token={metatix_token}"
    return RedirectResponse(url=frontend_redirect_url)


# ==========================================
# --- 5. PASSWORD RECOVERY LOGIC ---
# ==========================================

@router.post("/forgot-password")
def forgot_password(req: schema.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    
    # 1. Security Best Practice
    if not user:
        return {"message": "If that email exists in our system, a reset link has been sent."}

    # 2. Block Google Users
    if user.auth_provider == "google":
        raise HTTPException(
            status_code=400, 
            detail="You signed up with Google. Please reset your password through your Google account."
        )

    # 3. Generate the 15-minute JWT token
    reset_token = security.create_password_reset_token(email=user.email)
    
    # 4. 🚀 THE MAGIC: Send the actual email
    email_sent = send_reset_password_email(email_to=user.email, reset_token=reset_token)

    if not email_sent:
        raise HTTPException(
            status_code=500, 
            detail="There was a problem sending the email. Please try again later."
        )

    return {"message": "If that email exists in our system, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(req: schema.ResetPasswordRequest, db: Session = Depends(get_db)):
    # 1. Verify the token is valid, hasn't expired, and is a "reset" type
    email = security.verify_password_reset_token(req.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    # 2. Find the user
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 3. Hash the new password and lock it in the database
    user.password_hash = security.get_password_hash(req.new_password)
    db.commit()

    return {"message": "Password has been reset successfully. You can now log in."}