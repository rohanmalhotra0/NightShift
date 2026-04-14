"""Contact form API routes."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from database.models import ContactSubmission

router = APIRouter()


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str | None = None
    message: str


class ContactResponse(BaseModel):
    success: bool
    message: str


@router.post("/submit", response_model=ContactResponse)
async def submit_contact(request: ContactRequest, db: Session = Depends(get_db)):
    """Submit a contact form."""
    if len(request.name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name must be at least 2 characters",
        )

    if len(request.message) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message must be at least 10 characters",
        )

    submission = ContactSubmission(
        name=request.name,
        email=request.email,
        subject=request.subject,
        message=request.message,
    )
    db.add(submission)
    db.commit()

    return ContactResponse(
        success=True,
        message="Thank you for your message. We'll get back to you soon.",
    )
