from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class DataResponse(BaseModel):
    data: Any


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
