"""
Integration API endpoints for managing per-tenant Twilio and Email SMTP credentials.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorDatabase

from bson import ObjectId
from app.database import get_database
from app.api.deps import get_current_active_user
from app.utils.encryption import encrypt, decrypt, mask_value

router = APIRouter()


# ── Pydantic Models ──────────────────────────────

class TwilioConfigRequest(BaseModel):
    account_sid: str
    auth_token: str
    phone_number: str


class EmailConfigRequest(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    from_email: str
    from_name: str = "CallCenter SaaS"


class TwilioConfigResponse(BaseModel):
    account_sid: Optional[str] = None
    auth_token: Optional[str] = None
    phone_number: Optional[str] = None
    is_configured: bool = False


class EmailConfigResponse(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    is_configured: bool = False


class ApiKeyConfigRequest(BaseModel):
    api_key: str


class ApiKeyConfigResponse(BaseModel):
    api_key: Optional[str] = None
    is_configured: bool = False


class IntegrationConfigResponse(BaseModel):
    twilio: TwilioConfigResponse
    email: EmailConfigResponse
    groq: ApiKeyConfigResponse = ApiKeyConfigResponse()
    deepgram: ApiKeyConfigResponse = ApiKeyConfigResponse()
    openai: ApiKeyConfigResponse = ApiKeyConfigResponse()
    elevenlabs: ApiKeyConfigResponse = ApiKeyConfigResponse()


# ── GET /integration ─────────────────────────────

@router.get("/", response_model=IntegrationConfigResponse)
async def get_integration_config(
    current_user: dict = Depends(get_current_active_user)
):
    """Get current user's integration configuration (sensitive fields masked)."""
    config = current_user.get("integration_config", {})
    twilio = config.get("twilio", {})
    email = config.get("email", {})

    groq = config.get("groq", {})
    deepgram = config.get("deepgram", {})
    openai_cfg = config.get("openai", {})
    elevenlabs = config.get("elevenlabs", {})

    return IntegrationConfigResponse(
        twilio=TwilioConfigResponse(
            account_sid=mask_value(twilio["account_sid"]) if twilio.get("account_sid") else None,
            auth_token="****" if twilio.get("auth_token") else None,
            phone_number=twilio.get("phone_number"),
            is_configured=bool(twilio.get("account_sid") and twilio.get("auth_token"))
        ),
        email=EmailConfigResponse(
            smtp_host=email.get("smtp_host"),
            smtp_port=email.get("smtp_port"),
            smtp_username=mask_value(email["smtp_username"]) if email.get("smtp_username") else None,
            smtp_password="****" if email.get("smtp_password") else None,
            from_email=email.get("from_email"),
            from_name=email.get("from_name"),
            is_configured=bool(email.get("smtp_host") and email.get("smtp_password"))
        ),
        groq=ApiKeyConfigResponse(
            api_key=mask_value(groq["api_key"]) if groq.get("api_key") else None,
            is_configured=bool(groq.get("api_key"))
        ),
        deepgram=ApiKeyConfigResponse(
            api_key=mask_value(deepgram["api_key"]) if deepgram.get("api_key") else None,
            is_configured=bool(deepgram.get("api_key"))
        ),
        openai=ApiKeyConfigResponse(
            api_key=mask_value(openai_cfg["api_key"]) if openai_cfg.get("api_key") else None,
            is_configured=bool(openai_cfg.get("api_key"))
        ),
        elevenlabs=ApiKeyConfigResponse(
            api_key=mask_value(elevenlabs["api_key"]) if elevenlabs.get("api_key") else None,
            is_configured=bool(elevenlabs.get("api_key"))
        )
    )


# ── PUT /integration/twilio ──────────────────────

@router.put("/twilio")
async def save_twilio_config(
    config: TwilioConfigRequest,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Save Twilio integration credentials (auth_token is encrypted)."""
    encrypted_token = encrypt(config.auth_token)

    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {
            "integration_config.twilio": {
                "account_sid": config.account_sid,
                "auth_token": encrypted_token,
                "phone_number": config.phone_number
            },
            "updated_at": datetime.utcnow()
        }}
    )

    return {"message": "Twilio configuration saved successfully"}


# ── PUT /integration/email ───────────────────────

@router.put("/email")
async def save_email_config(
    config: EmailConfigRequest,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Save Email SMTP integration credentials (smtp_password is encrypted)."""
    encrypted_password = encrypt(config.smtp_password)

    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {
            "integration_config.email": {
                "smtp_host": config.smtp_host,
                "smtp_port": config.smtp_port,
                "smtp_username": config.smtp_username,
                "smtp_password": encrypted_password,
                "from_email": config.from_email,
                "from_name": config.from_name
            },
            "updated_at": datetime.utcnow()
        }}
    )

    return {"message": "Email configuration saved successfully"}


