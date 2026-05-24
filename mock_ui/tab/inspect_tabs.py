from __future__ import annotations

import sys
from typing import Any, Mapping, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QTabWidget, QVBoxLayout, QWidget

try:
    from .event_item import InspectEvent
    from .request_json_tab import RequestJsonTab
    from .response_tab import ResponseTab
    from .session_event_tab import SessionEventTab
except ImportError:
    from event_item import InspectEvent
    from request_json_tab import RequestJsonTab
    from response_tab import ResponseTab
    from session_event_tab import SessionEventTab


REQUEST_JSON_TAB = "request_json"
RESPONSE_EVENTS_TAB = "response_events"
SESSION_EVENTS_TAB = "session_events"


class InspectTabs(QWidget):
    tabSelected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("InspectTabs")

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("InspectTabWidget")

        self._request_json_tab = RequestJsonTab(self)
        self._response_tab = ResponseTab(self)
        self._session_event_tab = SessionEventTab(self)

        self._tabs.addTab(self._request_json_tab, "Request JSON")
        self._tabs.addTab(self._response_tab, "Response Events")
        self._tabs.addTab(self._session_event_tab, "Session Events")

        self._tabs.currentChanged.connect(self._onCurrentChanged)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tabs)

        self.setStyleSheet(
            """
            QWidget#InspectTabs {
                background: transparent;
            }

            QTabWidget#InspectTabWidget::pane {
                border: 1px solid #ddd8cf;
                border-radius: 4px;
                background: #fbfaf8;
                top: -1px;
            }

            QTabBar::tab {
                min-width: 118px;
                min-height: 30px;
                padding: 0 12px;
                border: 1px solid #ddd8cf;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                background: #eeeae3;
                color: #5f574d;
                font-size: 12px;
            }

            QTabBar::tab:selected {
                background: #fbfaf8;
                color: #2f2f2f;
                border-color: #cfc8bd;
            }

            QTabBar::tab:hover {
                background: #f5f1eb;
            }
            """
        )

    def setRequestJsonContent(self, content: Any) -> None:
        if content is None:
            self._request_json_tab.clearJsonContent()
            return

        self._request_json_tab.setJsonContent(content)

    def clearRequestJsonContent(self) -> None:
        self.setRequestJsonContent(None)

    def setResponseEvents(self, events: Sequence[InspectEvent | Mapping[str, Any]]) -> None:
        self._response_tab.setEvents(events)

    def appendResponseEvent(self, event: InspectEvent | Mapping[str, Any]) -> int:
        return self._response_tab.appendEvent(event)

    def selectResponseEvent(self, index: int) -> None:
        self._response_tab.selectEvent(index)

    def clearResponseSelection(self) -> None:
        self._response_tab.clearSelection()

    def clearResponseEvents(self) -> None:
        self._response_tab.clearEvents()

    def setSessionEvents(self, events: Sequence[InspectEvent | Mapping[str, Any]]) -> None:
        self._session_event_tab.setEvents(events)

    def appendSessionEvent(self, event: InspectEvent | Mapping[str, Any]) -> int:
        return self._session_event_tab.appendEvent(event)

    def selectSessionEvent(self, index: int) -> None:
        self._session_event_tab.selectEvent(index)

    def clearSessionSelection(self) -> None:
        self._session_event_tab.clearSelection()

    def clearSessionEvents(self) -> None:
        self._session_event_tab.clearEvents()

    def clearAll(self) -> None:
        self.clearRequestJsonContent()
        self.clearResponseEvents()
        self.clearSessionEvents()

    def currentTabName(self) -> str:
        index = self._tabs.currentIndex()

        if index == 0:
            return REQUEST_JSON_TAB

        if index == 1:
            return RESPONSE_EVENTS_TAB

        if index == 2:
            return SESSION_EVENTS_TAB

        return ""

    def selectRequestJsonTab(self) -> None:
        self._tabs.setCurrentIndex(0)

    def selectResponseTab(self) -> None:
        self._tabs.setCurrentIndex(1)

    def selectSessionEventsTab(self) -> None:
        self._tabs.setCurrentIndex(2)

    def requestJsonTab(self) -> RequestJsonTab:
        return self._request_json_tab

    def responseTab(self) -> ResponseTab:
        return self._response_tab

    def sessionEventTab(self) -> SessionEventTab:
        return self._session_event_tab

    def _onCurrentChanged(self, index: int) -> None:
        tab_name = self.currentTabName()
        if not tab_name:
            return

        self.tabSelected.emit(tab_name)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    root = QWidget()
    root.setWindowTitle("InspectTabs Demo")
    root.resize(1120, 640)
    root.setStyleSheet(
        """
        QWidget {
            background: #fbfaf8;
        }
        """
    )

    tabs = InspectTabs(root)

    tabs.setRequestJsonContent(
        {
            "app_name": "runtime_inspector",
            "session_id": "session_001",
            "invocation_id": "inv_001",
            "new_message": {
                "role": "user",
                "parts": [
                    {
                        "text": "Explain response events and session events."
                    }
                ],
            },
        }
    )

    tabs.setResponseEvents(
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
                                    "text": "Explain response events and session events."
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
                        "query": "ADK runtime response events"
                    },
                },
            ),
            {
                "title": "final_response",
                "content": {
                    "invocation_id": "inv_001",
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": "Response events belong to one invocation."
                            }
                        ],
                    },
                },
            },
        ]
    )

    tabs.appendResponseEvent(
        InspectEvent(
            title="stream_chunk",
            content={
                "invocation_id": "inv_001",
                "partial": True,
                "delta": "This is a streamed chunk.",
            },
        )
    )

    tabs.setSessionEvents(
        [
            InspectEvent(
                title="user_message: inv_001",
                content={
                    "session_id": "session_001",
                    "invocation_id": "inv_001",
                    "author": "user",
                    "content": {
                        "role": "user",
                        "parts": [
                            {
                                "text": "Explain response events and session events."
                            }
                        ],
                    },
                },
            ),
            InspectEvent(
                title="model_message: inv_001",
                content={
                    "session_id": "session_001",
                    "invocation_id": "inv_001",
                    "author": "model",
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": "Response events belong to one invocation. Session events belong to the whole session."
                            }
                        ],
                    },
                },
            ),
        ]
    )

    tabs.appendSessionEvent(
        {
            "title": "state_delta: inv_001",
            "content": {
                "session_id": "session_001",
                "invocation_id": "inv_001",
                "actions": {
                    "state_delta": {
                        "last_topic": "runtime_events"
                    }
                },
            },
        }
    )

    def on_tab_selected(tab_name: str) -> None:
        print(f"tabSelected: tab_name={tab_name}")

    tabs.tabSelected.connect(on_tab_selected)

    layout = QVBoxLayout(root)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(0)
    layout.addWidget(tabs)

    root.show()
    sys.exit(app.exec())