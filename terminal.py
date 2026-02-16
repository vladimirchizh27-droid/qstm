"""
Terminal emulator widget using pyte for proper VT100/xterm emulation
With syntax highlighting for network commands (like MobaXterm)
"""

import re
import pyte
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QFontDatabase,
    QKeyEvent, QPaintEvent, QResizeEvent
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize


# Syntax highlighting rules for network equipment commands
SYNTAX_RULES = {
    # Cisco/Huawei/Network commands - keywords
    'keyword': {
        'color': '#89b4fa',  # Blue
        'words': [
            'show', 'display', 'configure', 'config', 'terminal', 'interface',
            'router', 'switch', 'vlan', 'spanning-tree', 'stp',
            'enable', 'disable', 'shutdown', 'no', 'exit', 'end', 'quit',
            'write', 'copy', 'save', 'commit', 'rollback',
            'ping', 'traceroute', 'tracert', 'telnet', 'ssh',
            'debug', 'undebug', 'logging', 'terminal', 'length', 'width',
        ]
    },
    # IP/Network related
    'network': {
        'color': '#a6e3a1',  # Green
        'words': [
            'ip', 'ipv6', 'address', 'route', 'routing', 'static',
            'ospf', 'eigrp', 'bgp', 'rip', 'isis', 'mpls', 'vpn', 'vrf',
            'acl', 'access-list', 'prefix-list', 'route-map',
            'nat', 'pat', 'dhcp', 'dns', 'ntp', 'snmp', 'syslog',
            'arp', 'mac', 'mac-address', 'neighbor', 'adjacency',
            'network', 'area', 'subnet', 'mask', 'gateway', 'default',
        ]
    },
    # Interface types
    'interface': {
        'color': '#f9e2af',  # Yellow
        'words': [
            'ethernet', 'fastethernet', 'gigabitethernet', 'tengigabitethernet',
            'fa', 'gi', 'te', 'eth', 'ge', 'xe', 'fe',
            'serial', 'loopback', 'tunnel', 'vlanif', 'port-channel',
            'bridge-aggregation', 'eth-trunk', 'bundle',
            'management', 'mgmt', 'console', 'aux', 'vty',
        ]
    },
    # Status/State words
    'status': {
        'color': '#f38ba8',  # Red/Pink
        'words': [
            'up', 'down', 'administratively', 'err-disabled',
            'connected', 'notconnect', 'disabled', 'blocked', 'forwarding',
            'established', 'active', 'passive', 'idle', 'full', 'half',
            'error', 'errors', 'drops', 'discards', 'collision',
        ]
    },
    # Protocols
    'protocol': {
        'color': '#cba6f7',  # Purple
        'words': [
            'tcp', 'udp', 'icmp', 'http', 'https', 'ftp', 'tftp',
            'smtp', 'pop3', 'imap', 'ldap', 'radius', 'tacacs',
            'dot1q', '802.1q', 'lacp', 'pagp', 'lldp', 'cdp',
            'stp', 'rstp', 'mstp', 'pvst', 'hsrp', 'vrrp', 'glbp',
        ]
    },
}

# Compile regex patterns for syntax highlighting
SYNTAX_PATTERNS = {}
for category, data in SYNTAX_RULES.items():
    pattern = r'\b(' + '|'.join(re.escape(w) for w in data['words']) + r')\b'
    SYNTAX_PATTERNS[category] = {
        'pattern': re.compile(pattern, re.IGNORECASE),
        'color': data['color']
    }

# IP address pattern
IP_PATTERN = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?)\b')
IP_COLOR = '#94e2d5'  # Teal

# Numbers pattern
NUMBER_PATTERN = re.compile(r'\b(\d+)\b')
NUMBER_COLOR = '#fab387'  # Peach


