"""Authentication API routes."""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import bcrypt
import jwt

from config import settings
from database import get_db, User, UserPrefs

router = APIRouter()
security = HTTPBearer()


# Request/Response models
class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    is_admin: bool = False


class UserResponse(BaseModel):
    id: str
    email: str
    tier: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Helper functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: str, is_admin: bool = False) -> tuple[str, int]:
    """Create a JWT access token."""
    expires_in = settings.JWT_EXPIRATION_HOURS * 3600
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "is_admin": is_admin,
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_token(token: str) -> tuple[str, bool]:
    """Decode and validate a JWT token. Returns (user_id, is_admin)."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload["sub"], payload.get("is_admin", False)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    user_id, is_admin = decode_token(credentials.credentials)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    return user


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Require admin user."""
    user = await get_current_user(credentials, db)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# Routes
@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
    # Check if email exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Validate password
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    # Check if this is an admin signup
    is_admin = (
        request.email == settings.ADMIN_EMAIL and
        request.password == settings.ADMIN_PASSWORD
    )

    # Create user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        tier="admin" if is_admin else "free",
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create default preferences
    prefs = UserPrefs(user_id=user.id)
    db.add(prefs)
    db.commit()

    # Generate token
    token, expires_in = create_access_token(str(user.id), is_admin)

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        is_admin=is_admin,
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login and get access token."""
    # Check for admin login
    if request.email == settings.ADMIN_EMAIL and request.password == settings.ADMIN_PASSWORD:
        # Find or create admin user
        user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not user:
            user = User(
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                tier="admin",
                is_admin=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            prefs = UserPrefs(user_id=user.id)
            db.add(prefs)
            db.commit()

        token, expires_in = create_access_token(str(user.id), True)
        return TokenResponse(
            access_token=token,
            expires_in=expires_in,
            is_admin=True,
        )

    # Regular login
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
        )

    token, expires_in = create_access_token(str(user.id), user.is_admin)

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        tier=current_user.tier,
        is_admin=current_user.is_admin,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh access token."""
    token, expires_in = create_access_token(str(current_user.id), current_user.is_admin)

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        is_admin=current_user.is_admin,
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout (client should discard token)."""
    return {"message": "Logged out successfully"}


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change user password."""
    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    current_user.password_hash = hash_password(new_password)
    db.commit()

    return {"message": "Password changed successfully"}
