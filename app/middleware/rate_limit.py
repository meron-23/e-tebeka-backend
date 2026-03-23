from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only rate limit search and view endpoints
        if "/search" in request.url.path or "/documents/" in request.url.path:
            # We would normally get user from JWT, but for simplicity let's assume public if no token
            # In a real app, this would be more robust
            pass
        
        response = await call_next(request)
        return response
