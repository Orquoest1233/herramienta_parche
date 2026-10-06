# parche_ui.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QSpinBox, QFrame, QComboBox
from PyQt5.QtCore import Qt, QPoint, QTimer

class DragPad(QFrame):
#Pad y estilos abajo hasta la linea 15
    IDLE_STYLE = (
        "background-color: #222; border: 1px solid #444; border-radius: 5px;"
    )
    ACTIVE_STYLE = (
        "background-color: #1a1a2a; border: 1px solid #6688cc; border-radius: 5px;"
    )

    def __init__(self, parent=None, callback=None, release_callback=None):
        super().__init__(parent)
        self.callback, self.release_callback = callback, release_callback
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.setMinimumSize(200, 100)


        self.setStyleSheet(self.IDLE_STYLE) # estilos del pad
        self.setCursor(Qt.OpenHandCursor)

        self.last_pos = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = event.pos()

            # 3. Feedback visual al hacer clic: cambia el color al estado ACTIVO[cite: 1]
            self.setStyleSheet(self.ACTIVE_STYLE)
            
            # UX: El cursor se cierra indicando que estás arrastrando
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        # 4. Restaura el color y el cursor original al soltar el clic
        self.setStyleSheet(self.IDLE_STYLE)
        self.setCursor(Qt.OpenHandCursor)

        if event.buttons() & Qt.LeftButton:
            delta = event.pos() - self.last_pos
            self.last_pos = event.pos()
            if self.callback:
                self.callback(delta.x(), delta.y())

    def mouseReleaseEvent(self, event):
        if self.release_callback:
            self.release_callback()

class ParcheDialog(QDialog):
    def __init__(self, parent=None, update_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Herramienta Parche")
        self.update_callback = update_callback
        
        # Timer para render final con debounce
        self.timer_final = QTimer()
        self.timer_final.setSingleShot(True)
        self.timer_final.timeout.connect(self.solicitar_render_final)
        
        # Flag para evitar que las señales disparen durante la construcción del UI
        self._ui_lista = False
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Área de Arrastre:"))
        layout.addWidget(DragPad(self, self.manejar_arrastre, self.solicitar_render_final))
        
        layout.addWidget(QLabel("Calidad (Fluidez):"))
        self.combo_calidad = QComboBox()
        self.combo_calidad.addItems(["Baja", "Media", "Alta"])
        self.combo_calidad.setCurrentIndex(0)
        layout.addWidget(self.combo_calidad)

        layout.addWidget(QLabel("Offset X / Y:"))
        self.spin_x, self.spin_y = QSpinBox(), QSpinBox()
        for s in [self.spin_x, self.spin_y]:
            s.setRange(-5000, 5000)
            s.valueChanged.connect(self._on_value_changed)
            layout.addWidget(s)

        layout.addWidget(QLabel("Rotación (Grados):"))
        self.spin_rotacion = QSpinBox()
        self.spin_rotacion.setRange(-180, 180)
        self.spin_rotacion.setValue(0)
        self.spin_rotacion.setSuffix(" °")
        self.spin_rotacion.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.spin_rotacion)

        self.btn_reset = QPushButton("Resetear Transformación")
        self.btn_reset.setStyleSheet("background-color: #442222;")
        self.btn_reset.clicked.connect(self.reset_transformacion)
        layout.addWidget(self.btn_reset)
            
        layout.addWidget(QLabel("Suavizado de Bordes (Feather):"))
        self.spin_feather = QSpinBox()
        self.spin_feather.setRange(0, 100)
        self.spin_feather.setValue(0)
        self.spin_feather.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.spin_feather)

        layout.addWidget(QLabel("Tipo de Suavizado:"))
        self.combo_blur = QComboBox()
        self.combo_blur.addItems(["Box (Rápido)", "Gaussian (Suave)"])
        self.combo_blur.currentIndexChanged.connect(self._on_value_changed)
        layout.addWidget(self.combo_blur)
        
        self.btn_confirmar = QPushButton("Aplicar Parche")
        self.btn_confirmar.setStyleSheet("background-color: #224422; font-weight: bold; height: 30px;")
        self.btn_confirmar.clicked.connect(self.accept)
        layout.addWidget(self.btn_confirmar)
        self.setLayout(layout)
        
        # UI lista: a partir de aquí las señales pueden disparar callbacks
        self._ui_lista = True

    def _on_value_changed(self):
        """Preview rápida + render final con debounce."""
        if not self._ui_lista:
            return
        self.solicitar_previa(2)
        self.timer_final.start(250)

    def reset_transformacion(self):
        for s in [self.spin_x, self.spin_y, self.spin_rotacion]:
            s.blockSignals(True)
            s.setValue(0)
            s.blockSignals(False)
        self.solicitar_previa(1)

    def manejar_arrastre(self, dx, dy):
        # Sujetar valores a los límites del spinbox
        nuevo_x = max(self.spin_x.minimum(), min(self.spin_x.maximum(), self.spin_x.value() + dx))
        nuevo_y = max(self.spin_y.minimum(), min(self.spin_y.maximum(), self.spin_y.value() + dy))
        
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.spin_x.setValue(nuevo_x)
        self.spin_y.setValue(nuevo_y)
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)
        
        skip = {0: 4, 1: 2, 2: 1}[self.combo_calidad.currentIndex()]
        self.solicitar_previa(skip)
        self.timer_final.start(300)

    def solicitar_previa(self, skip=1):
        if self.update_callback:
            self.update_callback(
                self.spin_x.value(), self.spin_y.value(),
                self.spin_feather.value(), skip,
                self.combo_blur.currentIndex(),
                self.spin_rotacion.value()
            )

    def solicitar_render_final(self):
        self.solicitar_previa(1)