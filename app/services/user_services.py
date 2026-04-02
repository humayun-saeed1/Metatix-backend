from sqlalchemy.orm import Session
from app.models import models
from app import schema
from app.core import security

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schema.UserCreate):
    # 1. Hash the password here
    hashed_password = security.get_password_hash(user.password)
    
    # 2. Create the user model
    db_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hashed_password, # Save the hash, not the plain password
        role="Customer",
        auth_provider="local",  # Default role
        phone_number=user.phone_number
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str):
    # 1. Check if user exists
    print("   -> A. Inside authenticate_user, starting DB query...")
    user = get_user_by_email(db, email=email)
    print(f"   -> B. DB query finished! User found: {bool(user)}")
    if not user:
        return False
    print("   -> C. Starting password verification...")

    is_valid = security.verify_password(password, user.password_hash)
    

    print(f"   -> D. Password check finished! Valid: {is_valid}")
    
    # 2. Verify password
    if not is_valid:
        return False
    
    
    return user