"""Dialog windows for SSH Manager"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QComboBox, QCheckBox, QPushButton,
    QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QTabWidget, QWidget, QMessageBox,
    QHeaderView, QColorDialog, QFontComboBox, QGridLayout, QApplication
)
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import Qt

from .models import (
    Connection, Folder, SSHConfig, SerialConfig,
    AppSettings, DEFAULT_TERMINAL_SETTINGS, DEFAULT_LOGGING_SETTINGS
)
from .sessions import list_serial_ports


# Security presets
SECURITY_PRESETS = {
    "Modern (default)": {"ciphers": "", "kex": "", "hostkeys": "", "macs": ""},
    "Compatible": {
        "ciphers": "aes128-ctr,aes256-ctr,aes128-gcm@openssh.com,aes256-gcm@openssh.com,aes128-cbc,aes256-cbc",
        "kex": "curve25519-sha256,diffie-hellman-group16-sha512,diffie-hellman-group14-sha256,diffie-hellman-group14-sha1",
        "hostkeys": "ssh-ed25519,rsa-sha2-512,rsa-sha2-256,ssh-rsa",
        "macs": "hmac-sha2-256,hmac-sha2-512,hmac-sha1",
    },
    "Legacy (old devices)": {
        "ciphers": "aes128-ctr,aes256-ctr,aes128-cbc,aes256-cbc,3des-cbc",
        "kex": "curve25519-sha256,diffie-hellman-group14-sha256,diffie-hellman-group14-sha1,diffie-hellman-group1-sha1,diffie-hellman-group-exchange-sha1",
        "hostkeys": "ssh-ed25519,rsa-sha2-256,ssh-rsa,ssh-dss",
        "macs": "hmac-sha2-256,hmac-sha2-512,hmac-sha1,hmac-md5",
    },
    "Custom": None,
}

# Parity / stopbits / flow maps for serial config
PARITY_CODES = ["N", "E", "O", "M", "S"]
STOPBITS_VALS = [1.0, 1.5, 2.0]
FLOW_VALS = ["none", "xonxoff", "rtscts"]


def _make_dialog_buttons(parent, on_ok, on_cancel):
    """Create OK/Cancel buttons WITHOUT Qt standard icons (fixes rendering on Arch/Wayland)"""
    from PyQt5.QtGui import QIcon
    layout = QHBoxLayout()
    layout.addStretch()

    cancel_btn = QPushButton("Cancel")
    cancel_btn.setIcon(QIcon())          # force no icon (platform theme adds them)
    cancel_btn.clicked.connect(on_cancel)
    layout.addWidget(cancel_btn)

    ok_btn = QPushButton("OK")
    ok_btn.setIcon(QIcon())              # force no icon
    ok_btn.setDefault(True)
    ok_btn.clicked.connect(on_ok)
    layout.addWidget(ok_btn)

    return layout


# --- Shared terminal settings widget builder ---

class TerminalSettingsWidget(QWidget):
    """Reusable widget for terminal color/font/highlight settings"""

    def __init__(self, border_color="#45475a", accent_color="#89b4fa",
                 hint_color="#6c7086", parent=None):
        super().__init__(parent)
        self._border_color = border_color
        self._accent_color = accent_color
        self._hint_color = hint_color
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Colors
        colors_label = QLabel("Colors")
        colors_label.setStyleSheet(f"font-weight: bold; color: {self._accent_color};")
        layout.addWidget(colors_label)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 1)
        grid.setColumnMinimumWidth(1, 120)

        self.bg_edit, self.bg_preview = self._add_color_row(grid, 0, "Background:", "#1e1e2e")
        self.fg_edit, self.fg_preview = self._add_color_row(grid, 1, "Text:", "#cdd6f4")
        self.cursor_edit, self.cursor_preview = self._add_color_row(grid, 2, "Cursor:", "#f5e0dc")
        layout.addLayout(grid)

        # Font
        font_label = QLabel("Font")
        font_label.setStyleSheet(f"font-weight: bold; color: {self._accent_color};")
        layout.addWidget(font_label)

        font_form = QFormLayout()
        font_form.setSpacing(6)
        self.font_family = QFontComboBox()
        self.font_family.setFontFilters(QFontComboBox.MonospacedFonts)
        font_form.addRow("Family:", self.font_family)
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 32)
        self.font_size.setValue(11)
        font_form.addRow("Size:", self.font_size)
        layout.addLayout(font_form)

        # Syntax highlighting
        hl_label = QLabel("Syntax Highlighting")
        hl_label.setStyleSheet(f"font-weight: bold; color: {self._accent_color};")
        layout.addWidget(hl_label)
        self.syntax_enabled = QCheckBox("Enable command syntax highlighting")
        self.syntax_enabled.setChecked(True)
        layout.addWidget(self.syntax_enabled)
        hint = QLabel("Highlights network commands: show, interface, ip, vlan, configure, etc.")
        hint.setStyleSheet(f"color: {self._hint_color}; font-size: 11px;")
        layout.addWidget(hint)

        layout.addStretch()

    def _add_color_row(self, grid, row, label_text, default_color):
        grid.addWidget(QLabel(label_text), row, 0)

        edit = QLineEdit(default_color)
        edit.setMinimumWidth(100)
        grid.addWidget(edit, row, 1)

        btn = QPushButton("Choose")
        btn.setMinimumWidth(70)
        btn.clicked.connect(lambda: self._choose_color(edit))
        grid.addWidget(btn, row, 2)

        preview = QLabel()
        preview.setFixedSize(24, 24)
        preview.setStyleSheet(f"border: 1px solid {self._border_color}; border-radius: 4px;")
        grid.addWidget(preview, row, 3, Qt.AlignLeft)

        edit.textChanged.connect(lambda: self._update_preview(edit, preview))
        return edit, preview

    def _choose_color(self, edit: QLineEdit):
        color = QColorDialog.getColor(QColor(edit.text()), self, "Choose Color")
        if color.isValid():
            edit.setText(color.name())

    def _update_preview(self, edit: QLineEdit, preview: QLabel):
        c = edit.text()
        if QColor(c).isValid():
            preview.setStyleSheet(
                f"background-color: {c}; border: 1px solid {self._border_color}; border-radius: 4px;"
            )

    def load_settings(self, cfg: dict):
        self.bg_edit.setText(cfg.get('bg_color', '#1e1e2e'))
        self.fg_edit.setText(cfg.get('fg_color', '#cdd6f4'))
        self.cursor_edit.setText(cfg.get('cursor_color', '#f5e0dc'))
        self.font_size.setValue(cfg.get('font_size', 11))
        self.syntax_enabled.setChecked(cfg.get('syntax_highlight', True))
        family = cfg.get('font_family', '')
        if family:
            self.font_family.setCurrentFont(QFont(family))
        self.update_all_previews()

    def get_settings(self) -> dict:
        return {
            'bg_color': self.bg_edit.text(),
            'fg_color': self.fg_edit.text(),
            'cursor_color': self.cursor_edit.text(),
            'font_family': self.font_family.currentFont().family(),
            'font_size': self.font_size.value(),
            'syntax_highlight': self.syntax_enabled.isChecked(),
        }

    def update_all_previews(self):
        for edit, preview in [(self.bg_edit, self.bg_preview),
                              (self.fg_edit, self.fg_preview),
                              (self.cursor_edit, self.cursor_preview)]:
            self._update_preview(edit, preview)

    def reset_defaults(self):
        self.load_settings(DEFAULT_TERMINAL_SETTINGS)


# --- Dialogs ---

class ConnectionDialog(QDialog):
    """Dialog for creating/editing connections"""

    def __init__(self, connection: Connection = None, parent=None):
        super().__init__(parent)
        self.connection = connection or Connection()
        self.is_new = connection is None

        self.setWindowTitle("New Connection" if self.is_new else "Edit Connection")
        self.setMinimumSize(520, 420)
        self.setModal(True)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # Type
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["SSH", "Serial/TTY"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        layout.addLayout(type_row)

        # Tabs
        self.tabs = QTabWidget()
        self._build_ssh_tab()
        self._build_security_tab()
        self._build_serial_tab()
        self._build_terminal_tab()
        layout.addWidget(self.tabs)

        # Buttons (no icons)
        layout.addLayout(_make_dialog_buttons(self, self._save_and_accept, self.reject))

    def _build_ssh_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        self.ssh_host = QLineEdit()
        self.ssh_host.setPlaceholderText("192.168.1.1 or hostname")
        form.addRow("Host:", self.ssh_host)

        self.ssh_port = QSpinBox()
        self.ssh_port.setRange(1, 65535)
        self.ssh_port.setValue(22)
        form.addRow("Port:", self.ssh_port)

        self.ssh_username = QLineEdit()
        form.addRow("Username:", self.ssh_username)

        self.ssh_password = QLineEdit()
        self.ssh_password.setEchoMode(QLineEdit.Password)
        form.addRow("Password:", self.ssh_password)

        key_row = QHBoxLayout()
        self.ssh_keyfile = QLineEdit()
        self.ssh_keyfile.setPlaceholderText("Optional: path to private key")
        key_row.addWidget(self.ssh_keyfile)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_keyfile)
        key_row.addWidget(browse_btn)
        form.addRow("Key File:", key_row)

        self.tabs.addTab(w, "SSH")

    def _build_security_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(4)
        layout.setContentsMargins(12, 8, 12, 8)

        preset_label = QLabel("Security Preset")
        preset_label.setStyleSheet("font-weight: bold; color: #89b4fa;")
        layout.addWidget(preset_label)

        self.security_preset = QComboBox()
        self.security_preset.addItems(list(SECURITY_PRESETS.keys()))
        layout.addWidget(self.security_preset)

        hint = QLabel(
            "Modern: secure only · Compatible: most devices · "
            "Legacy: old Cisco/Huawei · Custom: manual"
        )
        hint.setStyleSheet("color: #6c7086; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addSpacing(2)

        # Algorithm fields
        self._algo_fields = {}
        algo_defs = [
            ("ciphers", "Ciphers", "e.g. aes128-ctr,aes256-ctr"),
            ("kex", "Key Exchange", "e.g. diffie-hellman-group14-sha1"),
            ("hostkeys", "Host Key Algs", "e.g. ssh-rsa,ssh-ed25519"),
            ("macs", "MAC Algs", "e.g. hmac-sha2-256,hmac-sha1"),
        ]
        for name, label_text, placeholder in algo_defs:
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-weight: bold; color: #89b4fa; margin-top: 2px;")
            layout.addWidget(lbl)
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            layout.addWidget(edit)
            self._algo_fields[name] = edit

        layout.addStretch()
        self.tabs.addTab(w, "Security")

        # Connect and trigger initial state
        self.security_preset.currentTextChanged.connect(self._on_security_preset_changed)
        self._on_security_preset_changed(self.security_preset.currentText())

    def _build_serial_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        port_row = QHBoxLayout()
        self.serial_port = QComboBox()
        self.serial_port.setEditable(True)
        self._refresh_serial_ports()
        port_row.addWidget(self.serial_port)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_serial_ports)
        port_row.addWidget(refresh_btn)
        form.addRow("Port:", port_row)

        self.serial_baud = QComboBox()
        self.serial_baud.addItems(["300", "1200", "2400", "4800", "9600",
                                   "19200", "38400", "57600", "115200"])
        self.serial_baud.setCurrentText("9600")
        form.addRow("Baud Rate:", self.serial_baud)

        self.serial_databits = QComboBox()
        self.serial_databits.addItems(["5", "6", "7", "8"])
        self.serial_databits.setCurrentText("8")
        form.addRow("Data Bits:", self.serial_databits)

        self.serial_parity = QComboBox()
        self.serial_parity.addItems(["None", "Even", "Odd", "Mark", "Space"])
        form.addRow("Parity:", self.serial_parity)

        self.serial_stopbits = QComboBox()
        self.serial_stopbits.addItems(["1", "1.5", "2"])
        form.addRow("Stop Bits:", self.serial_stopbits)

        self.serial_flow = QComboBox()
        self.serial_flow.addItems(["None", "XON/XOFF", "RTS/CTS"])
        form.addRow("Flow Control:", self.serial_flow)

        self.tabs.addTab(w, "Serial")

    def _build_terminal_tab(self):
        self.term_widget = TerminalSettingsWidget()
        self.tabs.addTab(self.term_widget, "Terminal")

    # --- Actions ---

    def _on_type_changed(self, index):
        self.tabs.setCurrentIndex(0 if index == 0 else 2)

    def _on_security_preset_changed(self, preset_name):
        preset = SECURITY_PRESETS.get(preset_name)
        is_custom = preset is None

        if is_custom:
            for key, edit in self._algo_fields.items():
                edit.setReadOnly(False)
                edit.setFocusPolicy(Qt.StrongFocus)
                edit.setToolTip("")
                if not edit.text() or edit.text() == "(system defaults)":
                    edit.clear()
        else:
            for key, edit in self._algo_fields.items():
                val = preset[key]
                if val:
                    # Show readable text, tooltip has full list
                    parts = val.split(",")
                    short = ", ".join(parts[:3])
                    if len(parts) > 3:
                        short += f"  (+{len(parts) - 3} more)"
                    edit.setText(short)
                    edit.setToolTip(val.replace(",", ",  "))
                else:
                    edit.setText("(system defaults)")
                    edit.setToolTip("Using paramiko defaults — strongest available algorithms")
                edit.setReadOnly(True)
                edit.setFocusPolicy(Qt.NoFocus)

    def _browse_keyfile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Private Key", "", "All Files (*)")
        if path:
            self.ssh_keyfile.setText(path)

    def _refresh_serial_ports(self):
        current = self.serial_port.currentText()
        self.serial_port.clear()
        for port in list_serial_ports():
            self.serial_port.addItem(f"{port['device']} - {port['description']}", port['device'])
        if current:
            idx = self.serial_port.findData(current)
            if idx >= 0:
                self.serial_port.setCurrentIndex(idx)
            else:
                self.serial_port.setEditText(current)

    def _load_data(self):
        self.name_edit.setText(self.connection.name)

        if self.connection.conn_type == "serial":
            self.type_combo.setCurrentIndex(1)
            self.tabs.setCurrentIndex(2)
        else:
            self.type_combo.setCurrentIndex(0)
            self.tabs.setCurrentIndex(0)

        # SSH
        ssh = self.connection.get_ssh_config()
        self.ssh_host.setText(ssh.host)
        self.ssh_port.setValue(ssh.port)
        self.ssh_username.setText(ssh.username)
        self.ssh_password.setText(ssh.password)
        self.ssh_keyfile.setText(ssh.key_file)

        # Security
        ssh_cfg = self.connection.ssh_config or {}
        for key in ('ciphers', 'kex', 'hostkeys', 'macs'):
            self._algo_fields[key].setText(ssh_cfg.get(key, ''))
        preset = ssh_cfg.get('security_preset', 'Modern (default)')
        idx = self.security_preset.findText(preset)
        if idx >= 0:
            self.security_preset.setCurrentIndex(idx)

        # Terminal
        term_cfg = ssh_cfg.get('terminal', {})
        self.term_widget.load_settings(term_cfg)

        # Serial
        ser = self.connection.get_serial_config()
        if ser.port:
            idx = self.serial_port.findData(ser.port)
            if idx >= 0:
                self.serial_port.setCurrentIndex(idx)
            else:
                self.serial_port.setEditText(ser.port)
        self.serial_baud.setCurrentText(str(ser.baudrate))
        self.serial_databits.setCurrentText(str(ser.bytesize))
        self.serial_parity.setCurrentIndex({"N": 0, "E": 1, "O": 2, "M": 3, "S": 4}.get(ser.parity, 0))
        self.serial_stopbits.setCurrentIndex({1.0: 0, 1.5: 1, 2.0: 2}.get(ser.stopbits, 0))
        self.serial_flow.setCurrentIndex({"none": 0, "xonxoff": 1, "rtscts": 2}.get(ser.flow_control, 0))

    def _save_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name is required")
            return

        self.connection.name = name
        self.connection.conn_type = "serial" if self.type_combo.currentIndex() == 1 else "ssh"

        def _algo_val(key):
            """Get real algorithm value — from preset or from field if custom"""
            preset_name = self.security_preset.currentText()
            preset = SECURITY_PRESETS.get(preset_name)
            if preset is not None:
                return preset[key]
            val = self._algo_fields[key].text().strip()
            return "" if val.startswith("(") else val

        # SSH config
        self.connection.ssh_config = {
            "host": self.ssh_host.text(),
            "port": self.ssh_port.value(),
            "username": self.ssh_username.text(),
            "password": self.ssh_password.text(),
            "key_file": self.ssh_keyfile.text(),
            "security_preset": self.security_preset.currentText(),
            "ciphers": _algo_val("ciphers"),
            "kex": _algo_val("kex"),
            "hostkeys": _algo_val("hostkeys"),
            "macs": _algo_val("macs"),
            "terminal": self.term_widget.get_settings(),
        }

        # Serial config
        port = self.serial_port.currentData() or self.serial_port.currentText().split(" - ")[0]
        self.connection.serial_config = {
            "port": port,
            "baudrate": int(self.serial_baud.currentText()),
            "bytesize": int(self.serial_databits.currentText()),
            "parity": PARITY_CODES[self.serial_parity.currentIndex()],
            "stopbits": STOPBITS_VALS[self.serial_stopbits.currentIndex()],
            "flow_control": FLOW_VALS[self.serial_flow.currentIndex()],
        }

        self.accept()

    def get_connection(self) -> Connection:
        return self.connection


class FolderDialog(QDialog):
    """Dialog for creating/editing folders"""

    def __init__(self, folder: Folder = None, parent=None):
        super().__init__(parent)
        self.folder = folder or Folder()
        self.is_new = folder is None

        self.setWindowTitle("New Folder" if self.is_new else "Edit Folder")
        self.setMinimumWidth(300)
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.folder.name)
        form.addRow("Name:", self.name_edit)
        layout.addLayout(form)
        layout.addLayout(_make_dialog_buttons(self, self._save_and_accept, self.reject))

    def _save_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name is required")
            return
        self.folder.name = name
        self.accept()

    def get_folder(self) -> Folder:
        return self.folder


class SerialPortsDialog(QDialog):
    """Dialog showing available serial ports"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Available Serial Ports")
        self.setMinimumSize(520, 250)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Port", "Description", "Hardware ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._refresh()

    def _refresh(self):
        self.table.setRowCount(0)
        for port in list_serial_ports():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(port['device']))
            self.table.setItem(row, 1, QTableWidgetItem(port['description']))
            self.table.setItem(row, 2, QTableWidgetItem(port['hwid']))


