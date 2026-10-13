"""Pytest bootstrap: dummy env so importing the app never fails.

Real secrets are never stored here; these are obviously-fake placeholders
for the test process only (R-08/R-12).
"""

import os

_FAKE_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "JWT_SECRET": "test-only-not-a-real-secret-0123456789abcdef",
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_MINUTES": "30",
    "WHATSAPP_API_TOKEN": "test-token",
    "WHATSAPP_PHONE_ID": "test-phone-id",
    "MP_ACCESS_TOKEN": "TEST-test-token",
    "ARCA_CUIT": "20000000001",
    "ARCA_CERT": "test-cert",
    "ARCA_KEY": "test-key",
    "APP_BASE_URL": "http://127.0.0.1:8080",
}

for _key, _value in _FAKE_ENV.items():
    os.environ.setdefault(_key, _value)
