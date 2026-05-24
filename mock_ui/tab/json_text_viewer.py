from __future__ import annotations

import json
import sys
from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class JsonTextViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._content: Any = None
        self._raw_text = ""

        self.setObjectName("JsonTextViewer")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._copy_button = QPushButton("Copy", self)
        self._copy_button.setObjectName("JsonCopyButton")
        self._copy_button.clicked.connect(self.copyText)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 6)
        toolbar_layout.setSpacing(0)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self._copy_button)

        self._viewer = QPlainTextEdit(self)
        self._viewer.setObjectName("JsonTextEdit")
        self._viewer.setReadOnly(True)
        self._viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._viewer.setPlaceholderText("No JSON content.")

        font = QFont("Consolas")
        font.setPointSize(10)
        self._viewer.setFont(font)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addLayout(toolbar_layout)
        root_layout.addWidget(self._viewer, 1)

        self.setStyleSheet(
            """
            QWidget#JsonTextViewer {
                background: transparent;
            }

            QPushButton#JsonCopyButton {
                min-height: 26px;
                padding: 0 10px;
                border: 1px solid #cfc8bd;
                border-radius: 4px;
                background: #f0ede8;
                color: #2f2f2f;
                font-size: 12px;
            }

            QPushButton#JsonCopyButton:hover {
                background: #e8e3dc;
            }

            QPushButton#JsonCopyButton:pressed {
                background: #ddd6cb;
            }

            QPlainTextEdit#JsonTextEdit {
                border: 1px solid #ddd8cf;
                border-radius: 4px;
                background: #ffffff;
                color: #2f2f2f;
                padding: 8px;
                selection-background-color: #d8d0c4;
                selection-color: #2f2f2f;
                font-size: 12px;
            }
            """
        )

    def setJsonContent(self, content: Any) -> None:
        self._content = content
        self._raw_text = self._formatJson(content)
        self._viewer.setPlainText(self._decorateJsonText(self._raw_text))

    def clearJsonContent(self) -> None:
        self._content = None
        self._raw_text = ""
        self._viewer.clear()

    def jsonContent(self) -> Any:
        return self._content

    def text(self) -> str:
        return self._viewer.toPlainText()

    def rawText(self) -> str:
        return self._raw_text

    def copyText(self) -> None:
        QApplication.clipboard().setText(self._raw_text)

    def setPlaceholderText(self, text: str) -> None:
        self._viewer.setPlaceholderText(text)

    def _formatJson(self, content: Any) -> str:
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        try:
            return json.dumps(
                content,
                ensure_ascii=False,
                indent=2,
            )
        except TypeError:
            return str(content)

    def _decorateJsonText(self, text: str) -> str:
        if not text:
            return ""

        lines = text.splitlines()
        decorated_lines: list[str] = []

        for line in lines:
            decorated_lines.append(self._decorateJsonLine(line))

        return "\n".join(decorated_lines)

    def _decorateJsonLine(self, line: str) -> str:
        stripped = line.lstrip(" ")
        indent_spaces = len(line) - len(stripped)

        if indent_spaces <= 0:
            return stripped

        level = indent_spaces // 2
        prefix = "| " * level

        return f"{prefix}{stripped}"


if __name__ == "__main__":
    app = QApplication(sys.argv)

    root = QWidget()
    root.setWindowTitle("JsonTextViewer Demo")
    root.resize(720, 560)
    root.setStyleSheet(
        """
        QWidget {
            background: #fbfaf8;
        }
        """
    )

    viewer = JsonTextViewer(root)
    viewer.setJsonContent(
        {
            "app_name": "runtime_inspector",
            "session_id": "session_001",
            "invocation_id": "inv_001",
            "new_message": {
                "role": "user",
                "parts": [
                    {
                        "text": "Explain session events in Google ADK."
                    }
                ],
            },
            "runtime": {
                "streaming": True,
                "tools": [
                    "search",
                    "weather",
                    "code_executor",
                ],
            },
        }
    )

    layout = QVBoxLayout(root)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(0)
    layout.addWidget(viewer)

    root.show()
    sys.exit(app.exec())