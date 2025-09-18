from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import timedelta , datetime
from typing import Optional, Union
import json

from database.db import get_db
from database.model import User
from utils.auth import (
    authenticate_user, create_access_token, get_current_user,
    create_user_account, get_password_hash
)
from config import settings

router = APIRouter()

# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str
    user_type: str
    user_name: str
    employee_id: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    user_type: str
    employee_id: Optional[str]
    full_name: str
    department: Optional[str]
    is_active: bool

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    user_type: str
    employee_id: str
    full_name: str
    department: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    """Login endpoint that accepts both JSON and form data"""
    
    # Get content type
    content_type = request.headers.get('content-type', '')
    
    try:
        if 'application/json' in content_type:
            # Handle JSON request
            body = await request.body()
            data = json.loads(body)
            email = data.get('username') or data.get('email')
            password = data.get('password')
        elif 'application/x-www-form-urlencoded' in content_type:
            # Handle form data
            form = await request.form()
            email = form.get('username')
            password = form.get('password')
        else:
            # Try to parse as form data anyway
            try:
                form = await request.form()
                email = form.get('username')
                password = form.get('password')
            except:
                # Fallback to JSON
                body = await request.body()
                data = json.loads(body)
                email = data.get('username') or data.get('email')
                password = data.get('password')
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request format: {str(e)}"
        )
    
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required"
        )
    
    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_type=user.user_type,
        user_name=user.full_name,
        employee_id=user.employee_id
    )

@router.post("/login-form", response_model=Token)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Alternative login endpoint specifically for form data"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_type=user.user_type,
        user_name=user.full_name,
        employee_id=user.employee_id
    )

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Register new user (admin only)"""
    if current_user.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can create new users"
        )
    
    user = create_user_account(
        db=db,
        email=user_data.email,
        password=user_data.password,
        user_type=user_data.user_type,
        employee_id=user_data.employee_id,
        full_name=user_data.full_name,
        department=user_data.department
    )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        user_type=user.user_type,
        employee_id=user.employee_id,
        full_name=user.full_name,
        department=user.department,
        is_active=user.is_active
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        user_type=current_user.user_type,
        employee_id=current_user.employee_id,
        full_name=current_user.full_name,
        department=current_user.department,
        is_active=current_user.is_active
    )

@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    from utils.auth import verify_password
    
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}

@router.post("/create-teacher-accounts")
async def create_teacher_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Auto-create teacher accounts from faculty data (admin only)"""
    if current_user.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can create teacher accounts"
        )
    
    from database.model import Faculty
    
    faculties = db.query(Faculty).all()
    created_count = 0
    
    for faculty in faculties:
        # Check if user already exists
        existing_user = db.query(User).filter(
            User.email == faculty.email
        ).first()
        
        if not existing_user and faculty.email:
            user = User(
                email=faculty.email,
                hashed_password=get_password_hash(settings.DEFAULT_TEACHER_PASSWORD),
                user_type="teacher",
                employee_id=faculty.employee_id,
                full_name=faculty.full_name,
                department=faculty.department
            )
            db.add(user)
            created_count += 1
    
    db.commit()
    return {"message": f"Created {created_count} teacher accounts"}

@router.post("/logout")
async def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Logged out successfully"}

@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {"message": "Auth API is working!", "timestamp": str(datetime.now())}