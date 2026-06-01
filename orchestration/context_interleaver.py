"""
Context Interleaver - Non-linear conversation handler.
Manages conversation flow when users interrupt qualification with support questions,
maintaining a conversation stack so no qualification state is lost.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import structlog

from config import settings

logger = structlog.get_logger(__name__)


class FlowType(str, Enum):
    QUALIFICATION = "qualification"
    SUPPORT = "support"
    DISCOVERY = "discovery"
    SCHEDULING = "scheduling"
    GENERAL = "general"


class IntentCategory(str, Enum):
    QUALIFICATION_ANSWER = "qualification_answer"
    SUPPORT_QUESTION = "support_question"
    TOPIC_CHANGE = "topic_change"
    RETURN_TO_FLOW = "return_to_flow"
    PROPERTY_INQUIRY = "property_inquiry"
    SCHEDULING_REQUEST = "scheduling_request"
    GENERAL_CHAT = "general_chat"


@dataclass
class FlowFrame:
    """A single frame on the conversation stack."""
    flow_type: FlowType
    context: dict[str, Any]
    step: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponseStrategy:
    """Output of the interleaver: how to respond to the user."""
    response_text: str
    return_to_previous: bool = False
    update_flow: Optional[FlowType] = None
    new_step: str = ""
    stack_depth: int = 0


# Per-lead conversation stacks
_conversation_stacks: dict[str, list[FlowFrame]] = {}

# Transition phrases keyed by topic
_TRANSITIONS = {
    "property": "Going back to the properties we were discussing,",
    "budget": "Picking up where we left off with your budget,",
    "timeline": "Returning to our conversation about your timeline,",
    "location": "Speaking of location, getting back to our earlier discussion,",
    "general": "Going back to what we were discussing,",
    "qualification": "Picking up our conversation,",
}


def _get_stack(lead_id: str) -> list[FlowFrame]:
    if lead_id not in _conversation_stacks:
        _conversation_stacks[lead_id] = []
    return _conversation_stacks[lead_id]


def _detect_interrupt_topic(message: str, intent: IntentCategory) -> str:
    """Map the interruption to a topic key for smooth transition phrasing."""
    lower = message.lower()
    if any(w in lower for w in ["property", "house", "home", "listing"]):
        return "property"
    if any(w in lower for w in ["price", "cost", "afford", "budget"]):
        return "budget"
    if any(w in lower for w in ["when", "timeline", "move in", "closing"]):
        return "timeline"
    if any(w in lower for w in ["area", "neighborhood", "school", "location"]):
        return "location"
    return "general"


async def handle_interruption(
    lead_id: str,
    current_flow: FlowFrame,
    user_message: str,
    extracted_intent: IntentCategory,
) -> ResponseStrategy:
    """
    Handle a non-linear conversation interruption.

    If the user asks something mid-qualification, answer the question,
    push the current flow onto the stack, and provide a smooth transition
    back when returning.
    """
    stack = _get_stack(lead_id)

    # If intent is still qualification-related, no interruption
    if extracted_intent == IntentCategory.QUALIFICATION_ANSWER:
        return ResponseStrategy(
            response_text="",  # Let qualification handler respond normally
            return_to_previous=False,
            update_flow=current_flow.flow_type,
            new_step=current_flow.step,
            stack_depth=len(stack),
        )

    # If user is explicitly returning to a previous flow
    if extracted_intent == IntentCategory.RETURN_TO_FLOW and stack:
        return await _handle_return(lead_id, stack)

    # Push current flow onto stack
    stack.append(current_flow)
    logger.info(
        "flow_pushed",
        lead_id=lead_id,
        pushed_flow=current_flow.flow_type.value,
        stack_depth=len(stack),
    )

    # Generate response to the interruption
    topic = _detect_interrupt_topic(user_message, extracted_intent)
    response_text = await _generate_interruption_response(
        lead_id=lead_id,
        message=user_message,
        intent=extracted_intent,
        topic=topic,
    )

    return ResponseStrategy(
        response_text=response_text,
        return_to_previous=False,
        update_flow=_intent_to_flow(extracted_intent),
        new_step="interruption_handled",
        stack_depth=len(stack),
    )


async def _handle_return(lead_id: str, stack: list[FlowFrame]) -> ResponseStrategy:
    """Pop the stack and generate a smooth return transition."""
    if not stack:
        return ResponseStrategy(
            response_text="Is there anything else I can help you with?",
            stack_depth=0,
        )

    previous_frame = stack.pop()
    topic = previous_frame.metadata.get("topic", "general")
    transition = _TRANSITIONS.get(topic, _TRANSITIONS["general"])

    logger.info(
        "flow_popped",
        lead_id=lead_id,
        restored_flow=previous_frame.flow_type.value,
        stack_depth=len(stack),
    )

    response_text = f"{transition} "
    response_text += await _generate_resume_text(previous_frame)

    return ResponseStrategy(
        response_text=response_text,
        return_to_previous=True,
        update_flow=previous_frame.flow_type,
        new_step=previous_frame.step,
        stack_depth=len(stack),
    )


async def _generate_interruption_response(
    lead_id: str,
    message: str,
    intent: IntentCategory,
    topic: str,
) -> str:
    """Generate an answer to the user's interruption question."""
    if intent == IntentCategory.SUPPORT_QUESTION:
        return (
            f"Great question! Let me help with that. {message} — "
            "I'll look into this for you. In the meantime, I had a few more quick questions "
            "to help find the perfect property for you."
        )
    if intent == IntentCategory.PROPERTY_INQUIRY:
        return (
            "That's a great property question! Let me pull up some details for you. "
            "After this, I'd love to continue learning about what you're looking for."
        )
    if intent == IntentCategory.SCHEDULING_REQUEST:
        return (
            "Absolutely, I'd be happy to help schedule that! "
            "Let me check availability. I'll have a few more questions afterward to make sure "
            "we find the right fit for you."
        )
    if intent == IntentCategory.TOPIC_CHANGE:
        return (
            "Sure, let's talk about that! "
            "After we cover this, I'd like to circle back to get a few more details."
        )
    return (
        "Of course! Let me address that. "
        "Once we're done, I'd love to continue our conversation."
    )


