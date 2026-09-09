from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Customer support chat request.
    """

    message: str = Field(
        min_length=1,
        max_length=10000,
    )

    conversation_id: str | None = None

    customer_id: str | None = None
