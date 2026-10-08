"""Scoped assistance outputs; private access is checked by the existing services."""

from typing import Any

from pydantic import BaseModel

from app.contracts.http import Meta


class KnowledgeResponse(BaseModel):
    data: dict[str, Any]
    meta: Meta
