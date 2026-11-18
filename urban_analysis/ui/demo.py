"""Demo window of the pixel components (only for development).

Open it from the QGIS Python console:

    from urban_analysis_plugin.urban_analysis.ui import demo
    demo.show()

Students never see it: there is no menu entry.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSlider,
    QVBoxLayout,
)

from ..theme import load_fonts, panel_stylesheet, set_role
from . import pixel_motion as pm
from .widgets.pixel_button import PixelButton

_window = None  # keep the window alive while it is open

STATE_LABELS = (
    ("normal", "Normal"),
    ("hover", "Hover"),
    ("pressed", "Gedrückt"),
    ("disabled", "Deaktiviert"),
)


class PixelDemo(QDialog):
    """All pixel components in all states, plus a frame-time slider."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UrbanAnalysisPixelDemo")
        self.setWindowTitle("Urban Analysis – Pixel-Demo")
        self.setStyleSheet(panel_stylesheet(load_fonts()))
        layout = QVBoxLayout(self)

        title = QLabel("Pixel-Demo")
        set_role(title, "heading")
        layout.addWidget(title)
        hint = QLabel("Feste Zustände zum Vergleichen; die unterste Zeile ist live zum Klicken.")
        set_role(hint, "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        grid = QGridLayout()
        self.buttons = []
        for column, (state, label) in enumerate(STATE_LABELS):
            grid.addWidget(QLabel(label), 0, column, Qt.AlignmentFlag.AlignCenter)
            for row, variant in enumerate(("primary", "secondary"), start=1):
                button = PixelButton("Weiter" if variant == "primary" else "Zurück", variant)
                button.preview_state(state)
                button.setEnabled(state != "disabled")
                grid.addWidget(button, row, column, Qt.AlignmentFlag.AlignCenter)
                self.buttons.append(button)
        layout.addLayout(grid)

        live = QHBoxLayout()
        self.live_secondary = PixelButton("Zurück", "secondary")
        self.live_primary = PixelButton("Bestätigen", "primary")
        self.clicks = QLabel("Klicks: 0")
        self.live_primary.confirmed.connect(self._count)
        live.addWidget(self.live_secondary)
        live.addStretch()
        live.addWidget(self.clicks)
        live.addWidget(self.live_primary)
        layout.addLayout(live)

        speed = QHBoxLayout()
        speed.addWidget(QLabel("Frame-Dauer"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(20, 200)
        self.slider.setValue(pm.FRAME_MS)
        self.slider_value = QLabel(f"{pm.FRAME_MS} ms")
        self.slider.valueChanged.connect(self._set_frame_ms)
        speed.addWidget(self.slider, 1)
        speed.addWidget(self.slider_value)
        layout.addLayout(speed)

        inputs = QGridLayout()
        inputs.addWidget(QLabel("Eingabefeld"), 0, 0)
        inputs.addWidget(QLineEdit("Siedlungsstruktur"), 0, 1)
        combo = QComboBox()
        combo.addItems(["Objektart", "Status", "Jahr"])
        inputs.addWidget(QLabel("Auswahl"), 1, 0)
        inputs.addWidget(combo, 1, 1)
        check = QCheckBox("Häkchen an")
        check.setChecked(True)
        inputs.addWidget(check, 2, 0)
        inputs.addWidget(QCheckBox("Häkchen aus"), 2, 1)
        radio = QRadioButton("Auswahl an")
        radio.setChecked(True)
        inputs.addWidget(radio, 3, 0)
        inputs.addWidget(QRadioButton("Auswahl aus"), 3, 1)
        layout.addLayout(inputs)
        layout.addStretch()

    def _count(self):
        number = int(self.clicks.text().split(": ")[1]) + 1
        self.clicks.setText(f"Klicks: {number}")

    def _set_frame_ms(self, value):
        self.slider_value.setText(f"{value} ms")
        for button in self.findChildren(PixelButton):
            button._timer.setInterval(value)


def show(parent=None):
    """Open (or bring to front) the demo window."""
    global _window
    if _window is None:
        _window = PixelDemo(parent)
    _window.show()
    _window.raise_()
    return _window
