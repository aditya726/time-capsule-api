from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, Session
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pydantic import BaseModel
import secrets
import string
from auth import route as auth_router, Base, engine, get_db, User, get_current_user

app = FastAPI(title="Time-Capsule")

app.include_router(auth_router)

# Capsule model (naive datetime)
class Capsule(Base):
    __tablename__ = "capsules"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    unlock_at = Column(DateTime, nullable=False)  
    created_at = Column(DateTime, default=datetime.now)  
    unlock_code = Column(String(12), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("user.id"))

    user = relationship("User", back_populates="capsules")

User.capsules = relationship("Capsule", back_populates="user")

Base.metadata.create_all(bind=engine)

# Pydantic models
class CapsuleCreate(BaseModel):
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

# Generate unlock code
def generate_unlock_code(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Create capsule endpoint
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

    unlock_at = capsule.unlock_at
    if unlock_at.tzinfo is not None:
        unlock_at = unlock_at.replace(tzinfo=None)

    unlock_code = generate_unlock_code()

    new_capsule = Capsule(
        message=capsule.message,
        unlock_at=unlock_at,
        unlock_code=unlock_code,
        user_id=user.id
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
    
    # Calculate total pages
    total_pages = (total_capsules + limit - 1) // limit
    
    # Get paginated capsules
    capsules = db.query(Capsule).filter(Capsule.user_id == user.id)\
        .order_by(Capsule.created_at.desc())\
        .offset((page - 1) * limit)\
        .limit(limit)\
        .all()
    
    current_time = datetime.now() 
    
    
    capsule_list = []
    for capsule in capsules:
        is_unlockable = current_time >= capsule.unlock_at and current_time <= capsule.unlock_at + timedelta(days=30)
        
        capsule_list.append({
            "id": capsule.id,
            "unlock_code": capsule.unlock_code,
            "unlock_at": capsule.unlock_at,
            "created_at": capsule.created_at,
            "is_unlockable": is_unlockable
        })
    
    return {
        "capsules": capsule_list,
        "total": total_capsules,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
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

    current_time = datetime.now()

    if current_time < capsule.unlock_at:
        raise HTTPException(
            status_code=403,
            detail="403 forbidden"
        )

    if current_time > capsule.unlock_at + timedelta(days=30):
        raise HTTPException(
            status_code=410,
            detail="410 GONE"
        )

    return capsule