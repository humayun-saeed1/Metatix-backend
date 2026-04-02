from fastapi import APIRouter, Depends, HTTPException, status ,File, UploadFile
from sqlalchemy.orm import Session
from app import schema
from app.models.database import get_db
from app.models import models
from app.api import deps
from app.services.upload_services import upload_profile_pic

router = APIRouter()

# --- 1. REQUEST ORGANIZER ROLE ---
@router.post("/request_organizer", status_code=status.HTTP_200_OK)
def request_organizer_role(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    if current_user.role == "Organizer":
        raise HTTPException(status_code=400, detail="You are already an Organizer!")
    
    if current_user.role == "Admin":
         raise HTTPException(status_code=400, detail="Admins cannot request to be Organizers.")

    if current_user.is_organizer_pending:
        raise HTTPException(status_code=400, detail="Your request is already pending.")

    current_user.is_organizer_pending = True
    db.commit()
    
    return {"message": "Request submitted successfully! An Admin will review it shortly."}

# --- 2. GET MY PROFILE ---
@router.get("/me", response_model=schema.UserResponse)
def read_users_me(current_user: models.User = Depends(deps.get_current_user)):
    return current_user

# --- 3. UPDATE MY PROFILE ---
@router.patch("/update_me", response_model=schema.UserResponse)
def update_user_me(
    user_update: schema.UserUpdate, # Ensure you have this in schema.py, or use UserCreate
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    # Only update fields that are provided
    if user_update.name is not None:
        current_user.name = user_update.name
    
    if user_update.email is not None and user_update.email != current_user.email:
        existing_user = db.query(models.User).filter(models.User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = user_update.email
        
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/me/profile-pic")
async def update_profile_picture(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    # 1. Upload to Cloud
    url = upload_profile_pic(file.file, current_user.user_id)
    
    if not url:
        raise HTTPException(status_code=500, detail="Failed to upload image.")

    # 2. Save URL to Database
    current_user.profile_pic_url = url
    db.commit()

    return {"profile_pic_url": url}