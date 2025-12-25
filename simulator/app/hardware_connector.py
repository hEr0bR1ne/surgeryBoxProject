"""
Hardware Connector Module
Handles communication with ESP8266 simulator hardware
"""

import socket
import subprocess
import re
import json
import threading
from typing import Tuple, Optional
from PySide6.QtCore import QThread, Signal


class HardwareConnector:
    """Manages connection to ESP8266 simulator hardware"""
    
    BOARD_URL = "http://192.168.4.1/echo"  # Fixed board IP and port
    BOARD_IP = "192.168.4.1"
    BOARD_PORT = 80
    TIMEOUT = 3  # seconds
    
    def __init__(self):
        self.current_wifi = None
        self.connection_status = False
    
    @staticmethod
    def get_current_wifi() -> Optional[str]:
        """
        Get the name of currently connected WiFi network
        Works on Windows, macOS, and Linux with timeout protection
        """
        try:
            # Try Windows first with adequate timeout (netsh can be slow)
            try:
                result = subprocess.run(
                    ["netsh", "wlan", "show", "interfaces"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                
                if result.returncode == 0 and result.stdout:
                    lines = result.stdout.split('\n')
                    # Look for SSID line
                    for line in lines:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            # Match SSID key
                            if key.upper() == 'SSID':
                                if value and value.lower() not in ["", "ssid", "unknown"]:
                                    return value
                    return None
            except subprocess.TimeoutExpired:
                pass
            except FileNotFoundError:
                pass
            except Exception:
                pass
            
            # Try macOS
            try:
                result = subprocess.run(
                    ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.split('\n'):
                        if 'SSID:' in line:
                            ssid = line.split(':', 1)[1].strip()
                            if ssid and ssid != "<unknown>":
                                return ssid
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass
            
            # Try Linux
            try:
                result = subprocess.run(
                    ["iwconfig"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout:
                    match = re.search(r'ESSID:"([^"]*)"', result.stdout)
                    if match:
                        return match.group(1)
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass
            
            return None
        except Exception:
            return None
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to hardware board using HTTP socket communication
        Returns: (success: bool, message: str)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.TIMEOUT)
            
            try:
                # Connect to board
                sock.connect((self.BOARD_IP, self.BOARD_PORT))
                
                # Prepare HTTP POST request
                command = "Hello"
                http_request = (
                    f"POST /echo HTTP/1.1\r\n"
                    f"Host: {self.BOARD_IP}\r\n"
                    f"Content-Type: text/plain\r\n"
                    f"Content-Length: {len(command)}\r\n"
                    f"Connection: close\r\n"
                    f"\r\n"
                    f"{command}"
                )
                
                sock.sendall(http_request.encode('utf-8'))
                
                # Receive response with timeout
                response_data = b""
                sock.settimeout(self.TIMEOUT)
                
                try:
                    while True:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        response_data += chunk
                except socket.timeout:
                    # Timeout is expected when server closes connection
                    pass
                
                # Decode response
                response_str = response_data.decode('utf-8', errors='ignore')
                
                # Check if response contains our command (case-insensitive)
                if "hello" in response_str.lower():
                    self.connection_status = True
                    return True, "Connection Successful"
                elif len(response_data) > 0:
                    # Got some response but no echo
                    if '\r\n\r\n' in response_str:
                        body = response_str.split('\r\n\r\n', 1)[1]
                    elif '\n\n' in response_str:
                        body = response_str.split('\n\n', 1)[1]
                    else:
                        body = response_str[-100:]
                    
                    if "hello" in body.lower():
                        self.connection_status = True
                        return True, "Connection Successful"
                    else:
                        return False, f"Response received but no echo"
                else:
                    return False, "No response from board"
            
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
        
        except socket.timeout:
            return False, "Connection timeout (3s) - board not responding"
        except ConnectionRefusedError:
            return False, "Connection refused - check board IP (192.168.4.1)"
        except Exception as e:
            error_msg = str(e)[:100]
            return False, f"Error: {error_msg}"
    
    def send_command(self, command: str) -> Tuple[bool, str]:
        """
        Send a command to the hardware board via HTTP
        Returns: (success: bool, response: str)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.TIMEOUT)
            
            try:
                sock.connect((self.BOARD_IP, self.BOARD_PORT))
                
                # Prepare HTTP POST request
                http_request = (
                    f"POST /echo HTTP/1.1\r\n"
                    f"Host: {self.BOARD_IP}\r\n"
                    f"Content-Type: text/plain\r\n"
                    f"Content-Length: {len(command)}\r\n"
                    f"Connection: close\r\n"
                    f"\r\n"
                    f"{command}"
                )
                
                sock.sendall(http_request.encode('utf-8'))
                
                # Receive response
                response_data = b""
                try:
                    while True:
                        chunk = sock.recv(1024)
                        if not chunk:
                            break
                        response_data += chunk
                except socket.timeout:
                    pass
                
                response_str = response_data.decode('utf-8', errors='ignore')
                
                # Extract response body
                if '\r\n\r\n' in response_str:
                    body = response_str.split('\r\n\r\n', 1)[1]
                else:
                    body = response_str
                
                return True, body
            
            finally:
                sock.close()
        
        except Exception as e:
            return False, f"Error: {str(e)}"


class WiFiThread(QThread):
    """Thread to get WiFi name without blocking UI"""
    wifi_ready = Signal(str)  # Emits WiFi name or "Unknown"
    
    def run(self):
        try:
            wifi_name = HardwareConnector.get_current_wifi()
            if wifi_name and wifi_name.strip():
                self.wifi_ready.emit(wifi_name)
            else:
                self.wifi_ready.emit("Not connected")
        except Exception:
            self.wifi_ready.emit("Not connected")


class ConnectionTestThread(QThread):
    """Thread to test connection without blocking UI"""
    connection_result = Signal(bool, str)  # (success, message)
    
    def run(self):
        try:
            connector = HardwareConnector()
            success, message = connector.test_connection()
            self.connection_result.emit(success, message)
        except Exception as e:
            self.connection_result.emit(False, f"Error: {str(e)[:50]}")

