"""
Session handlers for SSH and Serial connections
"""

import os
import socket
import threading
import time
from typing import Optional, Callable

import paramiko
import serial


class SSHSession:
    """Handles SSH connections"""
    
    def __init__(self, config: dict, on_data: Callable[[bytes], None], on_error: Callable[[str], None]):
        self.config = config
        self.on_data = on_data
        self.on_error = on_error
        
        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def connect(self) -> bool:
        """Establish SSH connection"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            hostname = self.config.get("host", "")
            port = self.config.get("port", 22)
            username = self.config.get("username", "")
            
            if not hostname:
                self.on_error("Host is not specified")
                return False
            
            if not username:
                self.on_error("Username is not specified")
                return False
            
            connect_kwargs = {
                "hostname": hostname,
                "port": port,
                "username": username,
                "timeout": 15,  # Reduced timeout
                "banner_timeout": 15,
                "auth_timeout": 15,
                "allow_agent": False,
                "look_for_keys": False,
            }
            
            password = self.config.get("password", "")
            key_file = self.config.get("key_file", "")
            
            if password:
                connect_kwargs["password"] = password
            if key_file and os.path.exists(key_file):
                connect_kwargs["key_filename"] = key_file
            
            if not password and not (key_file and os.path.exists(key_file)):
                self.on_error("No password or key file specified")
                return False
            
            # Build disabled_algorithms dict to ENABLE legacy algorithms
            # Paramiko by default disables insecure algorithms, we need to un-disable them
            disabled_algorithms = {}
            
            ciphers = self.config.get("ciphers", "")
            kex = self.config.get("kex", "")
            hostkeys = self.config.get("hostkeys", "")
            macs = self.config.get("macs", "")
            
            # If custom algorithms specified, we need to work with paramiko's security options
            if ciphers or kex or hostkeys or macs:
                # For legacy support, we tell paramiko not to disable these algorithms
                # by providing empty disabled lists
                disabled_algorithms = {
                    'ciphers': [],
                    'kex': [],
                    'keys': [],
                    'macs': [],
                }
                connect_kwargs['disabled_algorithms'] = disabled_algorithms
            
            self.client.connect(**connect_kwargs)
            
            # After connection, if we have specific algorithm preferences,
            # they would have been negotiated. For most legacy devices,
            # just allowing the algorithms (not disabling them) is enough.
            
            self.channel = self.client.invoke_shell(
                term='xterm-256color',
                width=self.config.get('_term_cols', 80),
                height=self.config.get('_term_rows', 24)
            )
            self.channel.settimeout(0.1)
            
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            
            return True
        
        except paramiko.AuthenticationException:
            self.on_error("Authentication failed - check username/password")
            return False
        except paramiko.SSHException as e:
            self.on_error(f"SSH error: {e}")
            return False
        except socket.timeout:
            self.on_error("Connection timed out - host unreachable")
            return False
        except socket.gaierror as e:
            self.on_error(f"DNS error - cannot resolve hostname: {e}")
            return False
        except ConnectionRefusedError:
            self.on_error("Connection refused - check host and port")
            return False
        except OSError as e:
            self.on_error(f"Network error: {e}")
            return False
        except Exception as e:
            self.on_error(f"Connection failed: {e}")
            return False
    
    def _read_loop(self):
        """Background thread reading from SSH channel"""
        while self.running and self.channel:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(4096)
                    if data:
                        self.on_data(data)
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    self.on_error(f"SSH read error: {e}")
                break
    
    def send(self, data: bytes):
        """Send data to SSH channel"""
        if self.channel:
            try:
                self.channel.send(data)
            except Exception as e:
                self.on_error(f"SSH send error: {e}")
    
    def resize(self, width: int, height: int):
        """Resize terminal (PTY window size)"""
        if self.channel:
            try:
                self.channel.resize_pty(width=width, height=height)
            except Exception:
                pass
    
    def disconnect(self):
        """Close SSH connection"""
        self.running = False
        
        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
            self.channel = None
        
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
    
    @property
    def is_connected(self) -> bool:
        return self.running and self.channel is not None


class SerialSession:
    """Handles Serial/TTY connections"""
    
    PARITY_MAP = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
        "M": serial.PARITY_MARK,
        "S": serial.PARITY_SPACE,
    }
    
    STOPBITS_MAP = {
        1: serial.STOPBITS_ONE,
        1.0: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2: serial.STOPBITS_TWO,
        2.0: serial.STOPBITS_TWO,
    }
    
    def __init__(self, config: dict, on_data: Callable[[bytes], None], on_error: Callable[[str], None]):
        self.config = config
        self.on_data = on_data
        self.on_error = on_error
        
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def connect(self) -> bool:
        """Establish serial connection"""
        try:
            parity = self.PARITY_MAP.get(
                self.config.get("parity", "N"), 
                serial.PARITY_NONE
            )
            stopbits = self.STOPBITS_MAP.get(
                self.config.get("stopbits", 1), 
                serial.STOPBITS_ONE
            )
            flow = self.config.get("flow_control", "none")
            
            self.serial_conn = serial.Serial(
                port=self.config.get("port", ""),
                baudrate=self.config.get("baudrate", 9600),
                bytesize=self.config.get("bytesize", 8),
                parity=parity,
                stopbits=stopbits,
                xonxoff=(flow == "xonxoff"),
                rtscts=(flow == "rtscts"),
                timeout=0.1
            )
            
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            
            return True
            
        except Exception as e:
            self.on_error(f"Serial connection failed: {e}")
            return False
    
    def _read_loop(self):
        """Background thread reading from serial port"""
        while self.running and self.serial_conn:
            try:
                if self.serial_conn.in_waiting:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    if data:
                        self.on_data(data)
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    self.on_error(f"Serial read error: {e}")
                break
    
    def send(self, data: bytes):
        """Send data to serial port"""
        if self.serial_conn:
            try:
                self.serial_conn.write(data)
            except Exception as e:
                self.on_error(f"Serial send error: {e}")
    
    def disconnect(self):
        """Close serial connection"""
        self.running = False
        
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None
    
    @property
    def is_connected(self) -> bool:
        return self.running and self.serial_conn is not None


def list_serial_ports() -> list:
    """List available serial ports"""
    import serial.tools.list_ports
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append({
            "device": port.device,
            "description": port.description,
            "hwid": port.hwid or ""
        })
    return ports
