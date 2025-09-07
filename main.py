import sys
import re
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QVBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QDialog,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QSpinBox,
)
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
import paho.mqtt.client as mqtt
try:
    import winsound
except Exception:
    winsound = None


def build_tray_icon() -> QIcon:
    # Crée un petit icône 16x16 simple (cercle vert) pour la zone de notification
    pix = QPixmap(16, 16)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(0, 200, 0))
    p.setPen(Qt.black)
    p.drawEllipse(1, 1, 14, 14)
    p.end()
    return QIcon(pix)


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres MQTT")
        form = QFormLayout(self)
        self.broker_url = QLineEdit(self)
        self.topic = QLineEdit(self)
        self.username = QLineEdit(self)
        self.password = QLineEdit(self)
        self.password.setEchoMode(QLineEdit.Password)
        self.font_size = QSpinBox(self)
        self.font_size.setRange(10, 200)
        self.font_color = QLineEdit(self)
        # Charger valeurs existantes
        self.broker_url.setText(settings.value("broker_url", ""))
        self.topic.setText(settings.value("mqtt_topic", ""))
        self.username.setText(settings.value("mqtt_user", ""))
        self.password.setText(settings.value("mqtt_password", ""))
        self.font_size.setValue(int(settings.value("font_size", 40)))
        self.font_color.setText(settings.value("font_color", "#FFFFFF"))
        form.addRow("Serveur (mqtt://host:1883)", self.broker_url)
        form.addRow("Topic", self.topic)
        form.addRow("Utilisateur", self.username)
        form.addRow("Mot de passe", self.password)
        form.addRow("Taille police", self.font_size)
        form.addRow("Couleur (#RRGGBB)", self.font_color)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return {
            "broker_url": self.broker_url.text().strip(),
            "mqtt_topic": self.topic.text().strip(),
            "mqtt_user": self.username.text().strip(),
            "mqtt_password": self.password.text(),
            "font_size": str(self.font_size.value()),
            "font_color": self.font_color.text().strip() or "#FFFFFF",
        }


