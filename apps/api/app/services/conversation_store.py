from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.utils.query import is_followup_question


@dataclass
class ConversationTurn:
    question: str


@dataclass
class Conversation:
    conversation_id: str
    turns: list[ConversationTurn] = field(default_factory=list)


class ConversationStore:
    """In-memory continuity only. Assistant answers are never stored as evidence."""

    def __init__(self, max_turns: int = 6) -> None:
        self.max_turns = max_turns
        self._conversations: dict[str, Conversation] = {}

    def ensure(self, conversation_id: str | None) -> Conversation:
        if conversation_id and conversation_id in self._conversations:
            return self._conversations[conversation_id]
        created = Conversation(conversation_id=conversation_id or str(uuid4()))
        self._conversations[created.conversation_id] = created
        return created

    def append_user_question(self, conversation_id: str, question: str) -> Conversation:
        conversation = self.ensure(conversation_id)
        conversation.turns.append(ConversationTurn(question=question))
        conversation.turns = conversation.turns[-self.max_turns :]
        return conversation

    def retrieval_query(self, conversation: Conversation, current_question: str) -> str:
        prior = [turn.question for turn in conversation.turns if turn.question != current_question]
        if not prior:
            return current_question
        if not is_followup_question(current_question, prior):
            return current_question
        recent = " | ".join(prior[-3:])
        return f"{recent} {current_question}"
