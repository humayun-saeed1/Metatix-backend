from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from app.core.config import settings
from app.models.database import get_db
from sqlalchemy.orm import Session
from app.services import user_services
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # This is the error we throw if things go wrong
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. DECODE THE TOKEN 
        # Hint: Use jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # 2. GET THE EMAIL
        email: str = payload.get("sub")
        
        if email is None:
            raise credentials_exception
            
    except JWTError:
        # If the token is fake or expired, we land here
        raise credentials_exception

    # 3. CHECK THE DATABASE
    user = user_services.get_user_by_email(db, email=email)
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been banned by an Administrator.")
        
    return user