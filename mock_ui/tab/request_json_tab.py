from __future__ import annotations

import sys
from typing import Any

from PySide6.QtWidgets import QApplication, QSizePolicy, QVBoxLayout, QWidget

try:
    from .json_text_viewer import JsonTextViewer
except ImportError:
    from json_text_viewer import JsonTextViewer


class RequestJsonTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("RequestJsonTab")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._viewer = JsonTextViewer(self)
        self._viewer.setPlaceholderText("Select a request to inspect its request JSON.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(self._viewer)

        self.setStyleSheet(
            """
            QWidget#RequestJsonTab {
                background: transparent;
            }
            """
        )

    def setJsonContent(self, content: Any) -> None:
        self._viewer.setJsonContent(content)

    def clearJsonContent(self) -> None:
        self._viewer.clearJsonContent()

    def jsonContent(self) -> Any:
        return self._viewer.jsonContent()

    def text(self) -> str:
        return self._viewer.text()

    def rawText(self) -> str:
        return self._viewer.rawText()

    def copyText(self) -> None:
        self._viewer.copyText()

    def setPlaceholderText(self, text: str) -> None:
        self._viewer.setPlaceholderText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    root = QWidget()
    root.setWindowTitle("RequestJsonTab Demo")
    root.resize(720, 560)
    root.setStyleSheet(
        """
        QWidget {
            background: #fbfaf8;
        }
        """
    )

    tab = RequestJsonTab(root)
    tab.setJsonContent(
        {
            "app_name": "runtime_inspector",
            "user_id": "demo_user",
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
                "source": "mock_runtime",
            },
        }
    )

    layout = QVBoxLayout(root)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(0)
    layout.addWidget(tab)

    root.show()
    sys.exit(app.exec())