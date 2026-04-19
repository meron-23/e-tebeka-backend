import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Build allowed origins list from hardcoded defaults + optional env var
_base_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "https://e-tebeka-frontendd.vercel.app",
    "https://e-tebeka-backend-5.onrender.com",
]

# ALLOWED_ORIGINS env var lets you add extra origins (comma-separated) at deploy time
_extra = os.getenv("ALLOWED_ORIGINS", "")
_extra_origins = [o.strip() for o in _extra.split(",") if o.strip()]
allowed_origins = list(set(_base_origins + _extra_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to E-Tebeka API"}

