from __future__ import annotations

from dotenv import load_dotenv
from langfuse import get_client
from langfuse.langchain import CallbackHandler

load_dotenv()


def get_langfuse_client():
    """
    Return the shared Langfuse client.
    """
    return get_client()


def get_langfuse_handler() -> CallbackHandler:
    """
    Create a Langfuse callback handler for one request.
    """
    return CallbackHandler()
