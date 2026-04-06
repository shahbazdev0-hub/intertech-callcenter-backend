# models/base.py
from bson import ObjectId as BsonObjectId
from pydantic_core import core_schema


class PyObjectId(BsonObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, BsonObjectId):
            return v
        if not BsonObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return BsonObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string", "example": "507f1f77bcf86cd799439011"}