from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship, Session
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import secrets
import string
import asyncio
from auth import route as auth_router, Base, engine, get_db, User, get_current_user, IST

app = FastAPI(title="Time-Capsule")

app.include_router(auth_router)

# Capsule model with expiration flag
class Capsule(Base):
    __tablename__ = "capsules"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    unlock_at = Column(DateTime, nullable=False) 
    created_at = Column(DateTime, default=lambda: datetime.now(IST)) 
    unlock_code = Column(String(12), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    expired = Column(Boolean, default=False)  # New column for expiration status

    user = relationship("User", back_populates="capsules")

User.capsules = relationship("Capsule", back_populates="user")

Base.metadata.create_all(bind=engine)

# Pydantic models
class CapsuleCreate(BaseModel):
    message: str
    unlock_at: datetime  

class CapsuleUpdate(BaseModel):
    message: Optional[str] = None
    unlock_at: Optional[datetime] = None

class CapsuleUpdateRespone(BaseModel):
    message: str
    unlock_at: datetime

class CapsuleResponse(BaseModel):
    id: int
    unlock_code: str
    unlock_at: datetime

    class Config:
        from_attributes = True

class CapsuleFullResponse(BaseModel):
    id: int
    message: str
    unlock_at: datetime
    created_at: datetime
    user_id: int

    class Config:
        from_attributes = True
        
class CapsuleListItem(BaseModel):
    id: int
    unlock_code: str
    unlock_at: datetime
    created_at: datetime
    is_unlockable: bool
    expired: bool  # Added expired field
    
    class Config:
        from_attributes = True
        
class CapsuleListResponse(BaseModel):
    capsules: List[CapsuleListItem]
    total: int
    page: int
    limit: int
    total_pages: int
    
    class Config:
        from_attributes = True

# Helper function to ensure datetime is timezone-aware with IST
def ensure_timezone_aware(dt):
    """Ensure datetime is timezone-aware with IST timezone"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    elif dt.tzinfo != IST:
        return dt.astimezone(IST)
    return dt

# Generate unlock code
def generate_unlock_code(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Background expiration task
async def check_expirations():
    """
    Background task that runs every hour to check for expired capsules.
    A capsule is considered expired when current_time > unlock_at + 30 days.
    """
    while True:
        try:
            db = next(get_db())
            current_time = datetime.now(IST)
            
            # Find capsules that need to be marked as expired
            # (unlock_at + 30 days < current_time AND not already marked expired)
            expired_capsules = db.query(Capsule).filter(
                Capsule.expired == False
            ).all()
            
            # Mark as expired if needed
            for capsule in expired_capsules:
                unlock_at = ensure_timezone_aware(capsule.unlock_at)
                if unlock_at + timedelta(days=30) < current_time:
                    capsule.expired = True
            
            # Commit changes if any capsules were updated
            if expired_capsules:
                db.commit()
                print(f"Checked {len(expired_capsules)} capsules for expiration")
                
        except Exception as e:
            print(f"Error in expiration check: {e}")
        finally:
            db.close()
        
        # Run every hour (3600 seconds)
        await asyncio.sleep(3600)

@app.get("/")
def welcome():
    return {"This is Time-Capsule"}

@app.post("/capsules", response_model=CapsuleResponse)
async def create_capsule(
    capsule: CapsuleCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    username = current_user["username"]
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure timezone awareness
    unlock_at = ensure_timezone_aware(capsule.unlock_at)
    
    # Check if unlock time is in the future
    if unlock_at <= datetime.now(IST):
        raise HTTPException(
            status_code=400,
            detail="Unlock time must be in the future"
        )

    unlock_code = generate_unlock_code()

    new_capsule = Capsule(
        message=capsule.message,
        unlock_at=unlock_at,
        unlock_code=unlock_code,
        user_id=user.id,
        expired=False
    )

    db.add(new_capsule)
    db.commit()
    db.refresh(new_capsule)

    return {
        "id": new_capsule.id,
        "unlock_code": new_capsule.unlock_code,
        "unlock_at": new_capsule.unlock_at
    }


@app.get("/capsules", response_model=CapsuleListResponse)
async def list_capsules(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    username = current_user["username"]
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    total_capsules = db.query(Capsule).filter(Capsule.user_id == user.id).count()
    total_pages = (total_capsules + limit - 1) // limit
    
    capsules = db.query(Capsule).filter(Capsule.user_id == user.id)\
        .order_by(Capsule.created_at.desc())\
        .offset((page - 1) * limit)\
        .limit(limit)\
        .all()
    
    current_time = datetime.now(IST)
    
    capsule_list = []
    for capsule in capsules:
        # Make sure unlock_at is timezone-aware
        unlock_at = ensure_timezone_aware(capsule.unlock_at)
        
        # Update is_unlockable logic to consider expiration
        is_unlockable = (current_time >= unlock_at and 
                        current_time <= unlock_at + timedelta(days=30) and
                        not capsule.expired)
        
        # Check if it should be marked as expired now
        if not capsule.expired and current_time > unlock_at + timedelta(days=30):
            capsule.expired = True
            db.commit()
        
        capsule_list.append({
            "id": capsule.id,
            "unlock_code": capsule.unlock_code,
            "unlock_at": capsule.unlock_at,
            "created_at": capsule.created_at,
            "is_unlockable": is_unlockable,
            "expired": capsule.expired
        })
    
    return {
        "capsules": capsule_list,
        "total": total_capsules,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

@app.put("/capsules/{capsule_id}", response_model=CapsuleUpdateRespone)
async def update_capsule(
    capsule_id: int,
    capsule_update: CapsuleUpdate,
    code: str = Query(..., description="Unlock code for the capsule"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    username = current_user["username"]
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    capsule = db.query(Capsule).filter(
        Capsule.id == capsule_id
    ).first()
    
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")
    
    if capsule.user_id != user.id:
        raise HTTPException(status_code=403, detail="403 forbidden")
    
    if capsule.unlock_code != code:
        raise HTTPException(status_code=401, detail="401 unauthorized")
    
    current_time = datetime.now(IST)
    
    # Ensure capsule.unlock_at is timezone-aware
    unlock_at = ensure_timezone_aware(capsule.unlock_at)
    
    if current_time >= unlock_at:
        raise HTTPException(
            status_code=403, 
            detail="403 forbidden(Unlock time already passed)"
        )
    
    if capsule_update.message is not None:
        capsule.message = capsule_update.message
        
    if capsule_update.unlock_at is not None:
        new_unlock_at = ensure_timezone_aware(capsule_update.unlock_at)
            
        if new_unlock_at <= current_time:
            raise HTTPException(
                status_code=400,
                detail="Unlock time must be in the future"
            )
            
        capsule.unlock_at = new_unlock_at
    
    db.commit()
    db.refresh(capsule)
    
    return {
        "message": capsule.message,
        "unlock_at": capsule.unlock_at
    }


@app.get("/capsules/{capsule_id}", response_model=CapsuleFullResponse)
async def get_capsule(
    capsule_id: int,
    code: str = Query(..., description="Unlock code for the capsule"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    capsule = db.query(Capsule).filter(Capsule.id == capsule_id).first()

    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    if capsule.unlock_code != code:
        raise HTTPException(status_code=401, detail="401 unauthorized")

    current_time = datetime.now(IST)
    
    # Ensure capsule.unlock_at is timezone-aware
    unlock_at = ensure_timezone_aware(capsule.unlock_at)

    if current_time < unlock_at:
        raise HTTPException(
            status_code=403,
            detail="403 forbidden"
        )

    # Check if expired (either by flag or by calculation)
    if capsule.expired or current_time > unlock_at + timedelta(days=30):
        # If not marked as expired but should be, mark it now
        if not capsule.expired and current_time > unlock_at + timedelta(days=30):
            capsule.expired = True
            db.commit()
            
        raise HTTPException(
            status_code=410,
            detail="410 GONE"
        )

    return capsule

@app.delete('/capsules/{capsule_id}')
async def delete_capsule(
    capsule_id: int,
    code: str = Query(..., description="Unlock code for Capsule"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    username = current_user["username"]
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    capsule = db.query(Capsule).filter(Capsule.id == capsule_id).first()

    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")
    
    if capsule.user_id != user.id:
        raise HTTPException(status_code=403, detail="403 forbidden")
    
    if capsule.unlock_code != code:
        raise HTTPException(status_code=401, detail="401 unauthorized")
    
    current_time = datetime.now(IST)
    
    # Ensure capsule.unlock_at is timezone-aware
    unlock_at = ensure_timezone_aware(capsule.unlock_at)
    
    if current_time >= unlock_at:
        raise HTTPException(
            status_code=403, 
            detail="403 forbidden (Cannot delete capsule after unlock time)"
        )
    
    db.delete(capsule)
    db.commit()
    
    return {"detail": "Capsule deleted successfully"}

# Start the background task when the app starts
@app.on_event("startup")
async def startup_event():
    """
    Register the hourly expiration check task when the application starts.
    This ensures we regularly mark expired capsules without checking on every request.
    """
    asyncio.create_task(check_expirations())
