"""
SQLAlchemy model registration.

Import every ORM model here so SQLAlchemy knows about all mapped
classes before SQLAlchemy configures relationships.

Keep app/database/models/__init__.py empty.
"""

from app.database.models.audit import AuditEvent
from app.database.models.conversation import ConversationHistory
from app.database.models.customer import Customer
from app.database.models.escalation import Escalation
from app.database.models.evaluation_run import EvaluationRun
from app.database.models.knowledge import KnowledgeArticleUsage
from app.database.models.ticket import SupportTicket
from app.database.models.ticket_message import TicketMessage
from app.database.models.user import User

__all__ = [
    "AuditEvent",
    "ConversationHistory",
    "Customer",
    "Escalation",
    "EvaluationRun",
    "KnowledgeArticleUsage",
    "SupportTicket",
    "TicketMessage",
    "User",
]
