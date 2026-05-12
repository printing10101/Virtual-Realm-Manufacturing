"""
CORS Configuration Module

Provides environment-aware CORS configuration for the LNN AI service.
- Development: Allows localhost origins for development convenience
- Production: Strict Tauri-only origins
- Supports reading allowed origins from environment variable
"""
from __future__ import annotations
import os
from typing import Optional, List


PRODUCTION_ORIGINS = [
    "tauri://localhost",
    "http://localhost:*",
    "https://tauri.localhost",
]

DEVELOPMENT_PATTERNS = [
    "http://localhost",
    "https://localhost",
    "tauri://localhost",
]

DEVELOPMENT_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8765",
    "https://localhost:3000",
    "https://localhost:5173",
    "tauri://localhost",
]


class CorsSettings:
    def __init__(self):
        self._env = os.environ.get("LINGJING_ENV", "production").lower()
        if self._env not in ("development", "production"):
            self._env = "production"
        
        env_override = os.environ.get("ALLOWED_ORIGINS", "")
        if env_override:
            self._origins = [o.strip() for o in env_override.split(",") if o.strip()]
        elif self._env == "development":
            self._origins = DEVELOPMENT_ORIGINS
        else:
            self._origins = list(PRODUCTION_ORIGINS)
        
        self.allow_credentials = True
        self.allow_origin_regex = None
        self.max_age = 3600 if self._env == "development" else 600
    
    def get_origins(self) -> List[str]:
        return self._origins
    
    def get_methods(self) -> List[str]:
        return ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    
    def get_headers(self) -> List[str]:
        return ["*"]
    
    def get_expose_headers(self) -> List[str]:
        return ["X-Content-Type-Options", "X-Frame-Options", "X-XSS-Protection"]
    
    def is_allowed_origin(self, origin: str) -> bool:
        if not origin:
            return False
        
        env_override = os.environ.get("ALLOWED_ORIGINS", "")
        if env_override:
            allowed = [o.strip() for o in env_override.split(",") if o.strip()]
            return origin in allowed
        
        if self._env == "development":
            for pattern in DEVELOPMENT_PATTERNS:
                if origin.startswith(pattern):
                    return True
            return False
        
        return origin in PRODUCTION_ORIGINS


cors_settings = CorsSettings()


def get_environment() -> str:
    env = os.environ.get("LINGJING_ENV", "production").lower()
    return env if env in ("development", "production") else "production"


def is_allowed_origin(origin: str, override_env: Optional[str] = None) -> bool:
    if override_env:
        env = override_env
    else:
        env = get_environment()
    
    env_override = os.environ.get("ALLOWED_ORIGINS", "")
    if env_override:
        allowed = [o.strip() for o in env_override.split(",") if o.strip()]
        return origin in allowed
    
    if env == "development":
        for pattern in DEVELOPMENT_PATTERNS:
            if origin.startswith(pattern):
                return True
        return False
    
    return origin in PRODUCTION_ORIGINS


def get_cors_origins(override_env: Optional[str] = None) -> list[str]:
    env_override = os.environ.get("ALLOWED_ORIGINS", "")
    if env_override:
        return [origin.strip() for origin in env_override.split(",") if origin.strip()]

    env = override_env or get_environment()

    if env == "development":
        return list(DEVELOPMENT_ORIGINS)

    return list(PRODUCTION_ORIGINS)


def get_cors_config(override_env: Optional[str] = None) -> dict:
    origins = get_cors_origins(override_env)
    env = override_env or get_environment()

    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Content-Type-Options", "X-Frame-Options", "X-XSS-Protection"],
        "max_age": 600 if env == "production" else 3600,
    }


def get_security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
    }


def is_development() -> bool:
    return get_environment() == "development"


def is_production() -> bool:
    return get_environment() == "production"
