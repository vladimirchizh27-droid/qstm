#!/usr/bin/env python3
"""SSH Manager - Main entry point"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

from ssh_manager import MainWindow, ConfigManager, CloseableTabBar

# --- Theme color definitions ---

DARK = {
    'window': '#1e1e2e', 'window_text': '#cdd6f4',
    'base': '#181825', 'alt_base': '#1e1e2e',
    'tooltip_bg': '#313244', 'tooltip_text': '#cdd6f4',
    'text': '#cdd6f4', 'placeholder': '#6c7086',
    'button': '#313244', 'button_text': '#cdd6f4',
    'bright_text': '#f38ba8', 'link': '#89b4fa',
    'highlight': '#89b4fa', 'highlight_text': '#1e1e2e',
    'disabled_text': '#6c7086',
    # UI surfaces
    'surface0': '#313244', 'surface1': '#45475a', 'surface2': '#585b70',
    'overlay': '#6c7086', 'subtext': '#a6adc8', 'accent': '#89b4fa',
    'tab_bg': '#181825', 'tab_text': '#a6adc8',
    'input_bg': '#313244', 'input_border': '#45475a',
    'btn_bg': '#45475a', 'btn_border': '#585b70',
    'tree_bg': '#181825', 'tree_border': '#313244',
    'tree_hover': '#313244', 'tree_selected': '#45475a',
    'splitter': '#313244', 'status_bg': '#181825', 'status_border': '#313244',
    'check_border': '#45475a', 'check_bg': '#313244',
    'scrollbar_bg': '#181825', 'scrollbar_handle': '#45475a', 'scrollbar_hover': '#585b70',
    'progress_bg': '#313244',
    'selection_bg': '#585b70',
    'close_hover': '#f38ba8',
}

LIGHT = {
    'window': '#f8f9fa', 'window_text': '#212529',
    'base': '#ffffff', 'alt_base': '#f8f9fa',
    'tooltip_bg': '#ffffff', 'tooltip_text': '#212529',
    'text': '#212529', 'placeholder': '#6c757d',
    'button': '#e9ecef', 'button_text': '#212529',
    'bright_text': '#dc3545', 'link': '#0d6efd',
    'highlight': '#0d6efd', 'highlight_text': '#ffffff',
    'disabled_text': '#6c757d',
    'surface0': '#e9ecef', 'surface1': '#dee2e6', 'surface2': '#ced4da',
    'overlay': '#6c757d', 'subtext': '#6c757d', 'accent': '#0d6efd',
    'tab_bg': '#e9ecef', 'tab_text': '#6c757d',
    'input_bg': '#ffffff', 'input_border': '#ced4da',
    'btn_bg': '#e9ecef', 'btn_border': '#ced4da',
    'tree_bg': '#ffffff', 'tree_border': '#dee2e6',
    'tree_hover': '#e9ecef', 'tree_selected': '#cfe2ff',
    'splitter': '#dee2e6', 'status_bg': '#f8f9fa', 'status_border': '#dee2e6',
    'check_border': '#ced4da', 'check_bg': '#ffffff',
    'scrollbar_bg': '#f8f9fa', 'scrollbar_handle': '#ced4da', 'scrollbar_hover': '#adb5bd',
    'progress_bg': '#e9ecef',
    'selection_bg': '#cfe2ff',
    'close_hover': '#dc3545',
}


def _build_palette(c: dict) -> QPalette:
    p = QPalette()
    _s = lambda hex_color: QColor(hex_color)
    p.setColor(QPalette.Window, _s(c['window']))
    p.setColor(QPalette.WindowText, _s(c['window_text']))
    p.setColor(QPalette.Base, _s(c['base']))
    p.setColor(QPalette.AlternateBase, _s(c['alt_base']))
    p.setColor(QPalette.ToolTipBase, _s(c['tooltip_bg']))
    p.setColor(QPalette.ToolTipText, _s(c['tooltip_text']))
    p.setColor(QPalette.Text, _s(c['text']))
    p.setColor(QPalette.PlaceholderText, _s(c['placeholder']))
    p.setColor(QPalette.Button, _s(c['button']))
    p.setColor(QPalette.ButtonText, _s(c['button_text']))
    p.setColor(QPalette.BrightText, _s(c['bright_text']))
    p.setColor(QPalette.Link, _s(c['link']))
    p.setColor(QPalette.Highlight, _s(c['highlight']))
    p.setColor(QPalette.HighlightedText, _s(c['highlight_text']))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, _s(c['disabled_text']))
    return p


def _build_stylesheet(c: dict) -> str:
    return f"""
    * {{ font-size: 12px; }}

    QMainWindow, QDialog {{ background-color: {c['window']}; }}
    QDialog QWidget, QDialog QGroupBox {{ background-color: transparent; }}
    QTabWidget > QWidget {{ background-color: {c['window']}; }}

    QToolTip {{
        background-color: {c['tooltip_bg']}; color: {c['tooltip_text']};
        border: 1px solid {c['surface1']}; padding: 3px 6px; border-radius: 4px;
    }}
    QMenu {{
        background-color: {c['window']}; color: {c['text']};
        border: 1px solid {c['surface1']}; border-radius: 4px; padding: 3px;
    }}
    QMenu::item {{ padding: 5px 20px 5px 10px; border-radius: 3px; }}
    QMenu::item:selected {{ background-color: {c['surface1']}; }}
    QMenu::separator {{ height: 1px; background-color: {c['surface1']}; margin: 3px 6px; }}

    QMenuBar {{
        background-color: {c['window']}; color: {c['text']}; padding: 1px;
    }}
    QMenuBar::item {{ padding: 3px 7px; border-radius: 4px; }}
    QMenuBar::item:selected {{ background-color: {c['surface1']}; }}

    QToolBar {{
        background-color: {c['window']}; border: none;
        border-bottom: 1px solid {c['surface0']}; padding: 2px; spacing: 2px;
    }}
    QToolBar::separator {{ width: 1px; background-color: {c['surface1']}; margin: 3px 6px; }}
    QToolButton {{
        background: transparent; border: 1px solid transparent;
        border-radius: 4px; padding: 4px 8px; color: {c['text']};
    }}
    QToolButton:hover {{ background-color: {c['surface0']}; border-color: {c['surface1']}; }}
    QToolButton:pressed {{ background-color: {c['surface1']}; }}

    QTabWidget::pane {{
        border: 1px solid {c['surface0']}; border-radius: 4px;
        background-color: {c['window']};
    }}
    QTabBar {{ background-color: transparent; }}
    QTabBar::tab {{
        background-color: {c['tab_bg']}; color: {c['tab_text']};
        padding: 5px 14px; border: 1px solid {c['surface0']}; border-bottom: none;
        border-top-left-radius: 5px; border-top-right-radius: 5px;
        margin-right: 2px; min-width: 80px;
    }}
    QTabBar::tab:selected {{
        background-color: {c['window']}; color: {c['text']};
        border-bottom: 2px solid {c['accent']};
    }}
    QTabBar::tab:hover:!selected {{ background-color: {c['surface0']}; color: {c['text']}; }}

    QHeaderView::section {{
        background-color: {c['surface0']}; color: {c['text']};
        padding: 5px 8px; border: none;
        border-right: 1px solid {c['surface1']}; border-bottom: 1px solid {c['surface1']};
        font-weight: 500;
    }}

    QScrollBar:vertical {{
        background-color: {c['scrollbar_bg']}; width: 10px; border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {c['scrollbar_handle']}; min-height: 24px;
        border-radius: 4px; margin: 1px;
    }}
    QScrollBar::handle:vertical:hover {{ background-color: {c['scrollbar_hover']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    QScrollBar:horizontal {{
        background-color: {c['scrollbar_bg']}; height: 10px; border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {c['scrollbar_handle']}; min-width: 24px;
        border-radius: 4px; margin: 1px;
    }}
    QScrollBar::handle:horizontal:hover {{ background-color: {c['scrollbar_hover']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

    QGroupBox {{
        border: 1px solid {c['surface1']}; border-radius: 6px;
        margin-top: 6px; padding: 6px; padding-top: 22px; font-weight: 500;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; subcontrol-position: top left;
        left: 8px; top: 6px; padding: 0 4px; color: {c['accent']};
    }}

    QLabel {{ color: {c['text']}; }}

    QLineEdit, QSpinBox, QTextEdit {{
        background-color: {c['input_bg']}; border: 1px solid {c['input_border']};
        border-radius: 5px; padding: 4px 8px; color: {c['text']};
        selection-background-color: {c['selection_bg']};
    }}
    QLineEdit:focus, QSpinBox:focus, QTextEdit:focus {{
        border: 1px solid {c['accent']};
    }}
    QLineEdit:disabled, QSpinBox:disabled {{
        background-color: {c['base']}; color: {c['subtext']};
        font-size: 11px;
    }}
    QLineEdit:read-only {{
        background-color: {c['base']}; color: {c['subtext']};
    }}

    QComboBox {{
        background-color: {c['input_bg']}; border: 1px solid {c['input_border']};
        border-radius: 5px; padding: 4px 8px; color: {c['text']}; min-height: 18px;
    }}
    QComboBox:focus {{ border: 1px solid {c['accent']}; }}
    QComboBox::drop-down {{ border: none; padding-right: 6px; }}
    QComboBox::down-arrow {{ width: 10px; height: 10px; }}
    QComboBox QAbstractItemView {{
        background-color: {c['input_bg']}; border: 1px solid {c['input_border']};
        border-radius: 5px; selection-background-color: {c['surface1']}; padding: 3px;
    }}

    QPushButton {{
        background-color: {c['btn_bg']}; border: 1px solid {c['btn_border']};
        border-radius: 5px; padding: 5px 12px; color: {c['text']};
        font-weight: 500; min-width: 60px;
    }}
    QPushButton:hover {{ background-color: {c['surface2']}; border-color: {c['overlay']}; }}
    QPushButton:pressed {{ background-color: {c['surface0']}; }}
    QPushButton:disabled {{
        background-color: {c['base']}; color: {c['overlay']};
        border-color: {c['surface0']};
    }}

    QTreeWidget {{
        background-color: {c['tree_bg']}; border: 1px solid {c['tree_border']};
        border-radius: 5px; padding: 2px; outline: none;
    }}
    QTreeWidget::item {{ padding: 4px 8px; border-radius: 3px; margin: 1px 2px; }}
    QTreeWidget::item:hover {{ background-color: {c['tree_hover']}; }}
    QTreeWidget::item:selected {{ background-color: {c['tree_selected']}; color: {c['text']}; }}

    QSplitter::handle {{ background-color: {c['splitter']}; width: 2px; }}
    QSplitter::handle:hover {{ background-color: {c['accent']}; }}

    QCheckBox {{ spacing: 8px; color: {c['text']}; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 2px solid {c['check_border']}; border-radius: 3px;
        background-color: {c['check_bg']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c['accent']}; border-color: {c['accent']};
    }}
    QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}

    QTableWidget {{
        background-color: {c['base']}; border: 1px solid {c['tree_border']};
        border-radius: 5px; gridline-color: {c['surface0']}; outline: none;
    }}
    QTableWidget::item {{ padding: 5px; }}
    QTableWidget::item:selected {{ background-color: {c['tree_selected']}; }}

    QProgressBar {{
        background-color: {c['progress_bg']}; border: none;
        border-radius: 3px; text-align: center; color: {c['text']};
    }}
    QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: 3px; }}

    QStatusBar {{
        background-color: {c['status_bg']}; border-top: 1px solid {c['status_border']};
        color: {c['subtext']}; padding: 2px;
    }}

    QDialogButtonBox QPushButton {{ min-width: 80px; }}
    """


def apply_theme(app: QApplication, theme: str):
    """Apply theme to application"""
    colors = DARK if theme == "dark" else LIGHT
    app.setStyle("Fusion")
    app.setPalette(_build_palette(colors))
    app.setStyleSheet(_build_stylesheet(colors))


def main():
    # Prevent KDE/Plasma from injecting platform button icons
    import os
    os.environ.pop("QT_QPA_PLATFORMTHEME", None)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_DontShowIconsInMenus, True)

    app = QApplication(sys.argv)
    app.setApplicationName("SSH Manager")
    app.setApplicationVersion("1.0.0")

    # Force empty icon theme to prevent garbled platform icons on Arch/Wayland
    from PyQt5.QtGui import QIcon
    QIcon.setThemeName("")

    config = ConfigManager()
    settings = config.get_app_settings()

    apply_theme(app, settings.theme)
    CloseableTabBar.set_theme(settings.theme)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
