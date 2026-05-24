from __future__ import annotations

import sys
from typing import Any, Mapping, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QFrame, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

try:
    from .event_item import EventItem, InspectEvent
except ImportError:
    from event_item import EventItem, InspectEvent


class EventList(QWidget):
    eventSelected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._events: list[InspectEvent] = []
        self._items: list[EventItem] = []
        self._selected_index = -1

        self.setObjectName("EventList")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._content = QWidget(self)
        self._content.setObjectName("EventListContent")

        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)
        self._content_layout.addStretch(1)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("EventListScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(self._content)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._scroll)

        self.setStyleSheet(
            """
            QWidget#EventList {
                background: transparent;
            }

            QWidget#EventListContent {
                background: transparent;
            }

            QScrollArea#EventListScroll {
                background: transparent;
                border: none;
            }
            """
        )

    def setEvents(self, events: Sequence[InspectEvent | Mapping[str, Any]]) -> None:
        self.clearEvents()

        for event in events:
            self._appendEventItem(_normalizeEvent(event))

    def appendEvent(self, event: InspectEvent | Mapping[str, Any]) -> int:
        return self._appendEventItem(_normalizeEvent(event))

    def clearEvents(self) -> None:
        self.clearSelection()

        for item in self._items:
            self._content_layout.removeWidget(item)
            item.deleteLater()

        self._events.clear()
        self._items.clear()

    def selectEvent(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            return

        self._setSelectedIndex(index)
        self.eventSelected.emit(index)

    def clearSelection(self) -> None:
        if self._selected_index != -1 and self._selected_index < len(self._items):
            self._items[self._selected_index].setSelected(False)

        self._selected_index = -1

    def selectedIndex(self) -> int:
        return self._selected_index

    def selectedEvent(self) -> InspectEvent | None:
        if self._selected_index < 0 or self._selected_index >= len(self._events):
            return None

        return self._events[self._selected_index]

    def events(self) -> list[InspectEvent]:
        return list(self._events)

    def _appendEventItem(self, event: InspectEvent) -> int:
        index = len(self._events)

        item = EventItem(event, self)
        item.clicked.connect(lambda checked=False, i=index: self.selectEvent(i))

        self._events.append(event)
        self._items.append(item)

        self._content_layout.insertWidget(self._content_layout.count() - 1, item)

        return index

    def _setSelectedIndex(self, index: int) -> None:
        if self._selected_index == index:
            return

        if self._selected_index != -1 and self._selected_index < len(self._items):
            self._items[self._selected_index].setSelected(False)

        self._selected_index = index
        self._items[index].setSelected(True)


def _normalizeEvent(event: InspectEvent | Mapping[str, Any]) -> InspectEvent:
    if isinstance(event, InspectEvent):
        return event

    title = str(event.get("title", ""))
    content = event.get("content")

    return InspectEvent(title=title, content=content)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    root = QWidget()
    root.setWindowTitle("EventList Demo")
    root.resize(360, 520)
    root.setStyleSheet(
        """
        QWidget {
            background: #fbfaf8;
        }
        """
    )

    event_list = EventList(root)
    event_list.setEvents(
        [
            InspectEvent(
                title="llm_request",
                content={
                    "model": "gemini-2.0-flash",
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": "Explain session events."
                                }
                            ],
                        }
                    ],
                },
            ),
            InspectEvent(
                title="tool_call",
                content={
                    "tool_name": "search_docs",
                    "args": {
                        "query": "ADK session events"
                    },
                },
            ),
            {
                "title": "tool_response",
                "content": {
                    "ok": True,
                    "items": [
                        {
                            "title": "Runtime Events",
                            "score": 0.92,
                        }
                    ],
                },
            },
            {
                "title": "final_response",
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "text": "Session events belong to the current session."
                        }
                    ],
                },
            },
        ]
    )

    def on_event_selected(index: int) -> None:
        event = event_list.selectedEvent()
        if event is None:
            return

        print(f"eventSelected: index={index}")
        print(f"title={event.title}")
        print(f"content={event.content}")

    event_list.eventSelected.connect(on_event_selected)

    layout = QVBoxLayout(root)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(0)
    layout.addWidget(event_list)

    event_list.appendEvent(
        InspectEvent(
            title="stream_chunk",
            content={
                "delta": "This is a streamed response chunk.",
                "partial": True,
            },
        )
    )

    root.show()
    sys.exit(app.exec())