class SettingsDialog(QDialog):
    """Application settings dialog"""

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.original_theme = settings.theme

        self.setWindowTitle("Settings")
        self.setMinimumSize(520, 420)
        self.setModal(True)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- Appearance tab ---
        appearance = QWidget()
        app_layout = QVBoxLayout(appearance)

        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout(theme_group)
        self.theme_dark = QCheckBox("Dark theme (Catppuccin Mocha)")
        self.theme_dark.setChecked(True)
        theme_layout.addWidget(self.theme_dark)
        self.theme_light = QCheckBox("Light theme")
        theme_layout.addWidget(self.theme_light)

        # Radio-button behavior
        self.theme_dark.toggled.connect(lambda on: self.theme_light.setChecked(not on) if on else None)
        self.theme_light.toggled.connect(lambda on: self.theme_dark.setChecked(not on) if on else None)

        hint = QLabel("Note: Theme changes take effect after restart.")
        hint.setStyleSheet("color: gray; font-style: italic;")
        theme_layout.addWidget(hint)
        app_layout.addWidget(theme_group)
        app_layout.addStretch()
        self.tabs.addTab(appearance, "Appearance")

        # --- Default Terminal tab ---
        terminal = QWidget()
        term_layout = QVBoxLayout(terminal)
        hint2 = QLabel("These settings will be applied to all new connections by default.")
        hint2.setWordWrap(True)
        term_layout.addWidget(hint2)

        self.term_widget = TerminalSettingsWidget()
        term_layout.addWidget(self.term_widget)

        reset_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.term_widget.reset_defaults)
        reset_row.addWidget(reset_btn)
        reset_row.addStretch()
        term_layout.addLayout(reset_row)

        self.tabs.addTab(terminal, "Default Terminal")

        # --- Logging tab ---
        logging_w = QWidget()
        log_layout = QVBoxLayout(logging_w)

        enable_group = QGroupBox("Session Logging")
        enable_gl = QVBoxLayout(enable_group)
        self.log_enabled = QCheckBox("Enable session logging")
        self.log_enabled.toggled.connect(self._on_logging_toggled)
        enable_gl.addWidget(self.log_enabled)
        log_hint = QLabel("When enabled, all terminal output will be saved to log files.")
        log_hint.setStyleSheet("color: gray; font-style: italic;")
        enable_gl.addWidget(log_hint)
        log_layout.addWidget(enable_group)

        dir_group = QGroupBox("Log Directory")
        dir_gl = QVBoxLayout(dir_group)
        dir_row = QHBoxLayout()
        self.log_dir_edit = QLineEdit()
        self.log_dir_edit.setPlaceholderText("Default: ~/.config/ssh_manager/logs")
        dir_row.addWidget(self.log_dir_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_log_dir)
        dir_row.addWidget(browse_btn)
        dir_gl.addLayout(dir_row)
        dir_hint = QLabel("Leave empty to use default location.")
        dir_hint.setStyleSheet("color: gray; font-style: italic;")
        dir_gl.addWidget(dir_hint)
        log_layout.addWidget(dir_group)

        fmt_group = QGroupBox("Log File Format")
        fmt_gl = QVBoxLayout(fmt_group)
        self.log_include_date = QCheckBox("Include date in filename")
        self.log_include_date.setChecked(True)
        fmt_gl.addWidget(self.log_include_date)
        fmt_hint = QLabel("Example: 2025-02-06_14-30-00_RouterCore1.log")
        fmt_hint.setStyleSheet("color: gray; font-style: italic;")
        fmt_gl.addWidget(fmt_hint)
        log_layout.addWidget(fmt_group)

        open_row = QHBoxLayout()
        open_btn = QPushButton("Open Logs Folder")
        open_btn.clicked.connect(self._open_logs_folder)
        open_row.addWidget(open_btn)
        open_row.addStretch()
        log_layout.addLayout(open_row)
        log_layout.addStretch()

        self.tabs.addTab(logging_w, "Logging")

        layout.addWidget(self.tabs)
        layout.addLayout(_make_dialog_buttons(self, self._save_and_accept, self.reject))

    def _load_data(self):
        self.theme_dark.setChecked(self.settings.theme == "dark")
        self.theme_light.setChecked(self.settings.theme == "light")
        self.term_widget.load_settings(self.settings.default_terminal)

        log = self.settings.logging
        self.log_enabled.setChecked(log.get('enabled', False))
        self.log_dir_edit.setText(log.get('log_dir', ''))
        self.log_include_date.setChecked(log.get('include_date_prefix', True))
        self._on_logging_toggled(self.log_enabled.isChecked())

    def _save_and_accept(self):
        self.settings.theme = "dark" if self.theme_dark.isChecked() else "light"
        self.settings.default_terminal = self.term_widget.get_settings()
        self.settings.logging = {
            'enabled': self.log_enabled.isChecked(),
            'log_dir': self.log_dir_edit.text(),
            'timestamp_format': '%Y-%m-%d_%H-%M-%S',
            'include_date_prefix': self.log_include_date.isChecked(),
        }
        self.accept()

    def _on_logging_toggled(self, enabled):
        self.log_dir_edit.setEnabled(enabled)
        self.log_include_date.setEnabled(enabled)

    def _browse_log_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Log Directory", self.log_dir_edit.text() or ""
        )
        if path:
            self.log_dir_edit.setText(path)

    def _open_logs_folder(self):
        import subprocess, platform
        from pathlib import Path

        log_dir = self.log_dir_edit.text() or str(Path.home() / ".config" / "ssh_manager" / "logs")
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)

        cmds = {"Linux": ["xdg-open"], "Darwin": ["open"], "Windows": ["explorer"]}
        cmd = cmds.get(platform.system())
        if cmd:
            try:
                subprocess.Popen(cmd + [str(path)])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open folder: {e}")

    def get_settings(self) -> AppSettings:
        return self.settings

    def theme_was_changed(self) -> bool:
        return self.settings.theme != self.original_theme


