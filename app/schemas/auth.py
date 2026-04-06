
# # backend/app/schemas/auth.py orginal file 
# from pydantic import BaseModel, EmailStr
# from typing import Optional

# class Token(BaseModel):
#     access_token: str
#     token_type: str
#     expires_in: int
#     user: dict

# class TokenData(BaseModel):
#     email: Optional[str] = None

# class UserLogin(BaseModel):
#     email: EmailStr
#     password: str

# class PasswordReset(BaseModel):
#     email: EmailStr

# class PasswordResetConfirm(BaseModel):
#     token: str
#     new_password: str

# class EmailVerification(BaseModel):
#     token: str


# backend/app/schemas/auth.py orginal file 
from pydantic import BaseModel, EmailStr
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: dict

class TokenData(BaseModel):
    email: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class PasswordReset(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class EmailVerification(BaseModel):
    token: str