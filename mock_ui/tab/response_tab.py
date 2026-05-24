from __future__ import annotations

import sys
from typing import Any, Mapping, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QSizePolicy, QWidget

try:
    from .event_item import InspectEvent
    from .event_list import EventList
    from .json_text_viewer import JsonTextViewer
except ImportError:
    from event_item import InspectEvent
    from event_list import EventList
    from json_text_viewer import JsonTextViewer


class ResponseTab(QWidget):
    eventSelected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("ResponseTab")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._event_list = EventList(self)
        self._event_list.setObjectName("ResponseEventList")
        self._event_list.eventSelected.connect(self._onEventSelected)

        self._json_viewer = JsonTextViewer(self)
        self._json_viewer.setObjectName("ResponseJsonViewer")
        self._json_viewer.setPlaceholderText("Select a response event to inspect its JSON.")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(self._event_list, 2)
        layout.addWidget(self._json_viewer, 5)

        self.setStyleSheet(
            """
            QWidget#ResponseTab {
                background: transparent;
            }
            """
        )

    def setEvents(self, events: Sequence[InspectEvent | Mapping[str, Any]]) -> None:
        self._event_list.setEvents(events)
        self._json_viewer.clearJsonContent()

    def appendEvent(self, event: InspectEvent | Mapping[str, Any]) -> int:
        return self._event_list.appendEvent(event)

    def clearEvents(self) -> None:
        self._event_list.clearEvents()
        self._json_viewer.clearJsonContent()

    def selectEvent(self, index: int) -> None:
        self._event_list.selectEvent(index)

    def clearSelection(self) -> None:
        self._event_list.clearSelection()
        self._json_viewer.clearJsonContent()

    def selectedIndex(self) -> int:
        return self._event_list.selectedIndex()

    def selectedEvent(self) -> InspectEvent | None:
        return self._event_list.selectedEvent()

    def events(self) -> list[InspectEvent]:
        return self._event_list.events()

    def eventList(self) -> EventList:
        return self._event_list

    def jsonViewer(self) -> JsonTextViewer:
        return self._json_viewer

    def setPlaceholderText(self, text: str) -> None:
        self._json_viewer.setPlaceholderText(text)

    def _onEventSelected(self, index: int) -> None:
        event = self._event_list.selectedEvent()
        if event is None:
            return

        self._json_viewer.setJsonContent(event.content)
        self.eventSelected.emit(index)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    root = QWidget()
    root.setWindowTitle("ResponseTab Demo")
    root.resize(980, 560)
    root.setStyleSheet(
        """
        QWidget {
            background: #fbfaf8;
        }
        """
    )

    tab = ResponseTab(root)
    tab.setEvents(
        [
            InspectEvent(
                title="llm_request",
                content={
                    "invocation_id": "inv_001",
                    "model": "gemini-2.0-flash",
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": "Explain session events in Google ADK."
                                }
                            ],
                        }
                    ],
                },
            ),
            InspectEvent(
                title="tool_call: search_docs",
                content={
                    "invocation_id": "inv_001",
                    "tool_name": "search_docs",
                    "args": {
                        "query": "ADK session events"
                    },
                },
            ),
            {
                "title": "tool_response: search_docs",
                "content": {
                    "invocation_id": "inv_001",
                    "tool_name": "search_docs",
                    "response": {
                        "ok": True,
                        "items": [
                            {
                                "title": "Sessions and Memory",
                                "score": 0.92,
                            },
                            {
                                "title": "Runtime Events",
                                "score": 0.88,
                            },
                        ],
                    },
                },
            },
            {
                "title": "final_response",
                "content": {
                    "invocation_id": "inv_001",
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": "Session events are persisted events associated with the current session."
                            }
                        ],
                    },
                },
            },
        ]
    )

    tab.appendEvent(
        InspectEvent(
            title="stream_chunk",
            content={
                "invocation_id": "inv_001",
                "partial": True,
                "delta": "This is a streamed response chunk.",
            },
        )
    )

    def on_event_selected(index: int) -> None:
        event = tab.selectedEvent()
        if event is None:
            return

        print(f"eventSelected: index={index}")
        print(f"title={event.title}")

    tab.eventSelected.connect(on_event_selected)

    layout = QHBoxLayout(root)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(0)
    layout.addWidget(tab)

    root.show()
    sys.exit(app.exec())