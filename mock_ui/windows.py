from __future__ import annotations

import sys
from typing import Any, Mapping, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from .panel_chat import RequestMessage, RequestPanel
    from .tab.event_item import InspectEvent
    from .tab.inspect_tabs import (
        InspectTabs,
        REQUEST_JSON_TAB,
        RESPONSE_EVENTS_TAB,
        SESSION_EVENTS_TAB,
    )
except ImportError:
    from panel_chat import RequestMessage, RequestPanel
    from tab.event_item import InspectEvent
    from tab.inspect_tabs import (
        InspectTabs,
        REQUEST_JSON_TAB,
        RESPONSE_EVENTS_TAB,
        SESSION_EVENTS_TAB,
    )


class TopBar(QWidget):
    sessionSelected = Signal(str)
    newSessionRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("TopBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._session_label = QLabel("Session", self)
        self._session_label.setObjectName("SessionLabel")

        self._session_combo = QComboBox(self)
        self._session_combo.setObjectName("SessionCombo")
        self._session_combo.currentTextChanged.connect(self._onCurrentTextChanged)

        self._new_session_button = QPushButton("New Session", self)
        self._new_session_button.setObjectName("NewSessionButton")
        self._new_session_button.clicked.connect(self.newSessionRequested.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(self._session_label)
        layout.addWidget(self._session_combo, 1)
        layout.addWidget(self._new_session_button)

        self.setStyleSheet(
            """
            QWidget#TopBar {
                background: #fbfaf8;
                border: 1px solid #ddd8cf;
                border-radius: 4px;
            }

            QLabel#SessionLabel {
                background: transparent;
                color: #5f574d;
                font-size: 13px;
            }

            QComboBox#SessionCombo {
                min-height: 30px;
                padding: 0 8px;
                border: 1px solid #d8d3cb;
                border-radius: 4px;
                background: #ffffff;
                color: #2f2f2f;
                font-size: 13px;
            }

            QPushButton#NewSessionButton {
                min-height: 30px;
                padding: 0 12px;
                border: 1px solid #cfc8bd;
                border-radius: 4px;
                background: #f0ede8;
                color: #2f2f2f;
                font-size: 13px;
            }

            QPushButton#NewSessionButton:hover {
                background: #e8e3dc;
            }

            QPushButton#NewSessionButton:pressed {
                background: #ddd6cb;
            }
            """
        )

    def setSessionIds(
        self,
        session_ids: Sequence[str],
        *,
        current_session_id: str | None = None,
        emit_signal: bool = False,
    ) -> None:
        old_blocked = self._session_combo.blockSignals(not emit_signal)

        self._session_combo.clear()
        self._session_combo.addItems([str(session_id) for session_id in session_ids])

        if current_session_id is not None:
            self.setCurrentSessionId(current_session_id, emit_signal=emit_signal)

        self._session_combo.blockSignals(old_blocked)

    def addSessionId(
        self,
        session_id: str,
        *,
        activate: bool = True,
        emit_signal: bool = False,
    ) -> None:
        session_id = str(session_id)

        old_blocked = self._session_combo.blockSignals(not emit_signal)

        if self._session_combo.findText(session_id) < 0:
            self._session_combo.addItem(session_id)

        self._session_combo.blockSignals(old_blocked)

        if activate:
            self.setCurrentSessionId(session_id, emit_signal=emit_signal)

    def setCurrentSessionId(self, session_id: str, *, emit_signal: bool = False) -> None:
        session_id = str(session_id)
        index = self._session_combo.findText(session_id)

        if index < 0:
            return

        old_blocked = self._session_combo.blockSignals(not emit_signal)
        self._session_combo.setCurrentIndex(index)
        self._session_combo.blockSignals(old_blocked)

    def currentSessionId(self) -> str:
        return self._session_combo.currentText()

    def _onCurrentTextChanged(self, text: str) -> None:
        if not text:
            return

        self.sessionSelected.emit(text)


class MainWindow(QMainWindow):
    sessionSelected = Signal(str)
    newSessionRequested = Signal()

    requestSelected = Signal(int, str)
    sendRequested = Signal(str)

    inspectTabSelected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("MainWindow")
        self.setWindowTitle("ADK Runtime Inspector")
        self.resize(1280, 760)

        self._top_bar = TopBar(self)
        self._request_panel = RequestPanel(self)
        self._inspect_tabs = InspectTabs(self)

        self._left_frame = QFrame(self)
        self._left_frame.setObjectName("LeftFrame")
        self._left_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        left_layout = QVBoxLayout(self._left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self._request_panel)

        self._right_frame = QFrame(self)
        self._right_frame.setObjectName("RightFrame")
        self._right_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        right_layout = QVBoxLayout(self._right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._inspect_tabs)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._left_frame, 2)
        content_layout.addWidget(self._right_frame, 5)

        root = QWidget(self)
        root.setObjectName("Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)
        root_layout.addWidget(self._top_bar)
        root_layout.addLayout(content_layout, 1)

        self.setCentralWidget(root)

        self._top_bar.sessionSelected.connect(self.sessionSelected.emit)
        self._top_bar.newSessionRequested.connect(self.newSessionRequested.emit)

        self._request_panel.requestSelected.connect(self.requestSelected.emit)
        self._request_panel.sendRequested.connect(self.sendRequested.emit)

        self._inspect_tabs.tabSelected.connect(self.inspectTabSelected.emit)

        self.setStyleSheet(
            """
            QMainWindow#MainWindow {
                background: #f3f0ea;
            }

            QWidget#Root {
                background: #f3f0ea;
            }

            QFrame#LeftFrame,
            QFrame#RightFrame {
                background: transparent;
                border: none;
            }
            """
        )

    def setSessionIds(
        self,
        session_ids: Sequence[str],
        *,
        current_session_id: str | None = None,
        emit_signal: bool = False,
    ) -> None:
        self._top_bar.setSessionIds(
            session_ids,
            current_session_id=current_session_id,
            emit_signal=emit_signal,
        )

    def addSessionId(
        self,
        session_id: str,
        *,
        activate: bool = True,
        emit_signal: bool = False,
    ) -> None:
        self._top_bar.addSessionId(
            session_id,
            activate=activate,
            emit_signal=emit_signal,
        )

    def setCurrentSessionId(self, session_id: str, *, emit_signal: bool = False) -> None:
        self._top_bar.setCurrentSessionId(session_id, emit_signal=emit_signal)

    def currentSessionId(self) -> str:
        return self._top_bar.currentSessionId()

    def setRequests(self, requests: Sequence[RequestMessage | Mapping[str, str]]) -> None:
        self._request_panel.setRequests(requests)

    def appendRequest(self, request: RequestMessage | Mapping[str, str]) -> int:
        return self._request_panel.appendRequest(request)

    def clearRequests(self) -> None:
        self._request_panel.clearRequests()

    def selectRequest(self, index: int) -> None:
        self._request_panel.selectRequest(index)

    def clearRequestSelection(self) -> None:
        self._request_panel.clearSelection()

    def selectedRequest(self) -> RequestMessage | None:
        return self._request_panel.selectedRequest()

    def selectedRequestIndex(self) -> int:
        return self._request_panel.selectedIndex()

    def requests(self) -> list[RequestMessage]:
        return self._request_panel.requests()

    def inputText(self) -> str:
        return self._request_panel.inputText()

    def setInputText(self, text: str) -> None:
        self._request_panel.setInputText(text)

    def clearInput(self) -> None:
        self._request_panel.clearInput()

    def setSendEnabled(self, enabled: bool) -> None:
        self._request_panel.setSendEnabled(enabled)

    def isSendEnabled(self) -> bool:
        return self._request_panel.isSendEnabled()

    def setSending(self, sending: bool) -> None:
        self.setSendEnabled(not sending)

    def isSending(self) -> bool:
        return not self.isSendEnabled()

    def setRequestJsonContent(self, content: Any) -> None:
        self._inspect_tabs.setRequestJsonContent(content)

    def clearRequestJsonContent(self) -> None:
        self._inspect_tabs.clearRequestJsonContent()

    def setResponseEvents(self, events: Sequence[InspectEvent | Mapping[str, Any]]) -> None:
        self._inspect_tabs.setResponseEvents(events)

    def appendResponseEvent(self, event: InspectEvent | Mapping[str, Any]) -> int:
        return self._inspect_tabs.appendResponseEvent(event)

    def selectResponseEvent(self, index: int) -> None:
        self._inspect_tabs.selectResponseEvent(index)

    def clearResponseSelection(self) -> None:
        self._inspect_tabs.clearResponseSelection()

    def clearResponseEvents(self) -> None:
        self._inspect_tabs.clearResponseEvents()

    def setSessionEvents(self, events: Sequence[InspectEvent | Mapping[str, Any]]) -> None:
        self._inspect_tabs.setSessionEvents(events)

    def appendSessionEvent(self, event: InspectEvent | Mapping[str, Any]) -> int:
        return self._inspect_tabs.appendSessionEvent(event)

    def selectSessionEvent(self, index: int) -> None:
        self._inspect_tabs.selectSessionEvent(index)

    def clearSessionSelection(self) -> None:
        self._inspect_tabs.clearSessionSelection()

    def clearSessionEvents(self) -> None:
        self._inspect_tabs.clearSessionEvents()

    def clearInspectTabs(self) -> None:
        self._inspect_tabs.clearAll()

    def currentInspectTab(self) -> str:
        return self._inspect_tabs.currentTabName()

    def selectRequestJsonTab(self) -> None:
        self._inspect_tabs.selectRequestJsonTab()

    def selectResponseTab(self) -> None:
        self._inspect_tabs.selectResponseTab()

    def selectSessionEventsTab(self) -> None:
        self._inspect_tabs.selectSessionEventsTab()

    def topBar(self) -> TopBar:
        return self._top_bar

    def requestPanel(self) -> RequestPanel:
        return self._request_panel

    def inspectTabs(self) -> InspectTabs:
        return self._inspect_tabs


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()

    request_json_by_invocation: dict[str, dict[str, Any]] = {
        "inv_001": {
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
        },
        "inv_002": {
            "app_name": "runtime_inspector",
            "session_id": "session_001",
            "invocation_id": "inv_002",
            "new_message": {
                "role": "user",
                "parts": [
                    {
                        "text": "Call a mock search tool."
                    }
                ],
            },
        },
    }

    response_events_by_invocation: dict[str, list[InspectEvent]] = {
        "inv_001": [
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
                title="final_response",
                content={
                    "invocation_id": "inv_001",
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
        ],
        "inv_002": [
            InspectEvent(
                title="llm_request",
                content={
                    "invocation_id": "inv_002",
                    "model": "gemini-2.0-flash",
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": "Call a mock search tool."
                                }
                            ],
                        }
                    ],
                },
            ),
            InspectEvent(
                title="tool_call: mock_search",
                content={
                    "invocation_id": "inv_002",
                    "tool_name": "mock_search",
                    "args": {
                        "query": "ADK runtime inspector"
                    },
                },
            ),
            InspectEvent(
                title="tool_response: mock_search",
                content={
                    "invocation_id": "inv_002",
                    "tool_name": "mock_search",
                    "response": {
                        "ok": True,
                        "items": [
                            {
                                "title": "Runtime",
                                "score": 0.91,
                            }
                        ],
                    },
                },
            ),
        ],
    }

    def current_session_events() -> list[InspectEvent]:
        return [
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
            InspectEvent(
                title="user_message: inv_002",
                content={
                    "session_id": "session_001",
                    "invocation_id": "inv_002",
                    "author": "user",
                    "content": {
                        "role": "user",
                        "parts": [
                            {
                                "text": "Call a mock search tool."
                            }
                        ],
                    },
                },
            ),
        ]

    window.setSessionIds(["session_001", "session_002"], current_session_id="session_001")
    window.setRequests(
        [
            RequestMessage(
                text="Explain response events and session events.",
                invocation_id="inv_001",
            ),
            RequestMessage(
                text="Call a mock search tool.",
                invocation_id="inv_002",
            ),
        ]
    )

    def on_request_selected(index: int, invocation_id: str) -> None:
        print(f"requestSelected: index={index}, invocation_id={invocation_id}")

        window.setRequestJsonContent(request_json_by_invocation.get(invocation_id))
        window.setResponseEvents(response_events_by_invocation.get(invocation_id, []))
        window.clearResponseSelection()

    def on_send_requested(text: str) -> None:
        print(f"sendRequested: text={text}")

        window.setSending(True)

        next_index = len(window.requests()) + 1
        invocation_id = f"inv_{next_index:03d}"

        request = RequestMessage(
            text=text,
            invocation_id=invocation_id,
        )

        request_json_by_invocation[invocation_id] = {
            "app_name": "runtime_inspector",
            "session_id": window.currentSessionId(),
            "invocation_id": invocation_id,
            "new_message": {
                "role": "user",
                "parts": [
                    {
                        "text": text
                    }
                ],
            },
        }

        response_events_by_invocation[invocation_id] = []

        index = window.appendRequest(request)
        window.clearInput()
        window.selectRequest(index)

        response_events_by_invocation[invocation_id].append(
            InspectEvent(
                title="llm_request",
                content={
                    "invocation_id": invocation_id,
                    "model": "mock_model",
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": text
                                }
                            ],
                        }
                    ],
                },
            )
        )

        if window.selectedRequest() is not None and window.selectedRequest().invocation_id == invocation_id:
            window.setResponseEvents(response_events_by_invocation[invocation_id])

        window.setSending(False)

    def on_inspect_tab_selected(tab_name: str) -> None:
        print(f"inspectTabSelected: tab_name={tab_name}")

        if tab_name == SESSION_EVENTS_TAB:
            window.setSessionEvents(current_session_events())
            window.clearSessionSelection()

    def on_new_session_requested() -> None:
        print("newSessionRequested")

        next_index = 1
        while True:
            session_id = f"session_{next_index:03d}"
            if session_id not in [window.topBar().currentSessionId()]:
                break
            next_index += 1

        window.addSessionId(session_id, activate=True, emit_signal=True)
        window.clearRequests()
        window.clearInspectTabs()

    def on_session_selected(session_id: str) -> None:
        print(f"sessionSelected: session_id={session_id}")

        window.clearRequests()
        window.clearInspectTabs()

    window.requestSelected.connect(on_request_selected)
    window.sendRequested.connect(on_send_requested)
    window.inspectTabSelected.connect(on_inspect_tab_selected)
    window.newSessionRequested.connect(on_new_session_requested)
    window.sessionSelected.connect(on_session_selected)

    window.show()
    sys.exit(app.exec())