async def _generate_resume_text(frame: FlowFrame) -> str:
    """Generate text to smoothly resume a previous flow."""
    step = frame.step
    flow = frame.flow_type

    if flow == FlowType.QUALIFICATION:
        if step == "ask_budget":
            return "What price range were you thinking of?"
        if step == "ask_timeline":
            return "When are you hoping to move?"
        if step == "ask_location":
            return "What areas are you interested in?"
        if step == "ask_property_type":
            return "What type of property are you looking for?"
        return "Could we pick up where we left off with a couple of quick questions?"

    if flow == FlowType.DISCOVERY:
        return "I'd love to learn a bit more about what you're looking for."

    if flow == FlowType.SCHEDULING:
        return "Getting back to scheduling — let's find a time that works."

    return "Let me continue where we left off."


def _intent_to_flow(intent: IntentCategory) -> FlowType:
    """Map an intent category to the appropriate flow type."""
    mapping = {
        IntentCategory.SUPPORT_QUESTION: FlowType.SUPPORT,
        IntentCategory.PROPERTY_INQUIRY: FlowType.DISCOVERY,
        IntentCategory.SCHEDULING_REQUEST: FlowType.SCHEDULING,
        IntentCategory.TOPIC_CHANGE: FlowType.GENERAL,
        IntentCategory.GENERAL_CHAT: FlowType.GENERAL,
    }
    return mapping.get(intent, FlowType.GENERAL)


def get_stack_depth(lead_id: str) -> int:
    """Return current conversation stack depth for a lead."""
    return len(_get_stack(lead_id))


def clear_stack(lead_id: str) -> None:
    """Clear the conversation stack (e.g., after qualification completes)."""
    _conversation_stacks.pop(lead_id, None)
    logger.info("stack_cleared", lead_id=lead_id)
