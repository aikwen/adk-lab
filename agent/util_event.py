from typing import Any

from google.adk.events import Event


def event_to_dict(event: Event) -> dict[str, Any]:
    return event.model_dump(mode="json", exclude_none=True)