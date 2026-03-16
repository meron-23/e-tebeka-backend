from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_users_profile():
    return {"message": "User profile placeholder"}