class PasswordManagerDialog(QDialog):
    """Dialog for viewing and managing saved passwords"""

    def __init__(self, connections: list, parent=None):
        super().__init__(parent)
        self.connections = connections
        self.hidden_passwords = {}

        self.setWindowTitle("Password Manager")
        self.setMinimumSize(620, 350)
        self.setModal(True)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by name, host, or username...")
        self.search_edit.textChanged.connect(self._filter_table)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Host", "Username", "Password", "Actions"])
        header = self.table.horizontalHeader()
        for col, mode in [(0, QHeaderView.Stretch), (1, QHeaderView.Stretch),
                          (2, QHeaderView.ResizeToContents), (3, QHeaderView.Stretch),
                          (4, QHeaderView.ResizeToContents)]:
            header.setSectionResizeMode(col, mode)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        info = QLabel("Click 'Show' to reveal password, 'Copy' to copy to clipboard")
        info.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_data(self):
        self.table.setRowCount(0)
        for conn in self.connections:
            if conn.conn_type != "ssh":
                continue
            ssh_cfg = conn.ssh_config or {}
            password = ssh_cfg.get("password", "")
            if not password:
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)
            self.hidden_passwords[conn.id] = True

            name_item = QTableWidgetItem(conn.name)
            name_item.setData(Qt.UserRole, conn.id)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(ssh_cfg.get("host", "")))
            self.table.setItem(row, 2, QTableWidgetItem(ssh_cfg.get("username", "")))

            pwd_item = QTableWidgetItem("••••••••")
            pwd_item.setData(Qt.UserRole, password)
            self.table.setItem(row, 3, pwd_item)

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)

            show_btn = QPushButton("Show")
            show_btn.setMinimumWidth(60)
            show_btn.clicked.connect(lambda _, r=row: self._toggle_password(r))
            al.addWidget(show_btn)

            copy_btn = QPushButton("Copy")
            copy_btn.setMinimumWidth(60)
            copy_btn.clicked.connect(lambda _, r=row: self._copy_password(r))
            al.addWidget(copy_btn)

            self.table.setCellWidget(row, 4, actions)

    def _toggle_password(self, row):
        pwd_item = self.table.item(row, 3)
        conn_id = self.table.item(row, 0).data(Qt.UserRole)
        show_btn = self.table.cellWidget(row, 4).layout().itemAt(0).widget()

        if self.hidden_passwords.get(conn_id, True):
            pwd_item.setText(pwd_item.data(Qt.UserRole))
            show_btn.setText("Hide")
            self.hidden_passwords[conn_id] = False
        else:
            pwd_item.setText("••••••••")
            show_btn.setText("Show")
            self.hidden_passwords[conn_id] = True

    def _copy_password(self, row):
        password = self.table.item(row, 3).data(Qt.UserRole)
        QApplication.clipboard().setText(password)
        name = self.table.item(row, 0).text()
        QMessageBox.information(self, "Copied", f"Password for '{name}' copied to clipboard.")

    def _filter_table(self, text):
        text = text.lower()
        for row in range(self.table.rowCount()):
            show = any(
                self.table.item(row, col) and text in self.table.item(row, col).text().lower()
                for col in range(3)
            )
            self.table.setRowHidden(row, not show)
