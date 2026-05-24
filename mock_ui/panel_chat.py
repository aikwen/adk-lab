from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Mapping, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(slots=True)
class RequestMessage:
    text: str
    invocation_id: str


class RequestItem(QFrame):
    clicked = Signal()

    def __init__(self, request: RequestMessage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._request = request
        self._selected = False

        self.setObjectName("RequestItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._title = QLabel(self)
        self._title.setObjectName("RequestItemTitle")
        self._title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._title.setWordWrap(False)
        self._title.setText(self._request.text)
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._invocation = QLabel(self)
        self._invocation.setObjectName("RequestItemInvocation")
        self._invocation.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._invocation.setText(self._request.invocation_id)
        self._invocation.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        layout.addWidget(self._title)
        layout.addWidget(self._invocation)

        self._refreshStyle()

    def request(self) -> RequestMessage:
        return self._request

    def text(self) -> str:
        return self._request.text

    def invocationId(self) -> str:
        return self._request.invocation_id

    def setRequest(self, request: RequestMessage | Mapping[str, str]) -> None:
        self._request = _normalizeRequest(request)
        self._title.setText(self._request.text)
        self._invocation.setText(self._request.invocation_id)

    def setSelected(self, selected: bool) -> None:
        if self._selected == selected:
            return

        self._selected = selected
        self._refreshStyle()

    def isSelected(self) -> bool:
        return self._selected

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return

        super().mousePressEvent(event)

    def _refreshStyle(self) -> None:
        self.setProperty("selected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)


class RequestPanel(QWidget):
    requestSelected = Signal(int, str)
    sendRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._requests: list[RequestMessage] = []
        self._items: list[RequestItem] = []
        self._selected_index = -1

        self._input = QLineEdit(self)
        self._input.setObjectName("RequestInput")
        self._input.setPlaceholderText("Send a request...")
        self._input.returnPressed.connect(self._emitSendRequested)

        self._send_button = QPushButton("Send", self)
        self._send_button.setObjectName("SendButton")
        self._send_button.clicked.connect(self._emitSendRequested)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        input_layout.addWidget(self._input, 1)
        input_layout.addWidget(self._send_button)

        self._list_widget = QWidget(self)
        self._list_widget.setObjectName("RequestList")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("RequestScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(self._list_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)
        root_layout.addLayout(input_layout)
        root_layout.addWidget(self._scroll, 1)

        self.setStyleSheet(
            """
            RequestPanel {
                background: #fbfaf8;
            }

            QLineEdit#RequestInput {
                min-height: 32px;
                padding: 0 10px;
                border: 1px solid #d8d3cb;
                border-radius: 4px;
                background: #ffffff;
                color: #2f2f2f;
                font-size: 13px;
            }

            QLineEdit#RequestInput:disabled {
                background: #f2eee8;
                color: #9a9186;
            }

            QPushButton#SendButton {
                min-height: 32px;
                padding: 0 14px;
                border: 1px solid #cfc8bd;
                border-radius: 4px;
                background: #f0ede8;
                color: #2f2f2f;
                font-size: 13px;
            }

            QPushButton#SendButton:hover {
                background: #e8e3dc;
            }

            QPushButton#SendButton:pressed {
                background: #ddd6cb;
            }

            QPushButton#SendButton:disabled {
                border: 1px solid #d9d3ca;
                background: #eeeae3;
                color: #aaa196;
            }

            QScrollArea#RequestScroll {
                background: transparent;
                border: none;
            }

            QWidget#RequestList {
                background: transparent;
            }

            QFrame#RequestItem {
                min-height: 54px;
                border: 1px solid #ddd8cf;
                border-radius: 4px;
                background: #ffffff;
            }

            QFrame#RequestItem:hover {
                background: #f4f1ec;
            }

            QFrame#RequestItem[selected="true"] {
                border: 1px solid #9f9281;
                background: #eee8df;
            }

            QLabel#RequestItemTitle {
                color: #2f2f2f;
                font-size: 13px;
            }

            QLabel#RequestItemInvocation {
                color: #8a8176;
                font-size: 11px;
            }
            """
        )

    def setRequests(self, requests: Sequence[RequestMessage | Mapping[str, str]]) -> None:
        self.clearRequests()

        for request in requests:
            self._appendRequestItem(_normalizeRequest(request))

    def appendRequest(self, request: RequestMessage | Mapping[str, str]) -> int:
        return self._appendRequestItem(_normalizeRequest(request))

    def clearRequests(self) -> None:
        self.clearSelection()

        for item in self._items:
            self._list_layout.removeWidget(item)
            item.deleteLater()

        self._requests.clear()
        self._items.clear()

    def selectRequest(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            return

        self._setSelectedIndex(index)
        request = self._requests[index]
        self.requestSelected.emit(index, request.invocation_id)

    def clearSelection(self) -> None:
        if self._selected_index != -1 and self._selected_index < len(self._items):
            self._items[self._selected_index].setSelected(False)

        self._selected_index = -1

    def selectedIndex(self) -> int:
        return self._selected_index

    def selectedRequest(self) -> RequestMessage | None:
        if self._selected_index < 0 or self._selected_index >= len(self._requests):
            return None

        return self._requests[self._selected_index]

    def requests(self) -> list[RequestMessage]:
        return list(self._requests)

    def inputText(self) -> str:
        return self._input.text()

    def setInputText(self, text: str) -> None:
        self._input.setText(text)

    def clearInput(self) -> None:
        self._input.clear()

    def setSendEnabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_button.setEnabled(enabled)

    def isSendEnabled(self) -> bool:
        return self._send_button.isEnabled()

    def _appendRequestItem(self, request: RequestMessage) -> int:
        index = len(self._requests)

        item = RequestItem(request, self)
        item.clicked.connect(lambda checked=False, i=index: self.selectRequest(i))

        self._requests.append(request)
        self._items.append(item)

        self._list_layout.insertWidget(self._list_layout.count() - 1, item)

        return index

    def _setSelectedIndex(self, index: int) -> None:
        if self._selected_index == index:
            return

        if self._selected_index != -1 and self._selected_index < len(self._items):
            self._items[self._selected_index].setSelected(False)

        self._selected_index = index
        self._items[index].setSelected(True)

    def _emitSendRequested(self) -> None:
        if not self._send_button.isEnabled():
            return

        text = self._input.text().strip()
        if not text:
            return

        self.sendRequested.emit(text)


def _normalizeRequest(request: RequestMessage | Mapping[str, str]) -> RequestMessage:
    if isinstance(request, RequestMessage):
        return request

    text = str(request.get("text", ""))
    invocation_id = str(request.get("invocation_id", ""))

    return RequestMessage(text=text, invocation_id=invocation_id)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    panel = RequestPanel()
    panel.resize(360, 520)

    panel.setRequests(
        [
            RequestMessage(
                text="What is Google ADK Runtime?",
                invocation_id="inv_001",
            ),
            RequestMessage(
                text="Call weather tool for Taipei",
                invocation_id="inv_002",
            ),
            RequestMessage(
                text="Explain session events",
                invocation_id="inv_003",
            ),
        ]
    )

    def on_request_selected(index: int, invocation_id: str) -> None:
        print(f"requestSelected: index={index}, invocation_id={invocation_id}")

    def on_send_requested(text: str) -> None:
        print(f"sendRequested: text={text}")

        next_index = len(panel.requests()) + 1
        invocation_id = f"inv_{next_index:03d}"

        panel.appendRequest(
            RequestMessage(
                text=text,
                invocation_id=invocation_id,
            )
        )
        panel.clearInput()

    panel.requestSelected.connect(on_request_selected)
    panel.sendRequested.connect(on_send_requested)

    panel.show()
    sys.exit(app.exec())