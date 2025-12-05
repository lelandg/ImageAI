"""
Conversation Manager for Multi-Turn Image Generation and Editing.

Manages chat sessions for iterative image refinement with Gemini 3 Pro Image (Nano Banana Pro).
Uses the Google GenAI SDK's chat feature which handles thought signatures automatically.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ImageConversation:
    """
    Represents a single image generation/editing conversation.

    Stores the chat session and metadata for a specific image's generation history.
    """

    def __init__(self, conversation_id: str, initial_prompt: str, model: str):
        """
        Initialize an image conversation.

        Args:
            conversation_id: Unique identifier for this conversation
            initial_prompt: The original prompt that created the image
            model: The model ID used for generation
        """
        self.conversation_id = conversation_id
        self.initial_prompt = initial_prompt
        self.model = model
        self.created_at = datetime.now()
        self.last_updated = datetime.now()

        # Chat session from the SDK - handles thought signatures automatically
        self._chat_session = None

        # History of messages and results
        self.messages: List[Dict[str, Any]] = []

        # Most recent image bytes (for display in refine dialog)
        self.current_image_bytes: Optional[bytes] = None
        self.current_image_path: Optional[Path] = None

    def set_chat_session(self, chat_session):
        """
        Set the chat session from the SDK.

        Args:
            chat_session: The chat session object from client.chats.create()
        """
        self._chat_session = chat_session
        logger.info(f"Chat session set for conversation {self.conversation_id}")

    def get_chat_session(self):
        """Get the current chat session."""
        return self._chat_session

    def add_message(self, role: str, content: str, image_bytes: Optional[bytes] = None,
                    image_path: Optional[Path] = None):
        """
        Add a message to the conversation history.

        Args:
            role: 'user' or 'model'
            content: Text content of the message
            image_bytes: Optional image data
            image_path: Optional path to saved image
        """
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'has_image': image_bytes is not None
        }
        self.messages.append(message)

        if role == 'model' and image_bytes:
            self.current_image_bytes = image_bytes
            self.current_image_path = image_path

        self.last_updated = datetime.now()

    def has_chat_session(self) -> bool:
        """Check if this conversation has an active chat session."""
        return self._chat_session is not None

    def get_message_count(self) -> int:
        """Get the number of messages in this conversation."""
        return len(self.messages)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize conversation metadata to dictionary.

        Note: Chat session cannot be serialized, only metadata is stored.
        """
        return {
            'conversation_id': self.conversation_id,
            'initial_prompt': self.initial_prompt,
            'model': self.model,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'message_count': len(self.messages),
            'current_image_path': str(self.current_image_path) if self.current_image_path else None
        }


class ConversationManager:
    """
    Manages multiple image conversations for multi-turn editing.

    Provides storage and retrieval of chat sessions for iterative refinement.
    """

    # Maximum number of conversations to keep in memory
    MAX_CONVERSATIONS = 20

    def __init__(self):
        """Initialize the conversation manager."""
        self._conversations: Dict[str, ImageConversation] = {}
        self._conversation_order: List[str] = []  # LRU tracking

    def create_conversation(self, initial_prompt: str, model: str,
                            image_bytes: Optional[bytes] = None,
                            image_path: Optional[Path] = None) -> ImageConversation:
        """
        Create a new image conversation.

        Args:
            initial_prompt: The prompt used for initial generation
            model: The model ID used
            image_bytes: Optional generated image bytes
            image_path: Optional path to saved image

        Returns:
            New ImageConversation instance
        """
        # Generate unique ID
        conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        conversation = ImageConversation(
            conversation_id=conversation_id,
            initial_prompt=initial_prompt,
            model=model
        )

        # Add initial message
        conversation.add_message('user', initial_prompt)

        if image_bytes:
            conversation.add_message('model', 'Generated image', image_bytes, image_path)

        # Store conversation
        self._conversations[conversation_id] = conversation
        self._conversation_order.append(conversation_id)

        # Evict old conversations if needed
        self._evict_old_conversations()

        logger.info(f"Created conversation {conversation_id} for model {model}")
        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[ImageConversation]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The conversation ID

        Returns:
            ImageConversation or None if not found
        """
        if conversation_id in self._conversations:
            # Update LRU order
            if conversation_id in self._conversation_order:
                self._conversation_order.remove(conversation_id)
            self._conversation_order.append(conversation_id)
            return self._conversations[conversation_id]
        return None

    def get_conversation_by_image_path(self, image_path: Path) -> Optional[ImageConversation]:
        """
        Find a conversation by its current image path.

        Args:
            image_path: Path to the image file

        Returns:
            ImageConversation or None if not found
        """
        image_path_str = str(image_path)
        for conversation in self._conversations.values():
            if conversation.current_image_path and str(conversation.current_image_path) == image_path_str:
                return conversation
        return None

    def get_recent_conversations(self, limit: int = 5) -> List[ImageConversation]:
        """
        Get the most recent conversations.

        Args:
            limit: Maximum number to return

        Returns:
            List of recent conversations
        """
        recent_ids = self._conversation_order[-limit:][::-1]  # Most recent first
        return [self._conversations[cid] for cid in recent_ids if cid in self._conversations]

    def remove_conversation(self, conversation_id: str):
        """
        Remove a conversation.

        Args:
            conversation_id: The conversation ID to remove
        """
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            if conversation_id in self._conversation_order:
                self._conversation_order.remove(conversation_id)
            logger.info(f"Removed conversation {conversation_id}")

    def _evict_old_conversations(self):
        """Evict oldest conversations when limit is exceeded."""
        while len(self._conversations) > self.MAX_CONVERSATIONS:
            if self._conversation_order:
                oldest_id = self._conversation_order.pop(0)
                if oldest_id in self._conversations:
                    # Don't evict if it has an active chat session
                    conv = self._conversations[oldest_id]
                    if conv.has_chat_session():
                        # Put it back and try next
                        self._conversation_order.insert(0, oldest_id)
                        continue
                    del self._conversations[oldest_id]
                    logger.debug(f"Evicted old conversation {oldest_id}")

    def clear_all(self):
        """Clear all conversations."""
        self._conversations.clear()
        self._conversation_order.clear()
        logger.info("Cleared all conversations")


# Global conversation manager instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
