"""
Data models for SSH Manager
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from enum import Enum
import json
import uuid
from pathlib import Path


class ConnectionType(Enum):
    SSH = "ssh"
    SERIAL = "serial"


# Default terminal settings
DEFAULT_TERMINAL_SETTINGS = {
    'bg_color': '#1e1e2e',
    'fg_color': '#cdd6f4',
    'cursor_color': '#f5e0dc',
    'font_family': '',
    'font_size': 11,
    'syntax_highlight': True,
}

# Default logging settings
DEFAULT_LOGGING_SETTINGS = {
    'enabled': False,
    'log_dir': '',  # Empty = default (~/.config/ssh_manager/logs)
    'timestamp_format': '%Y-%m-%d_%H-%M-%S',
    'include_date_prefix': True,
}


@dataclass
class AppSettings:
    """Application-wide settings"""
    theme: str = "dark"  # "dark" or "light"
    default_terminal: Dict = field(default_factory=lambda: DEFAULT_TERMINAL_SETTINGS.copy())
    logging: Dict = field(default_factory=lambda: DEFAULT_LOGGING_SETTINGS.copy())


@dataclass
class SSHConfig:
    """SSH connection configuration"""
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    key_file: str = ""
    # Security settings
    security_preset: str = "Modern (default)"
    ciphers: str = ""
    kex: str = ""
    hostkeys: str = ""
    macs: str = ""
    # Terminal settings
    terminal: Dict = field(default_factory=lambda: DEFAULT_TERMINAL_SETTINGS.copy())
    # Legacy (kept for compatibility)
    use_legacy_ciphers: bool = False
    legacy_ciphers: List[str] = field(default_factory=list)
    legacy_kex: List[str] = field(default_factory=list)
    legacy_host_keys: List[str] = field(default_factory=list)


@dataclass  
class SerialConfig:
    """Serial/TTY connection configuration"""
    port: str = ""
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1.0
    flow_control: str = "none"


@dataclass
class Connection:
    """Connection entry"""
    id: str = ""
    name: str = ""
    conn_type: str = "ssh"
    folder_id: str = ""
    ssh_config: Optional[Dict] = None
    serial_config: Optional[Dict] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if self.ssh_config is None:
            self.ssh_config = asdict(SSHConfig())
        if self.serial_config is None:
            self.serial_config = asdict(SerialConfig())
    
    def get_ssh_config(self) -> SSHConfig:
        return SSHConfig(**self.ssh_config)
    
    def get_serial_config(self) -> SerialConfig:
        return SerialConfig(**self.serial_config)


@dataclass
class Folder:
    """Folder for organizing connections"""
    id: str = ""
    name: str = ""
    parent_id: str = ""
    expanded: bool = True
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]


class ConfigManager:
    """Manages configuration storage"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path.home() / ".config" / "ssh_manager" / "config.json"
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self) -> Dict:
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"folders": [], "connections": [], "settings": {}}
    
    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_app_settings(self) -> AppSettings:
        """Get application settings"""
        settings_data = self.data.get("settings", {})
        return AppSettings(
            theme=settings_data.get("theme", "dark"),
            default_terminal=settings_data.get("default_terminal", DEFAULT_TERMINAL_SETTINGS.copy()),
            logging=settings_data.get("logging", DEFAULT_LOGGING_SETTINGS.copy())
        )
    
    def update_app_settings(self, settings: AppSettings):
        """Update application settings"""
        self.data["settings"] = asdict(settings)
        self.save()
    
    def get_default_terminal_settings(self) -> Dict:
        """Get default terminal settings for new connections"""
        settings = self.get_app_settings()
        return settings.default_terminal.copy()
    
    def get_log_directory(self) -> Path:
        """Get directory for session logs"""
        settings = self.get_app_settings()
        log_dir = settings.logging.get('log_dir', '')
        
        if log_dir:
            path = Path(log_dir)
        else:
            path = self.config_path.parent / "logs"
        
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_folders(self) -> List[Folder]:
        return [Folder(**f) for f in self.data.get("folders", [])]
    
    def get_connections(self) -> List[Connection]:
        return [Connection(**c) for c in self.data.get("connections", [])]
    
    def add_folder(self, folder: Folder):
        self.data.setdefault("folders", []).append(asdict(folder))
        self.save()
    
    def update_folder(self, folder: Folder):
        folders = self.data.get("folders", [])
        for i, f in enumerate(folders):
            if f["id"] == folder.id:
                folders[i] = asdict(folder)
                break
        self.save()
    
    def delete_folder(self, folder_id: str):
        # Delete folder and move children to root
        self.data["folders"] = [
            f for f in self.data.get("folders", [])
            if f["id"] != folder_id
        ]
        # Update connections in this folder
        for c in self.data.get("connections", []):
            if c.get("folder_id") == folder_id:
                c["folder_id"] = ""
        # Update subfolders
        for f in self.data.get("folders", []):
            if f.get("parent_id") == folder_id:
                f["parent_id"] = ""
        self.save()
    
    def add_connection(self, conn: Connection):
        self.data.setdefault("connections", []).append(asdict(conn))
        self.save()
    
    def update_connection(self, conn: Connection):
        connections = self.data.get("connections", [])
        for i, c in enumerate(connections):
            if c["id"] == conn.id:
                connections[i] = asdict(conn)
                break
        self.save()
    
    def delete_connection(self, conn_id: str):
        self.data["connections"] = [
            c for c in self.data.get("connections", [])
            if c["id"] != conn_id
        ]
        self.save()
    
    def get_connection_by_id(self, conn_id: str) -> Optional[Connection]:
        for c in self.data.get("connections", []):
            if c["id"] == conn_id:
                return Connection(**c)
        return None
    
    def get_folder_by_id(self, folder_id: str) -> Optional[Folder]:
        for f in self.data.get("folders", []):
            if f["id"] == folder_id:
                return Folder(**f)
        return None
