"""
Meta Flow Parser - WhatsApp Flows decoder.

Handles structured form responses from WhatsApp Flows including
qualification forms, scheduling flows, and general form submissions.
"""

import json
import time
from enum import Enum
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class FlowType(str, Enum):
    QUALIFICATION = "qualification"
    SCHEDULING = "scheduling"
    CONTACT_FORM = "contact_form"
    PREFERENCE_UPDATE = "preference_update"
    UNKNOWN = "unknown"


# Known flow ID → type mapping (configure per deployment)
FLOW_TYPE_MAP: dict[str, FlowType] = {
    "qualification_flow": FlowType.QUALIFICATION,
    "scheduling_flow": FlowType.SCHEDULING,
    "contact_form_flow": FlowType.CONTACT_FORM,
    "preference_flow": FlowType.PREFERENCE_UPDATE,
}


class MetaFlowParser:
    """
    Decodes structured JSON responses from WhatsApp Flows
    and maps form fields to CRM lead fields.
    """

    def __init__(self, db_session_factory=None, redis_client=None, llm_client=None):
        self._db_factory = db_session_factory
        self._redis = redis_client
        self._llm = llm_client

    # -- Core parsing --

    async def parse_flow_response(self, flow_data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse an incoming WhatsApp Flow response.
        Returns normalized data with flow type and extracted fields.
        """
        # Extract flow metadata
        flow_id = flow_data.get("flow_id", "")
        flow_token = flow_data.get("flow_token", "")
        screen_id = flow_data.get("screen", "")
        data = flow_data.get("data", {})

        # Determine flow type
        flow_type = FLOW_TYPE_MAP.get(flow_id, FlowType.UNKNOWN)

        # Extract form fields from the response
        fields = await self.extract_form_fields(data)

        result = {
            "flow_id": flow_id,
            "flow_token": flow_token,
            "screen_id": screen_id,
            "flow_type": flow_type,
            "fields": fields,
            "raw_data": data,
            "parsed_at": time.time(),
        }

        logger.info(
            "flow_parsed",
            flow_id=flow_id,
            flow_type=flow_type.value,
            field_count=len(fields),
        )

        return result

    async def extract_form_fields(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract form field values from WhatsApp Flow response data.
        Handles checkboxes, dropdowns, text inputs, date pickers, etc.
        """
        fields = {}

        for key, value in response_data.items():
            if value is None:
                continue

            # Checkbox groups return arrays of selected values
            if isinstance(value, list):
                fields[key] = {
                    "type": "checkbox_group",
                    "values": value,
                    "display": ", ".join(str(v) for v in value),
                }
            # Dropdown / radio buttons return single string
            elif isinstance(value, str):
                fields[key] = {
                    "type": "text",
                    "value": value,
                    "display": value,
                }
            # Numeric inputs
            elif isinstance(value, (int, float)):
                fields[key] = {
                    "type": "number",
                    "value": value,
                    "display": str(value),
                }
            # Nested objects (date pickers, complex inputs)
            elif isinstance(value, dict):
                fields[key] = self._parse_complex_field(value)
            else:
                fields[key] = {
                    "type": "unknown",
                    "value": value,
                    "display": str(value),
                }

        return fields

    def _parse_complex_field(self, value: dict) -> dict[str, Any]:
        """Parse complex field types like date pickers."""
        # Date picker format: {"date": "2024-01-15"}
        if "date" in value:
            return {
                "type": "date",
                "value": value["date"],
                "display": value["date"],
            }
        # Time picker format: {"hour": 14, "minute": 30}
        if "hour" in value and "minute" in value:
            time_str = f"{value['hour']:02d}:{value['minute']:02d}"
            return {
                "type": "time",
                "value": value,
                "display": time_str,
            }
        # Location picker
        if "latitude" in value and "longitude" in value:
            return {
                "type": "location",
                "value": value,
                "display": f"{value['latitude']}, {value['longitude']}",
            }
        # Generic nested
        return {
            "type": "complex",
            "value": value,
            "display": json.dumps(value),
        }

    # -- Flow-specific handlers --

    async def handle_qualification_flow(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Process a qualification form response.
        Maps form answers to lead qualification fields.
        """
        parsed = await self.parse_flow_response(response)
        fields = parsed["fields"]

        # Map common qualification fields
        qualifications = {}

        # Budget range
        if "budget" in fields:
            qualifications["budget"] = fields["budget"]["value"]
        elif "budget_min" in fields and "budget_max" in fields:
            qualifications["budget"] = {
                "min": fields["budget_min"]["value"],
                "max": fields["budget_max"]["value"],
            }

        # Property type
        if "property_type" in fields:
            pt = fields["property_type"]
            qualifications["property_type"] = pt["values"] if pt["type"] == "checkbox_group" else pt["value"]

        # Location preferences
        if "preferred_areas" in fields:
            pa = fields["preferred_areas"]
            qualifications["preferred_areas"] = pa["values"] if pa["type"] == "checkbox_group" else [pa["value"]]

        # Timeline
        if "timeline" in fields:
            qualifications["timeline"] = fields["timeline"]["value"]

        # Bedrooms
        if "bedrooms" in fields:
            qualifications["bedrooms"] = fields["bedrooms"]["value"]

        # Financing
        if "financing" in fields:
            qualifications["financing"] = fields["financing"]["value"]

        # First-time buyer
        if "first_time_buyer" in fields:
            qualifications["first_time_buyer"] = fields["first_time_buyer"]["value"]

        # Calculate warmth score based on responses
        warmth = self._calculate_qualification_warmth(qualifications)
        qualifications["warmth_score"] = warmth

        result = {
            "flow_type": FlowType.QUALIFICATION,
            "qualifications": qualifications,
            "warmth_score": warmth,
            "parsed": parsed,
        }

        logger.info("qualification_processed", warmth=warmth, fields=list(qualifications.keys()))
        return result

    async def handle_scheduling_flow(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Process a scheduling/booking flow response.
        Extracts date, time, and appointment details.
        """
        parsed = await self.parse_flow_response(response)
        fields = parsed["fields"]

        booking = {}

        # Date
        if "preferred_date" in fields:
            booking["date"] = fields["preferred_date"]["value"]
        elif "date" in fields:
            booking["date"] = fields["date"]["value"]

        # Time
        if "preferred_time" in fields:
            booking["time"] = fields["preferred_time"]["value"]
        elif "time" in fields:
            booking["time"] = fields["time"]["value"]

        # Appointment type
        if "appointment_type" in fields:
            booking["type"] = fields["appointment_type"]["value"]

        # Property of interest
        if "property_id" in fields:
            booking["property_id"] = fields["property_id"]["value"]

        # Notes
        if "notes" in fields:
            booking["notes"] = fields["notes"]["value"]

        # Contact method preference
        if "contact_method" in fields:
            booking["contact_method"] = fields["contact_method"]["value"]

        result = {
            "flow_type": FlowType.SCHEDULING,
            "booking": booking,
            "parsed": parsed,
        }

        logger.info("scheduling_processed", date=booking.get("date"), time=booking.get("time"))
        return result

    # -- CRM update --

    async def update_lead_from_flow(self, lead_id: str, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update CRM lead fields based on parsed flow response.
        """
        flow_type = parsed_data.get("flow_type", FlowType.UNKNOWN)
        updates: dict[str, Any] = {}

        if flow_type == FlowType.QUALIFICATION:
            quals = parsed_data.get("qualifications", {})
            updates.update({
                "property_preferences": quals.get("property_type"),
                "budget": quals.get("budget"),
                "preferred_areas": quals.get("preferred_areas"),
                "timeline": quals.get("timeline"),
                "bedrooms": quals.get("bedrooms"),
                "financing": quals.get("financing"),
                "warmth_score": quals.get("warmth_score"),
                "stage": "QUALIFIED" if quals.get("warmth_score", 0) >= 60 else "ENGAGED",
            })

        elif flow_type == FlowType.SCHEDULING:
            booking = parsed_data.get("booking", {})
            updates["last_booking_request"] = booking
            updates["stage"] = "APPOINTMENT_REQUESTED"

        elif flow_type == FlowType.CONTACT_FORM:
            fields = parsed_data.get("parsed", {}).get("fields", {})
            if "name" in fields:
                updates["name"] = fields["name"]["value"]
            if "email" in fields:
                updates["email"] = fields["email"]["value"]
            if "phone" in fields:
                updates["phone"] = fields["phone"]["value"]

        # Filter out None values
        updates = {k: v for k, v in updates.items() if v is not None}

        if updates:
            await self._db_update_lead(lead_id, updates)
            logger.info("lead_updated_from_flow", lead_id=lead_id, fields=list(updates.keys()))

        return {"lead_id": lead_id, "updates": updates, "flow_type": flow_type.value}

    # -- Helpers --

    def _calculate_qualification_warmth(self, qualifications: dict) -> int:
        """Calculate a 0-100 warmth score from qualification responses."""
        score = 0

        # Budget provided = serious
        if qualifications.get("budget"):
            score += 20

        # Timeline urgency
        timeline = qualifications.get("timeline", "")
        if "immediate" in timeline.lower() or "asap" in timeline.lower():
            score += 25
        elif "1 month" in timeline.lower() or "month" in timeline.lower():
            score += 20
        elif "3 month" in timeline.lower():
            score += 15
        elif "6 month" in timeline.lower():
            score += 10
        else:
            score += 5

        # Property type specified
        if qualifications.get("property_type"):
            score += 10

        # Preferred areas specified
        if qualifications.get("preferred_areas"):
            score += 10

        # Financing sorted
        if qualifications.get("financing") and "pre-approved" in str(qualifications["financing"]).lower():
            score += 20
        elif qualifications.get("financing"):
            score += 10

        # First-time buyer = motivated
        if qualifications.get("first_time_buyer"):
            score += 10

        return min(score, 100)

    # -- DB stubs --

    async def _db_update_lead(self, lead_id: str, updates: dict[str, Any]) -> None:
        """Update lead fields in database."""
        pass  # Implement with SQLAlchemy
