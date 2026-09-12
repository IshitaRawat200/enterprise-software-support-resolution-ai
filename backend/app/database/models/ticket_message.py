from app.database.models.conversation import ConversationHistory

# Backward-compatible alias while message storage is consolidated
# in conversation_history.
TicketMessage = ConversationHistory

__all__ = ["TicketMessage"]
