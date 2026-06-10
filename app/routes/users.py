from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models, schemas, auth
from app.dependencies import get_current_user, admin_only, get_db

router = APIRouter(prefix="/users", tags=["👤 User Management"])


@router.post("/signup", response_model=schemas.UserResponse)
def signup(user: schemas.UserCreate,
           db: Session = Depends(get_db)):

    existing = db.query(models.Account)\
        .filter(models.Account.email == user.email)\
        .first()

    if existing:
        raise HTTPException(400, "Email exists")

    new_user = models.Account(
        name=user.name,
        email=user.email,
        password_hash=auth.hash_password(user.password),
        role=user.role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.get("/profile", response_model=schemas.UserResponse)
def profile(current_user=Depends(get_current_user)):
    return current_user


@router.get("/", response_model=list[schemas.UserResponse])
def get_users(admin=Depends(admin_only),
              db: Session = Depends(get_db)):
    return db.query(models.Account).all()


@router.put("/{account_id}", response_model=schemas.UserResponse)
def update_user(
    account_id: int,
    user_update: schemas.UserUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    user = db.query(models.Account)\
        .filter(models.Account.account_id == account_id)\
        .first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ Permission Check (Admin or Self)
    if (
        current_user.role != "admin"
        and current_user.account_id != account_id
    ):
        raise HTTPException(status_code=403, detail="Not allowed")

    # ✅ Only update provided fields
    update_data = user_update.dict(exclude_unset=True)

    for key, value in update_data.items():

        # Password handling
        if key == "password":
            user.password_hash = auth.hash_password(value)

        # Role change allowed only for admin
        elif key == "role":
            if current_user.role != "admin":
                raise HTTPException(
                    status_code=403,
                    detail="Only admin can change role"
                )
            user.role = value

        else:
            setattr(user, key, value)

    db.commit()
    db.refresh(user)

    return user

@router.delete("/{user_id}")
def delete_user(user_id: int,
                admin=Depends(admin_only),
                db: Session = Depends(get_db)):

    user = db.query(models.Account)\
        .filter(models.Account.account_id == user_id)\
        .first()

    if not user:
        raise HTTPException(404, "User not found")

    db.delete(user)
    db.commit()

    return {"message": "Deleted"}
