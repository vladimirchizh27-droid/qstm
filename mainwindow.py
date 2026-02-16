"""Main window for SSH Manager"""

import re
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTabWidget, QToolBar, QAction,
    QMenu, QMessageBox, QApplication, QStatusBar, QLabel, QAbstractItemView,
    QProgressBar, QTabBar, QPushButton
)
from PyQt5.QtGui import QKeySequence, QFont, QPixmap, QPainter, QPen, QColor, QIcon
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QMimeData, QThread


def _make_close_icon(color: str, size: int = 14) -> QIcon:
    """Create a clean X icon for tab close buttons"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    m = 3  # margin
    painter.drawLine(m, m, size - m, size - m)
    painter.drawLine(size - m, m, m, size - m)
    painter.end()
    return QIcon(pixmap)


class CloseableTabBar(QTabBar):
    """Custom TabBar with styled close buttons"""

    _STYLE_TEMPLATE = """
        QPushButton {{
            border: none; border-radius: 3px; background: transparent;
            padding: 0px; margin: 2px;
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
        }}
    """

    _dark_style = _STYLE_TEMPLATE.format(hover_bg="#f38ba8")
    _light_style = _STYLE_TEMPLATE.format(hover_bg="#dc3545")
    _current_style = _dark_style
    _icon_color = "#a6adc8"
    _icon_hover_color = "#1e1e2e"

    @classmethod
    def set_theme(cls, theme: str):
        if theme == "light":
            cls._current_style = cls._light_style
            cls._icon_color = "#6c757d"
            cls._icon_hover_color = "#ffffff"
        else:
            cls._current_style = cls._dark_style
            cls._icon_color = "#a6adc8"
            cls._icon_hover_color = "#1e1e2e"

    def __init__(self, parent=None):
        super().__init__(parent)

    def tabInserted(self, index):
        super().tabInserted(index)
        btn = QPushButton()
        btn.setFixedSize(20, 20)
        btn.setFlat(True)
        btn.setIcon(_make_close_icon(self._icon_color))
        btn.setIconSize(QSize(14, 14))
        btn.setStyleSheet(self._current_style)
        btn.clicked.connect(self._on_close_clicked)
        self.setTabButton(index, QTabBar.RightSide, btn)

    def _on_close_clicked(self):
        sender = self.sender()
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.RightSide) == sender:
                self.tabCloseRequested.emit(i)
                return


class CloseableTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(CloseableTabBar(self))


from .models import ConfigManager, Connection, Folder
from .sessions import SSHSession, SerialSession
from .terminal import TerminalWidget
from .dialogs import (
    ConnectionDialog, FolderDialog, SerialPortsDialog,
    SettingsDialog, PasswordManagerDialog,
)


class SessionLogger:
    """Handles logging of terminal session output to file"""

    ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[PX^_].*?\x1b\\|\x1b.')

    def __init__(self, log_dir: Path, connection_name: str, include_date: bool = True):
        self.log_file = None
        self.log_path = None

        safe_name = re.sub(r'[^\w\-.]', '_', connection_name)
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"{ts}_{safe_name}.log" if include_date else f"{safe_name}_{ts}.log"
        self.log_path = log_dir / filename

        try:
            self.log_file = open(self.log_path, 'a', encoding='utf-8', errors='replace')
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.log_file.write(f"=== Session started: {now} ===\n")
            self.log_file.write(f"=== Connection: {connection_name} ===\n\n")
            self.log_file.flush()
        except Exception as e:
            print(f"Failed to create log file: {e}")
            self.log_file = None

    def write(self, data: bytes):
        if not self.log_file:
            return
        try:
            text = data.decode('utf-8', errors='replace')
            self.log_file.write(self.ANSI_ESCAPE.sub('', text))
            self.log_file.flush()
        except Exception:
            pass

    def close(self):
        if self.log_file:
            try:
                self.log_file.write(f"\n\n=== Session ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

    @property
    def is_active(self) -> bool:
        return self.log_file is not None


class DragDropTree(QTreeWidget):
    """Tree widget with drag & drop support"""

    item_moved = pyqtSignal(object, object)
    ROLE_TYPE = Qt.UserRole
    ROLE_ID = Qt.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    MIME_TYPE = 'application/x-ssh-manager-item'

    def mimeTypes(self):
        return [self.MIME_TYPE]

    def mimeData(self, items):
        mime = QMimeData()
        if items:
            item = items[0]
            data = f"{item.data(0, self.ROLE_TYPE)}:{item.data(0, self.ROLE_ID)}"
            mime.setData(self.MIME_TYPE, data.encode())
        return mime

    def dropMimeData(self, parent, index, data, action):
        return False

    def _parse_mime(self, event):
        raw = bytes(event.mimeData().data(self.MIME_TYPE)).decode()
        return raw.split(':')

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            event.ignore()
            return

        target = self.itemAt(event.pos())
        item_type, item_id = self._parse_mime(event)

        if item_type == 'connection':
            if target is None or target.data(0, self.ROLE_TYPE) == 'folder':
                event.acceptProposedAction()
                return
        elif item_type == 'folder':
            if target is None:
                event.acceptProposedAction()
                return
            if target.data(0, self.ROLE_TYPE) == 'folder' and target.data(0, self.ROLE_ID) != item_id:
                event.acceptProposedAction()
                return

        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            event.ignore()
            return

        target = self.itemAt(event.pos())
        item_type, item_id = self._parse_mime(event)

        if not self._find_item_by_id(item_id):
            event.ignore()
            return

        new_parent_id = ""
        if target:
            if target.data(0, self.ROLE_TYPE) == 'folder':
                new_parent_id = target.data(0, self.ROLE_ID)
            elif target.data(0, self.ROLE_TYPE) == 'connection':
                parent = target.parent()
                if parent:
                    new_parent_id = parent.data(0, self.ROLE_ID)

        self.item_moved.emit({'type': item_type, 'id': item_id}, new_parent_id)
        event.acceptProposedAction()

    def _find_item_by_id(self, item_id: str) -> Optional[QTreeWidgetItem]:
        def search(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.data(0, self.ROLE_ID) == item_id:
                    return child
                found = search(child)
                if found:
                    return found
            return None

        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, self.ROLE_ID) == item_id:
                return item
            found = search(item)
            if found:
                return found
        return None


class ConnectionThread(QThread):
    """Thread for establishing connections without blocking UI"""

    connected = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._cancelled = False

    def run(self):
        try:
            if self.session.connect():
                if not self._cancelled:
                    self.connected.emit()
            else:
                if not self._cancelled:
                    self.failed.emit("Connection failed")
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(str(e))

    def cancel(self):
        self._cancelled = True
        if self.session:
            self.session.disconnect()


class SessionTab(QWidget):
    """Widget containing a terminal session"""

    connection_status_changed = pyqtSignal(bool)

    def __init__(self, connection: Connection, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.config = config_manager
        self.session = None
        self.connect_thread = None
        self.logger = None

        self._setup_ui()
        self._apply_terminal_settings()
        self._setup_logging()
        self._start_connection()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Connection status bar
        self.status_widget = QWidget()
        sl = QHBoxLayout(self.status_widget)
        sl.setContentsMargins(6, 2, 6, 2)
        self.status_label = QLabel("Connecting...")
        sl.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximumHeight(16)
        sl.addWidget(self.progress_bar)
        sl.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMaximumWidth(80)
        self.cancel_btn.clicked.connect(self._cancel_connection)
        sl.addWidget(self.cancel_btn)
        layout.addWidget(self.status_widget)

        # Terminal
        self.terminal = TerminalWidget()
        self.terminal.data_to_send.connect(self._on_data_to_send)
        self.terminal.size_changed.connect(self._on_size_changed)
        layout.addWidget(self.terminal)

    def _apply_terminal_settings(self):
        ssh_cfg = self.connection.ssh_config or {}
        term_cfg = ssh_cfg.get('terminal', {})
        if term_cfg:
            self.terminal.apply_settings(term_cfg)

    def _setup_logging(self):
        settings = self.config.get_app_settings()
        log_cfg = settings.logging
        if log_cfg.get('enabled', False):
            log_dir = self.config.get_log_directory()
            self.logger = SessionLogger(log_dir, self.connection.name,
                                        log_cfg.get('include_date_prefix', True))
            if self.logger.is_active:
                self.terminal.write_data(f"[Logging to: {self.logger.log_path.name}]\n".encode())

    def _start_connection(self):
        self.terminal.write_data(f"Connecting to {self.connection.name}...\n".encode())
        cols, rows = self.terminal.get_terminal_size()

        if self.connection.conn_type == "serial":
            self.session = SerialSession(
                self.connection.serial_config, self._on_data_received, self._on_error
            )
        else:
            config = self.connection.ssh_config.copy()
            config['_term_cols'] = cols
            config['_term_rows'] = rows
            self.session = SSHSession(config, self._on_data_received, self._on_error)

        self.connect_thread = ConnectionThread(self.session, self)
        self.connect_thread.connected.connect(self._on_connected)
        self.connect_thread.failed.connect(self._on_connection_failed)
        self.connect_thread.start()

    def _on_connected(self):
        self.status_widget.hide()
        self.terminal.write_data(b"Connected!\n\n")
        self.connection_status_changed.emit(True)

    def _on_connection_failed(self, error):
        self.status_widget.hide()
        self.terminal.write_data(f"\n[CONNECTION FAILED] {error}\n".encode())
        self.terminal.write_data(b"\nPress any key or close this tab.\n")
        self.connection_status_changed.emit(False)

    def _cancel_connection(self):
        if self.connect_thread and self.connect_thread.isRunning():
            self.connect_thread.cancel()
            self.connect_thread.wait(1000)
        self.status_widget.hide()
        self.terminal.write_data(b"\n[CANCELLED] Connection cancelled by user.\n")

    def _on_data_received(self, data: bytes):
        self.terminal.write_data(data)
        if self.logger and self.logger.is_active:
            self.logger.write(data)

    def _on_data_to_send(self, data: bytes):
        if self.session and self.session.is_connected:
            self.session.send(data)

    def _on_size_changed(self, cols, rows):
        if self.session and hasattr(self.session, 'resize'):
            self.session.resize(cols, rows)

    def _on_error(self, message):
        self.terminal.write_data(f"\n[ERROR] {message}\n".encode())

    def disconnect(self):
        if self.logger:
            self.logger.close()
            self.logger = None
        if self.connect_thread and self.connect_thread.isRunning():
            self.connect_thread.cancel()
            self.connect_thread.wait(1000)
        if self.session:
            self.session.disconnect()
            self.session = None

    @property
    def is_connected(self):
        return self.session and self.session.is_connected


class MainWindow(QMainWindow):
    """Main application window"""

    TREE_ROLE_TYPE = DragDropTree.ROLE_TYPE
    TREE_ROLE_ID = DragDropTree.ROLE_ID

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.sessions: Dict[str, SessionTab] = {}

        self._setup_window()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_statusbar()
        self._refresh_tree()

    def _setup_window(self):
        self.setWindowTitle("SSH Manager")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        actions = [
            ("➕ New Connection", "Ctrl+N", "Create new SSH or Serial connection",
             self._new_connection),
            ("📁 New Folder", "Ctrl+Shift+N", "Create new folder",
             self._new_folder),
            None,
            ("▶ Connect", None, "Connect to selected host",
             self._connect_selected),
            ("⏹ Disconnect", "Ctrl+W", "Close current tab",
             self._close_current_tab),
            None,
            ("🔌 Serial Ports", "Ctrl+P", "View available serial ports",
             self._show_serial_ports),
            ("🔑 Passwords", "Ctrl+Shift+P", "View saved passwords",
             self._show_password_manager),
            None,
            ("⚙ Settings", "Ctrl+,", "Application settings",
             self._show_settings),
        ]

        for entry in actions:
            if entry is None:
                toolbar.addSeparator()
            else:
                name, shortcut, tooltip, handler = entry
                action = QAction(name, self)
                if shortcut:
                    action.setShortcut(QKeySequence(shortcut))
                if tooltip:
                    action.setToolTip(f"{tooltip} ({shortcut})" if shortcut else tooltip)
                action.triggered.connect(handler)
                toolbar.addAction(action)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Sidebar
        sidebar = QWidget()
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(4, 4, 4, 4)
        sl.setSpacing(4)

        title = QLabel("Connections")
        title.setStyleSheet("font-weight: 600; font-size: 12px; padding: 2px 4px; color: #89b4fa;")
        sl.addWidget(title)

        self.tree = DragDropTree()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setMinimumWidth(180)
        self.tree.item_moved.connect(self._on_item_moved)
        self.tree.setIndentation(18)
        sl.addWidget(self.tree)
        splitter.addWidget(sidebar)

        # Tabs
        self.tabs = CloseableTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.setDocumentMode(True)
        splitter.addWidget(self.tabs)
        splitter.setSizes([220, 980])

    def _setup_shortcuts(self):
        for i in range(1, 10):
            action = QAction(self)
            action.setShortcut(QKeySequence(f"Ctrl+{i}"))
            action.triggered.connect(lambda _, idx=i - 1: self._switch_to_tab(idx))
            self.addAction(action)

        for key, handler in [(QKeySequence.Delete, self._delete_selected),
                             (QKeySequence("F2"), self._edit_selected)]:
            action = QAction(self)
            action.setShortcut(key)
            action.triggered.connect(handler)
            self.addAction(action)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")

    def _refresh_tree(self):
        # Capture current expanded state from UI before clearing
        expanded_ids = set()
        def _collect(item):
            if item.isExpanded():
                fid = item.data(0, self.TREE_ROLE_ID)
                if fid:
                    expanded_ids.add(fid)
            for i in range(item.childCount()):
                _collect(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            _collect(self.tree.topLevelItem(i))
        had_items = self.tree.topLevelItemCount() > 0

        self.tree.clear()
        folders = {f.id: f for f in self.config.get_folders()}
        connections = self.config.get_connections()
        folder_items: Dict[str, QTreeWidgetItem] = {}

        def _should_expand(fid, folder):
            return (fid in expanded_ids) if had_items else folder.expanded

        # Root folders
        for fid, folder in folders.items():
            if not folder.parent_id:
                item = QTreeWidgetItem([f"📁 {folder.name}"])
                item.setData(0, self.TREE_ROLE_TYPE, "folder")
                item.setData(0, self.TREE_ROLE_ID, fid)
                self.tree.addTopLevelItem(item)
                item.setExpanded(_should_expand(fid, folder))
                folder_items[fid] = item

        # Nested folders
        for fid, folder in folders.items():
            if folder.parent_id and folder.parent_id in folder_items:
                item = QTreeWidgetItem([f"📁 {folder.name}"])
                item.setData(0, self.TREE_ROLE_TYPE, "folder")
                item.setData(0, self.TREE_ROLE_ID, fid)
                folder_items[folder.parent_id].addChild(item)
                item.setExpanded(_should_expand(fid, folder))
                folder_items[fid] = item

        # Connections
        for conn in connections:
            emoji = "🖥" if conn.conn_type == "ssh" else "🔌"
            item = QTreeWidgetItem([f"{emoji} {conn.name}"])
            item.setData(0, self.TREE_ROLE_TYPE, "connection")
            item.setData(0, self.TREE_ROLE_ID, conn.id)
            parent = folder_items.get(conn.folder_id)
            if parent:
                parent.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

    # --- Context menu & actions ---

    def _tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            if item.data(0, self.TREE_ROLE_TYPE) == "connection":
                menu.addAction("Connect", self._connect_selected)
                menu.addSeparator()
            menu.addAction("Edit", self._edit_selected)
            menu.addAction("Delete", self._delete_selected)
            menu.addSeparator()
        menu.addAction("New Connection", self._new_connection)
        menu.addAction("New Folder", self._new_folder)
        menu.exec_(self.tree.mapToGlobal(pos))

    def _on_item_double_clicked(self, item, column):
        if item.data(0, self.TREE_ROLE_TYPE) == "connection":
            self._connect_selected()

    def _on_item_moved(self, item_info, new_parent_id):
        item_type, item_id = item_info['type'], item_info['id']
        if item_type == 'connection':
            conn = self.config.get_connection_by_id(item_id)
            if conn:
                conn.folder_id = new_parent_id
                self.config.update_connection(conn)
        elif item_type == 'folder':
            folder = self.config.get_folder_by_id(item_id)
            if folder:
                folder.parent_id = new_parent_id
                self.config.update_folder(folder)
        self._refresh_tree()
        self.statusbar.showMessage(f"{item_type.title()} moved", 2000)

    def _get_selected_folder_id(self) -> str:
        item = self.tree.currentItem()
        if not item:
            return ""
        if item.data(0, self.TREE_ROLE_TYPE) == "folder":
            return item.data(0, self.TREE_ROLE_ID)
        if item.data(0, self.TREE_ROLE_TYPE) == "connection":
            conn = self.config.get_connection_by_id(item.data(0, self.TREE_ROLE_ID))
            return conn.folder_id if conn else ""
        return ""

    def _new_connection(self):
        folder_id = self._get_selected_folder_id()
        conn = Connection(folder_id=folder_id)
        default_term = self.config.get_default_terminal_settings()
        if conn.ssh_config:
            conn.ssh_config['terminal'] = default_term
        dialog = ConnectionDialog(conn, self)
        if dialog.exec_():
            self.config.add_connection(dialog.get_connection())
            self._refresh_tree()
            self.statusbar.showMessage("Connection created", 3000)

    def _new_folder(self):
        folder = Folder(parent_id=self._get_selected_folder_id())
        dialog = FolderDialog(folder, self)
        if dialog.exec_():
            self.config.add_folder(dialog.get_folder())
            self._refresh_tree()
            self.statusbar.showMessage("Folder created", 3000)

    def _edit_selected(self):
        item = self.tree.currentItem()
        if not item:
            return
        item_type = item.data(0, self.TREE_ROLE_TYPE)
        item_id = item.data(0, self.TREE_ROLE_ID)

        if item_type == "connection":
            conn = self.config.get_connection_by_id(item_id)
            if conn:
                dialog = ConnectionDialog(conn, self)
                if dialog.exec_():
                    self.config.update_connection(dialog.get_connection())
                    self._refresh_tree()
                    self.statusbar.showMessage("Connection updated", 3000)
        elif item_type == "folder":
            folder = self.config.get_folder_by_id(item_id)
            if folder:
                dialog = FolderDialog(folder, self)
                if dialog.exec_():
                    self.config.update_folder(dialog.get_folder())
                    self._refresh_tree()
                    self.statusbar.showMessage("Folder updated", 3000)

    def _delete_selected(self):
        item = self.tree.currentItem()
        if not item:
            return
        name = item.text(0)
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete {name}?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            item_type = item.data(0, self.TREE_ROLE_TYPE)
            item_id = item.data(0, self.TREE_ROLE_ID)
            if item_type == "connection":
                self.config.delete_connection(item_id)
            elif item_type == "folder":
                self.config.delete_folder(item_id)
            self._refresh_tree()
            self.statusbar.showMessage("Deleted", 3000)

    def _connect_selected(self):
        item = self.tree.currentItem()
        if not item or item.data(0, self.TREE_ROLE_TYPE) != "connection":
            return
        conn_id = item.data(0, self.TREE_ROLE_ID)
        conn = self.config.get_connection_by_id(conn_id)
        if not conn:
            return
        tab = SessionTab(conn, self.config, self)
        idx = self.tabs.addTab(tab, conn.name)
        self.tabs.setCurrentIndex(idx)
        self.sessions[conn_id] = tab
        self.statusbar.showMessage(f"Connected to {conn.name}", 3000)

    def _close_tab(self, index):
        widget = self.tabs.widget(index)
        if isinstance(widget, SessionTab):
            widget.disconnect()
            for sid, tab in list(self.sessions.items()):
                if tab == widget:
                    del self.sessions[sid]
                    break
        self.tabs.removeTab(index)

    def _close_current_tab(self):
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self._close_tab(idx)

    def _switch_to_tab(self, index):
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)

    def _show_serial_ports(self):
        SerialPortsDialog(self).exec_()

    def _show_password_manager(self):
        PasswordManagerDialog(self.config.get_connections(), self).exec_()

    def _show_settings(self):
        settings = self.config.get_app_settings()
        dialog = SettingsDialog(settings, self)
        if dialog.exec_():
            self.config.update_app_settings(dialog.get_settings())
            self.statusbar.showMessage("Settings saved", 3000)
            if dialog.theme_was_changed():
                QMessageBox.information(
                    self, "Theme Changed",
                    "Theme changes will take effect after restarting the application."
                )

    def closeEvent(self, event):
        for tab in self.sessions.values():
            tab.disconnect()
        event.accept()
