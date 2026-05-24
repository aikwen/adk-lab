from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


@dataclass(slots=True)
class InspectEvent:
    title: str
    content: Any


class EventItem(QFrame):
    clicked = Signal()

    def __init__(self, event: InspectEvent | Mapping[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._event = _normalizeEvent(event)
        self._selected = False

        self.setObjectName("EventItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._title = QLabel(self)
        self._title.setObjectName("EventItemTitle")
        self._title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._title.setWordWrap(False)
        self._title.setText(self._event.title)
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)
        layout.addWidget(self._title)

        self.setStyleSheet(
            """
            QFrame#EventItem {
                min-height: 40px;
                border: 1px solid #ddd8cf;
                border-radius: 4px;
                background: #ffffff;
            }

            QFrame#EventItem:hover {
                background: #f4f1ec;
            }

            QFrame#EventItem[selected="true"] {
                border: 1px solid #9f9281;
                background: #eee8df;
            }

            QLabel#EventItemTitle {
                background: transparent;
                border: none;
                color: #2f2f2f;
                font-size: 13px;
            }
            """
        )

        self._refreshStyle()

    def inspectEvent(self) -> InspectEvent:
        return self._event

    def title(self) -> str:
        return self._event.title

    def content(self) -> Any:
        return self._event.content

    def setInspectEvent(self, event: InspectEvent | Mapping[str, Any]) -> None:
        self._event = _normalizeEvent(event)
        self._title.setText(self._event.title)

    def setTitle(self, title: str) -> None:
        self._event = InspectEvent(title=title, content=self._event.content)
        self._title.setText(title)

    def setContent(self, content: Any) -> None:
        self._event = InspectEvent(title=self._event.title, content=content)

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


def _normalizeEvent(event: InspectEvent | Mapping[str, Any]) -> InspectEvent:
    if isinstance(event, InspectEvent):
        return event

    title = str(event.get("title", ""))
    content = event.get("content")

    return InspectEvent(title=title, content=content)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    root = QWidget()
    root.setWindowTitle("EventItem Demo")
    root.resize(360, 220)
    root.setStyleSheet(
        """
        QWidget {
            background: #fbfaf8;
        }
        """
    )

    layout = QVBoxLayout(root)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    item_1 = EventItem(
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
        )
    )

    item_2 = EventItem(
        InspectEvent(
            title="tool_call",
            content={
                "tool_name": "search_docs",
                "args": {
                    "query": "ADK session events"
                },
            },
        )
    )

    item_3 = EventItem(
        {
            "title": "final_response",
            "content": {
                "role": "model",
                "parts": [
                    {
                        "text": "Session events belong to the session."
                    }
                ],
            },
        }
    )

    items = [item_1, item_2, item_3]

    def on_clicked(clicked_item: EventItem) -> None:
        print(f"clicked: title={clicked_item.title()}")
        print(f"content={clicked_item.content()}")

        for item in items:
            item.setSelected(item is clicked_item)

    for item in items:
        item.clicked.connect(lambda checked=False, current=item: on_clicked(current))
        layout.addWidget(item)

    layout.addStretch(1)

    root.show()
    sys.exit(app.exec())