class TimerWindow(QWidget):
    mqtt_timer_received = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.timer_label = QLabel("00:00:00", self)
        self.timer_label.setFont(QFont("Arial", 40, QFont.Bold))
        self.timer_label.setStyleSheet("color: #FFFFFF; background: transparent;")

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self.timer_label, alignment=Qt.AlignCenter)
        self.setLayout(layout)

        self.resize(300, 100)
        self.remaining_seconds = 0

        # QSettings
        self.settings = QSettings("timerMQTT", "App")
        pos_x = self.settings.value("pos_x")
        pos_y = self.settings.value("pos_y")
        if pos_x is not None and pos_y is not None:
            try:
                self.move(int(pos_x), int(pos_y))
            except Exception:
                pass
        # Apparence depuis settings
        self.apply_appearance_from_settings()

        # Drag
        self._dragging = False
        self._drag_pos = None
        self.setCursor(Qt.OpenHandCursor)
        self.timer_label.setCursor(Qt.OpenHandCursor)

        # MQTT
        self.mqtt_client = None
        self._last_received_values = []
        self.mqtt_timer_received.connect(self.set_timer)

        # Décrémentation locale
        self.qtimer = QTimer(self)
        self.qtimer.timeout.connect(self.decrement_timer)
        self.qtimer.start(1000)

        # Alarme sonore
        self.alarm_active = False
        self.alarm_timer = QTimer(self)
        self.alarm_timer.setInterval(1200)
        self.alarm_timer.timeout.connect(self._beep)

        # Systray
        self.init_systray()
        if self.settings.value("broker_url") and self.settings.value("mqtt_topic"):
            self.connect_mqtt()

        # Drag via label
        self.timer_label.mousePressEvent = self._proxy_mousePressEvent
        self.timer_label.mouseMoveEvent = self._proxy_mouseMoveEvent
        self.timer_label.mouseReleaseEvent = self._proxy_mouseReleaseEvent

    # --- Timer ---
    def set_timer(self, seconds):
        prev = self.remaining_seconds
        self.remaining_seconds = max(0, int(seconds))
        self.update_label()
        if self.remaining_seconds == 0 and prev != 0:
            self.start_alarm()
        elif self.remaining_seconds > 0 and self.alarm_active:
            self.stop_alarm()

    def decrement_timer(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.update_label()
            if self.remaining_seconds == 0:
                self.start_alarm()

    def update_label(self):
        h = self.remaining_seconds // 3600
        m = (self.remaining_seconds % 3600) // 60
        s = self.remaining_seconds % 60
        self.timer_label.setText(f"{h:02}:{m:02}:{s:02}")

    def apply_appearance_from_settings(self):
        try:
            size = int(self.settings.value("font_size", 40))
        except Exception:
            size = 40
        color = self.settings.value("font_color", "#FFFFFF")
        f = self.timer_label.font()
        f.setPointSize(int(size))
        f.setBold(True)
        self.timer_label.setFont(f)
        # Sanitize color (fallback white)
        if not isinstance(color, str) or not color:
            color = "#FFFFFF"
        self.timer_label.setStyleSheet(f"color: {color}; background: transparent;")

    # --- Drag ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Un clic arrête l'alarme si active
            if self.alarm_active:
                self.stop_alarm()
            self._dragging = True
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            self.timer_label.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            # Sauvegarde position courante
            try:
                self.settings.setValue("pos_x", self.x())
                self.settings.setValue("pos_y", self.y())
            except Exception:
                pass
            self.setCursor(Qt.OpenHandCursor)
            self.timer_label.setCursor(Qt.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # Proxy des événements pour le label
    def _proxy_mousePressEvent(self, event):
        self.mousePressEvent(event)

    def _proxy_mouseMoveEvent(self, event):
        self.mouseMoveEvent(event)

    def _proxy_mouseReleaseEvent(self, event):
        self.mouseReleaseEvent(event)

    # --- Systray et actions ---
    def init_systray(self):
        self.tray_icon = QSystemTrayIcon(build_tray_icon())
        self.tray_icon.setToolTip("TimerMQTT")
        menu = QMenu()
        settings_action = QAction("Paramètres…", self)
        settings_action.triggered.connect(self.open_settings)
        center_action = QAction("Recentrer l'affichage", self)
        center_action.triggered.connect(self.center_on_screen)
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(settings_action)
        menu.addAction(center_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
            self.settings.setValue("pos_x", self.x())
            self.settings.setValue("pos_y", self.y())

    def quit_app(self):
        try:
            if self.mqtt_client is not None:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
        except Exception:
            pass
        QApplication.instance().quit()

    # --- Paramètres et MQTT ---
    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_() == QDialog.Accepted:
            vals = dlg.values()
            for k, v in vals.items():
                self.settings.setValue(k, v)
            self.apply_appearance_from_settings()
            self.connect_mqtt()

    def parse_broker_url(self, url: str):
        # Supporte mqtt://host:1883, tcp://host:1883, host:1883, host
        url = url.strip()
        url = re.sub(r'^(mqtt|tcp)://', '', url, flags=re.IGNORECASE)
        if ':' in url:
            host, port = url.split(':', 1)
            try:
                port = int(port)
            except ValueError:
                port = 1883
        else:
            host, port = url, 1883
        return host or 'localhost', port

    def connect_mqtt(self):
        # Nettoyer ancien client
        try:
            if self.mqtt_client is not None:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
        except Exception:
            pass

        broker_url = self.settings.value("broker_url", "")
        topic = self.settings.value("mqtt_topic", "")
        user = self.settings.value("mqtt_user", "")
        pwd = self.settings.value("mqtt_password", "")
        if not broker_url or not topic:
            return
        host, port = self.parse_broker_url(broker_url)

        self.mqtt_client = mqtt.Client()
        if user:
            self.mqtt_client.username_pw_set(user, pwd)
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        try:
            self.mqtt_client.connect(host, port, keepalive=30)
            self.mqtt_client.loop_start()
        except Exception as e:
            self.tray_icon.showMessage("MQTT", f"Connexion échouée: {e}")

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            topic = self.settings.value("mqtt_topic", "")
            try:
                if topic:
                    client.subscribe(topic)
                    self.tray_icon.showMessage("MQTT", f"Connecté et abonné à {topic}")
            except Exception as e:
                self.tray_icon.showMessage("MQTT", f"Abonnement échoué: {e}")
        else:
            self.tray_icon.showMessage("MQTT", f"Connexion refusée (rc={rc})")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        pass

    def parse_time_str(self, payload: str) -> int:
        # Format attendu HH:MM:SS
        s = payload.strip()
        m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", s)
        if not m:
            return -1
        h = int(m.group(1))
        mi = int(m.group(2))
        se = int(m.group(3))
        return h * 3600 + mi * 60 + se

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            text = msg.payload.decode('utf-8', errors='ignore')
        except Exception:
            return
        seconds = self.parse_time_str(text)
        if seconds < 0:
            return
        # Détection 3 fois identique
        self._last_received_values.append(seconds)
        if len(self._last_received_values) > 3:
            self._last_received_values.pop(0)
        if len(self._last_received_values) == 3 and len(set(self._last_received_values)) == 1:
            self.mqtt_timer_received.emit(0)
        else:
            self.mqtt_timer_received.emit(seconds)

    # --- Alarme sonore ---
    def start_alarm(self):
        if not self.alarm_active:
            self.alarm_active = True
            self.alarm_timer.start()

    def stop_alarm(self):
        if self.alarm_active:
            self.alarm_active = False
            self.alarm_timer.stop()

    def _beep(self):
        if winsound is not None:
            try:
                winsound.Beep(1000, 200)  # fréquence 1000 Hz, 200 ms
            except Exception:
                try:
                    winsound.MessageBeep()
                except Exception:
                    pass
        # Sinon, pas de fallback cross-plateforme requis (app ciblée Windows)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TimerWindow()
    window.show()
    sys.exit(app.exec_())