class TerminalColors:
    """Terminal color palette"""
    
    PALETTE = [
        "#000000", "#cd0000", "#00cd00", "#cdcd00",
        "#0000ee", "#cd00cd", "#00cdcd", "#e5e5e5",
        "#7f7f7f", "#ff0000", "#00ff00", "#ffff00",
        "#5c5cff", "#ff00ff", "#00ffff", "#ffffff",
    ]
    
    DEFAULT_FG = "#cdd6f4"
    DEFAULT_BG = "#1e1e2e"
    CURSOR_COLOR = "#f5e0dc"
    
    @classmethod
    def get_color(cls, code) -> str:
        if code is None or code == "default":
            return None
        
        if isinstance(code, str):
            if code.startswith("#"):
                return code
            name_map = {
                "black": 0, "red": 1, "green": 2, "yellow": 3,
                "blue": 4, "magenta": 5, "cyan": 6, "white": 7,
                "brightblack": 8, "brightred": 9, "brightgreen": 10,
                "brightyellow": 11, "brightblue": 12, "brightmagenta": 13,
                "brightcyan": 14, "brightwhite": 15,
            }
            code = name_map.get(code.lower().replace("_", "").replace("-", ""), 7)
        
        if isinstance(code, int):
            if code < 16:
                return cls.PALETTE[code]
            elif code < 232:
                code -= 16
                r = (code // 36) * 51
                g = ((code // 6) % 6) * 51
                b = (code % 6) * 51
                return f"#{r:02x}{g:02x}{b:02x}"
            else:
                gray = (code - 232) * 10 + 8
                return f"#{gray:02x}{gray:02x}{gray:02x}"
        
        return cls.DEFAULT_FG


class TerminalWidget(QWidget):
    """
    Terminal emulator with:
    - VT100/xterm emulation via pyte
    - Syntax highlighting for network commands
    - Customizable colors and fonts
    """
    
    data_to_send = pyqtSignal(bytes)
    data_received = pyqtSignal(bytes)
    size_changed = pyqtSignal(int, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.cols = 80
        self.rows = 24
        
        # pyte screen with history
        self.screen = pyte.HistoryScreen(self.cols, self.rows, history=10000)
        self.screen.set_mode(pyte.modes.LNM)
        self.stream = pyte.Stream(self.screen)
        
        # Default settings
        self.settings = {
            'bg_color': '#1e1e2e',
            'fg_color': '#cdd6f4',
            'cursor_color': '#f5e0dc',
            'font_family': '',
            'font_size': 11,
            'syntax_highlight': True,
        }
        
        self._setup_font()
        self._update_colors()
        
        # Cursor blink
        self.cursor_visible = True
        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self._blink_cursor)
        self.cursor_timer.start(500)
        
        # Widget settings
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        
        # Scroll offset
        self.scroll_offset = 0
        
        # Thread-safe updates
        self.data_received.connect(self._do_write_data)
        
        # Batch updates
        self.update_pending = False
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._do_update)
        self.update_timer.start(16)
        
        # Cache for syntax-highlighted lines
        self._syntax_cache = {}
        
        # Mouse selection
        self.selection_start = None  # (col, row)
        self.selection_end = None    # (col, row)
        self.is_selecting = False
    
    def apply_settings(self, settings: dict):
        """Apply terminal settings from connection config"""
        self.settings.update(settings)
        self._setup_font()
        self._update_colors()
        self._syntax_cache.clear()
        self._schedule_update()
    
    def _setup_font(self):
        """Setup monospace font"""
        family = self.settings.get('font_family', '')
        size = self.settings.get('font_size', 11)
        
        if not family:
            font_families = [
                "JetBrains Mono", "Fira Code", "Source Code Pro",
                "DejaVu Sans Mono", "Consolas", "Monaco", "monospace"
            ]
            available = QFontDatabase().families()
            for f in font_families:
                if f in available:
                    family = f
                    break
            else:
                family = "monospace"
        
        self.font = QFont(family, size)
        self.font.setStyleHint(QFont.Monospace)
        self.font.setFixedPitch(True)
        
        metrics = QFontMetrics(self.font)
        self.char_width = metrics.horizontalAdvance('M')
        self.char_height = metrics.height()
        self.char_ascent = metrics.ascent()
    
    def _update_colors(self):
        """Update color objects from settings"""
        self.bg_color = QColor(self.settings.get('bg_color', '#1e1e2e'))
        self.fg_color = QColor(self.settings.get('fg_color', '#cdd6f4'))
        self.cursor_color = QColor(self.settings.get('cursor_color', '#f5e0dc'))
    
    def write_data(self, data: bytes):
        """Thread-safe write"""
        self.data_received.emit(data)
    
    def _do_write_data(self, data: bytes):
        """Process data in main thread"""
        try:
            text = data.decode('utf-8', errors='replace')
        except Exception:
            text = str(data)
        
        self.stream.feed(text)
        self.scroll_offset = 0
        self._syntax_cache.clear()
        self._schedule_update()
    
    def _schedule_update(self):
        self.update_pending = True
    
    def _do_update(self):
        if self.update_pending:
            self.update_pending = False
            self.update()
    
    def _blink_cursor(self):
        self.cursor_visible = not self.cursor_visible
        self._schedule_update()
    
    def _get_line_text(self, line) -> str:
        """Extract text from a pyte line"""
        result = []
        for i in range(min(self.cols, len(line))):
            char = line[i]
            if isinstance(char, str):
                result.append(char if char else ' ')
            else:
                result.append(char.data if char.data else ' ')
        return ''.join(result)
    
    def _get_syntax_colors(self, line_text: str) -> dict:
        """Get syntax highlighting colors for positions in line"""
        if not self.settings.get('syntax_highlight', True):
            return {}
        
        colors = {}
        
        # Check for IP addresses first
        for match in IP_PATTERN.finditer(line_text):
            for i in range(match.start(), match.end()):
                colors[i] = IP_COLOR
        
        # Check syntax patterns
        for category, data in SYNTAX_PATTERNS.items():
            for match in data['pattern'].finditer(line_text):
                for i in range(match.start(), match.end()):
                    if i not in colors:  # Don't override IP colors
                        colors[i] = data['color']
        
        return colors
    
    def sizeHint(self) -> QSize:
        return QSize(self.cols * self.char_width + 4, 
                     self.rows * self.char_height + 4)
    
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        
        new_cols = max(10, (event.size().width() - 4) // self.char_width)
        new_rows = max(2, (event.size().height() - 4) // self.char_height)
        
        if new_cols != self.cols or new_rows != self.rows:
            self.cols = new_cols
            self.rows = new_rows
            self.screen.resize(self.rows, self.cols)
            self._syntax_cache.clear()
            self.size_changed.emit(self.cols, self.rows)
            self._schedule_update()
    
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setFont(self.font)
        painter.fillRect(self.rect(), self.bg_color)
        
        history_top = list(self.screen.history.top) if self.screen.history.top else []
        total_history = len(history_top)
        
        for row in range(self.rows):
            y = row * self.char_height + self.char_ascent + 2
            
            # Get line based on scroll position
            if self.scroll_offset > 0:
                history_idx = total_history - self.scroll_offset + row
                if 0 <= history_idx < total_history:
                    line = history_top[history_idx]
                elif history_idx >= total_history:
                    buffer_idx = history_idx - total_history
                    if buffer_idx < len(self.screen.buffer):
                        line = self.screen.buffer[buffer_idx]
                    else:
                        continue
                else:
                    continue
            else:
                if row < len(self.screen.buffer):
                    line = self.screen.buffer[row]
                else:
                    continue
            
            # Get syntax highlighting for this line
            line_text = self._get_line_text(line)
            syntax_colors = self._get_syntax_colors(line_text)
            
            # Check if line is from history (string) or buffer (Char objects)
            is_history_line = isinstance(line[0] if len(line) > 0 else None, str)
            
            for col in range(min(self.cols, len(line))):
                if is_history_line:
                    # History lines are plain strings
                    char = line[col] if col < len(line) else " "
                    fg_name = "default"
                    bg_name = "default"
                    is_bold = False
                    is_italic = False
                    is_underline = False
                    is_strike = False
                    is_reverse = False
                else:
                    # Buffer lines are Char objects
                    char_data = line[col]
                    char = char_data.data if char_data.data else " "
                    fg_name = char_data.fg
                    bg_name = char_data.bg
                    is_bold = char_data.bold
                    is_italic = char_data.italics
                    is_underline = char_data.underscore
                    is_strike = char_data.strikethrough
                    is_reverse = char_data.reverse
                    
                    # Bold = bright colors
                    if is_bold and fg_name in ('black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'):
                        fg_name = 'bright' + fg_name
                
                fg = TerminalColors.get_color(fg_name)
                bg = TerminalColors.get_color(bg_name)
                
                # Apply syntax highlighting if no color from terminal
                if fg is None and col in syntax_colors:
                    fg = syntax_colors[col]
                
                fg_color = QColor(fg) if fg else self.fg_color
                bg_color = QColor(bg) if bg else self.bg_color
                
                if is_reverse:
                    fg_color, bg_color = bg_color, fg_color
                
                x = col * self.char_width + 2
                cell_y = row * self.char_height + 2
                
                # Check if cell is selected
                is_selected = self._is_cell_selected(col, row)
                if is_selected:
                    # Selection colors - invert
                    bg_color = QColor("#89b4fa")  # Selection highlight
                    fg_color = QColor("#1e1e2e")  # Dark text on selection
                
                # Draw background
                if bg or is_reverse or is_selected:
                    painter.fillRect(x, cell_y, self.char_width, self.char_height, bg_color)
                
                # Draw character
                if char and char != " ":
                    font = QFont(self.font)
                    if is_bold:
                        font.setBold(True)
                    if is_italic:
                        font.setItalic(True)
                    if is_underline:
                        font.setUnderline(True)
                    if is_strike:
                        font.setStrikeOut(True)
                    
                    painter.setFont(font)
                    painter.setPen(fg_color)
                    painter.drawText(x, y, char)
                    painter.setFont(self.font)
        
        # Draw cursor
        if self.cursor_visible and self.hasFocus() and self.scroll_offset == 0:
            cursor_x = self.screen.cursor.x * self.char_width + 2
            cursor_y = self.screen.cursor.y * self.char_height + 2
            
            painter.fillRect(
                cursor_x, cursor_y,
                self.char_width, self.char_height,
                self.cursor_color
            )
            
            if self.screen.cursor.y < len(self.screen.buffer):
                line = self.screen.buffer[self.screen.cursor.y]
                if self.screen.cursor.x < len(line):
                    char = line[self.screen.cursor.x].data or " "
                    if char.strip():
                        painter.setPen(self.bg_color)
                        painter.drawText(
                            cursor_x, 
                            cursor_y + self.char_ascent,
                            char
                        )
        
        painter.end()
    
    def event(self, event):
        """Override to catch Tab key"""
        if event.type() == event.KeyPress:
            if event.key() == Qt.Key_Tab or event.key() == Qt.Key_Backtab:
                self.keyPressEvent(event)
                return True
        return super().event(event)
    
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()
        text = event.text()
        
        # Clipboard shortcuts
        if modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            if key == Qt.Key_C:
                # Copy selected text
                selected = self._get_selected_text()
                if selected:
                    clipboard = QApplication.clipboard()
                    clipboard.setText(selected)
                return
            elif key == Qt.Key_V:
                self._paste_clipboard()
                return
        
        # Clear selection on any input
        if self.selection_start or self.selection_end:
            self.clear_selection()
        
        data = None
        
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            data = b'\r'
        elif key == Qt.Key_Backspace:
            data = b'\x7f'
        elif key == Qt.Key_Tab:
            data = b'\x1b[Z' if modifiers & Qt.ShiftModifier else b'\t'
        elif key == Qt.Key_Escape:
            data = b'\x1b'
        elif key == Qt.Key_Up:
            if modifiers & Qt.ShiftModifier:
                self._scroll_up(1)
                return
            data = b'\x1b[A'
        elif key == Qt.Key_Down:
            if modifiers & Qt.ShiftModifier:
                self._scroll_down(1)
                return
            data = b'\x1b[B'
        elif key == Qt.Key_Right:
            data = b'\x1b[C'
        elif key == Qt.Key_Left:
            data = b'\x1b[D'
        elif key == Qt.Key_Home:
            data = b'\x1b[H'
        elif key == Qt.Key_End:
            data = b'\x1b[F'
        elif key == Qt.Key_PageUp:
            if modifiers & Qt.ShiftModifier:
                self._scroll_up(self.rows - 1)
                return
            data = b'\x1b[5~'
        elif key == Qt.Key_PageDown:
            if modifiers & Qt.ShiftModifier:
                self._scroll_down(self.rows - 1)
                return
            data = b'\x1b[6~'
        elif key == Qt.Key_Insert:
            data = b'\x1b[2~'
        elif key == Qt.Key_Delete:
            data = b'\x1b[3~'
        elif Qt.Key_F1 <= key <= Qt.Key_F12:
            fn = key - Qt.Key_F1 + 1
            f_codes = {
                1: b'\x1bOP', 2: b'\x1bOQ', 3: b'\x1bOR', 4: b'\x1bOS',
                5: b'\x1b[15~', 6: b'\x1b[17~', 7: b'\x1b[18~', 8: b'\x1b[19~',
                9: b'\x1b[20~', 10: b'\x1b[21~', 11: b'\x1b[23~', 12: b'\x1b[24~',
            }
            data = f_codes.get(fn)
        elif modifiers & Qt.ControlModifier and not (modifiers & Qt.AltModifier):
            if Qt.Key_A <= key <= Qt.Key_Z:
                data = bytes([key - Qt.Key_A + 1])
            elif key == Qt.Key_BracketLeft:
                data = b'\x1b'
            elif key == Qt.Key_Backslash:
                data = b'\x1c'
            elif key == Qt.Key_BracketRight:
                data = b'\x1d'
            elif key == Qt.Key_Space:
                data = b'\x00'
        elif modifiers & Qt.AltModifier:
            if text:
                data = b'\x1b' + text.encode('utf-8')
        elif text:
            data = text.encode('utf-8')
        
        if data:
            self.data_to_send.emit(data)
    
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self._scroll_up(3)
        elif delta < 0:
            self._scroll_down(3)
    
    def mousePressEvent(self, event):
        """Start text selection on mouse press"""
        if event.button() == Qt.LeftButton:
            pos = self._screen_to_cell(event.pos())
            self.selection_start = pos
            self.selection_end = pos
            self.is_selecting = True
            self._schedule_update()
    
    def mouseMoveEvent(self, event):
        """Update selection while dragging"""
        if self.is_selecting and event.buttons() & Qt.LeftButton:
            pos = self._screen_to_cell(event.pos())
            self.selection_end = pos
            self._schedule_update()
    
    def mouseReleaseEvent(self, event):
        """Finish selection and auto-copy to clipboard"""
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            pos = self._screen_to_cell(event.pos())
            self.selection_end = pos
            
            # Auto-copy if there's a selection
            text = self._get_selected_text()
            if text:
                clipboard = QApplication.clipboard()
                clipboard.setText(text)
            
            self._schedule_update()
    
    def mouseDoubleClickEvent(self, event):
        """Select word on double click"""
        if event.button() == Qt.LeftButton:
            pos = self._screen_to_cell(event.pos())
            col, row = pos
            
            # Get line text
            if row < len(self.screen.buffer):
                line = self.screen.buffer[row]
                line_text = self._get_line_text(line)
                
                # Find word boundaries
                start_col = col
                end_col = col
                
                # Expand left
                while start_col > 0 and self._is_word_char(line_text[start_col - 1] if start_col - 1 < len(line_text) else ' '):
                    start_col -= 1
                
                # Expand right
                while end_col < len(line_text) and self._is_word_char(line_text[end_col] if end_col < len(line_text) else ' '):
                    end_col += 1
                
                self.selection_start = (start_col, row)
                self.selection_end = (end_col, row)
                
                # Auto-copy
                text = self._get_selected_text()
                if text:
                    clipboard = QApplication.clipboard()
                    clipboard.setText(text)
                
                self._schedule_update()
    
    def _is_word_char(self, char):
        """Check if character is part of a word"""
        return char.isalnum() or char in '-_./:'
    
    def _screen_to_cell(self, pos):
        """Convert screen position to cell coordinates"""
        col = max(0, min((pos.x() - 2) // self.char_width, self.cols - 1))
        row = max(0, min((pos.y() - 2) // self.char_height, self.rows - 1))
        return (col, row)
    
    def _get_selected_text(self):
        """Get selected text from terminal buffer"""
        if not self.selection_start or not self.selection_end:
            return ""
        
        start_col, start_row = self.selection_start
        end_col, end_row = self.selection_end
        
        # Normalize selection (start should be before end)
        if (start_row > end_row) or (start_row == end_row and start_col > end_col):
            start_col, end_col = end_col, start_col
            start_row, end_row = end_row, start_row
        
        # Same position = no selection
        if start_row == end_row and start_col == end_col:
            return ""
        
        lines = []
        for row in range(start_row, end_row + 1):
            if row < len(self.screen.buffer):
                line = self.screen.buffer[row]
                line_text = self._get_line_text(line)
                
                if row == start_row and row == end_row:
                    # Single line selection
                    lines.append(line_text[start_col:end_col])
                elif row == start_row:
                    # First line
                    lines.append(line_text[start_col:])
                elif row == end_row:
                    # Last line
                    lines.append(line_text[:end_col])
                else:
                    # Middle lines
                    lines.append(line_text)
        
        return '\n'.join(line.rstrip() for line in lines)
    
    def _is_cell_selected(self, col, row):
        """Check if a cell is within the current selection"""
        if not self.selection_start or not self.selection_end:
            return False
        
        start_col, start_row = self.selection_start
        end_col, end_row = self.selection_end
        
        # Normalize
        if (start_row > end_row) or (start_row == end_row and start_col > end_col):
            start_col, end_col = end_col, start_col
            start_row, end_row = end_row, start_row
        
        if row < start_row or row > end_row:
            return False
        
        if row == start_row and row == end_row:
            return start_col <= col < end_col
        elif row == start_row:
            return col >= start_col
        elif row == end_row:
            return col < end_col
        else:
            return True
    
    def clear_selection(self):
        """Clear the current selection"""
        self.selection_start = None
        self.selection_end = None
        self._schedule_update()
    
    def _scroll_up(self, lines=1):
        max_offset = len(self.screen.history.top) if self.screen.history.top else 0
        self.scroll_offset = min(self.scroll_offset + lines, max_offset)
        self._schedule_update()
    
    def _scroll_down(self, lines=1):
        self.scroll_offset = max(0, self.scroll_offset - lines)
        self._schedule_update()
    
    def _paste_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.data_to_send.emit(text.encode('utf-8'))
    
    def clear_terminal(self):
        self.screen.reset()
        self._syntax_cache.clear()
        self._schedule_update()
    
    def get_terminal_size(self) -> tuple:
        return (self.cols, self.rows)