# ── POST /integration/twilio/test ────────────────

@router.post("/twilio/test")
async def test_twilio_config(
    current_user: dict = Depends(get_current_active_user)
):
    """Test Twilio connection using saved credentials."""
    config = current_user.get("integration_config", {}).get("twilio", {})
    if not config.get("account_sid") or not config.get("auth_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Twilio configuration found. Please save your credentials first."
        )

    try:
        from twilio.rest import Client
        sid = config["account_sid"]
        token = decrypt(config["auth_token"])
        client = Client(sid, token)
        account = client.api.accounts(sid).fetch()
        return {
            "success": True,
            "message": f"Connected successfully to account: {account.friendly_name}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {str(e)}"
        }


# ── POST /integration/email/test ─────────────────

@router.post("/email/test")
async def test_email_config(
    current_user: dict = Depends(get_current_active_user)
):
    """Test Email SMTP connection using saved credentials."""
    config = current_user.get("integration_config", {}).get("email", {})
    if not config.get("smtp_host") or not config.get("smtp_password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email configuration found. Please save your credentials first."
        )

    try:
        import aiosmtplib
        smtp = aiosmtplib.SMTP(
            hostname=config["smtp_host"],
            port=config.get("smtp_port", 587),
            start_tls=True
        )
        await smtp.connect()
        await smtp.login(config["smtp_username"], decrypt(config["smtp_password"]))
        await smtp.quit()
        return {
            "success": True,
            "message": "SMTP connection successful"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"SMTP connection failed: {str(e)}"
        }


# ── DELETE /integration/twilio ───────────────────

@router.delete("/twilio")
async def delete_twilio_config(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Remove Twilio integration (reverts to default .env credentials)."""
    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {
            "$unset": {"integration_config.twilio": ""},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return {"message": "Twilio configuration removed. System will use default credentials."}


# ── DELETE /integration/email ────────────────────

@router.delete("/email")
async def delete_email_config(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Remove Email SMTP integration (reverts to default .env credentials)."""
    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {
            "$unset": {"integration_config.email": ""},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return {"message": "Email configuration removed. System will use default credentials."}


# ── API Key Integrations (Groq, Deepgram, OpenAI, ElevenLabs) ────

API_KEY_SERVICES = ["groq", "deepgram", "openai", "elevenlabs"]


@router.put("/{service}")
async def save_api_key_config(
    service: str,
    config: ApiKeyConfigRequest,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Save API key for a service (encrypted)."""
    if service not in API_KEY_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service}")

    encrypted_key = encrypt(config.api_key)

    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {
            f"integration_config.{service}": {"api_key": encrypted_key},
            "updated_at": datetime.utcnow()
        }}
    )

    return {"message": f"{service.capitalize()} API key saved successfully"}


@router.post("/{service}/test")
async def test_api_key_config(
    service: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Test an API key by making a lightweight request to the service."""
    if service not in API_KEY_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service}")

    cfg = current_user.get("integration_config", {}).get(service, {})
    if not cfg.get("api_key"):
        raise HTTPException(status_code=400, detail=f"No {service} API key configured.")

    api_key = decrypt(cfg["api_key"])

    try:
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=10)

        if service == "groq":
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                ) as resp:
                    if resp.status == 200:
                        return {"success": True, "message": "Groq API key is valid"}
                    return {"success": False, "message": f"Groq API returned status {resp.status}"}

        elif service == "deepgram":
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://api.deepgram.com/v1/projects",
                    headers={"Authorization": f"Token {api_key}"}
                ) as resp:
                    if resp.status == 200:
                        return {"success": True, "message": "Deepgram API key is valid"}
                    return {"success": False, "message": f"Deepgram API returned status {resp.status}"}

        elif service == "openai":
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                ) as resp:
                    if resp.status == 200:
                        return {"success": True, "message": "OpenAI API key is valid"}
                    return {"success": False, "message": f"OpenAI API returned status {resp.status}"}

        elif service == "elevenlabs":
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://api.elevenlabs.io/v1/user",
                    headers={"xi-api-key": api_key}
                ) as resp:
                    if resp.status == 200:
                        return {"success": True, "message": "ElevenLabs API key is valid"}
                    return {"success": False, "message": f"ElevenLabs API returned status {resp.status}"}

    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}


@router.delete("/{service}")
async def delete_api_key_config(
    service: str,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Remove API key integration (reverts to system default from .env)."""
    if service not in API_KEY_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service}")

    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {
            "$unset": {f"integration_config.{service}": ""},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return {"message": f"{service.capitalize()} API key removed. System will use default credentials."}
