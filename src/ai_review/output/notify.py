"""
System notifications — cross-platform, never crashes.

Windows strategy (in order):
  1. BurntToast PowerShell module — modern toast, customizable duration
  2. Windows Forms BalloonTip — built-in, but 5s max
  3. MessageBox — always works, blocks until dismissed
  4. Silent fallback — just print to stderr
"""

import sys
import subprocess
import time
from typing import Optional


class SystemNotifier:
    """Zero-config OS notification with cross-platform abstraction."""

    def notify(self, title: str, message: str, duration: int = 10):
        """Send system notification.

        Args:
            title: Notification title
            message: Notification body text
            duration: How long to show (seconds). Only effective on supported backends.
        """
        try:
            if sys.platform == "win32":
                self._notify_windows(title, message, duration)
            elif sys.platform == "darwin":
                self._notify_macos(title, message, duration)
            else:
                self._notify_linux(title, message, duration)
        except Exception:
            # Silently skip notification failures, but print to stderr
            self._print_fallback(title, message)

    def _notify_windows(self, title: str, message: str, duration: int):
        """Windows notification — try multiple backends."""
        # Escape quotes for PowerShell
        safe_title = title.replace('"', '`"').replace("'", "`'")
        safe_msg = message.replace('"', '`"').replace("'", "`'")
        # Truncate for notification limits
        safe_msg = self._truncate(safe_msg, 300)

        # 1. Try BurntToast (modern, supports duration)
        try:
            ps_script = f'''
New-BurntToastNotification -Text "{safe_title}", "{safe_msg}" -ExpirationTime (Get-Date).AddSeconds({duration})
'''
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, timeout=8, text=True,
                encoding="utf-8", errors="replace"
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

        # 2. Try Windows Forms BalloonTip
        try:
            ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Warning
$notify.BalloonTipTitle = "{safe_title}"
$notify.BalloonTipText = "{safe_msg}"
$notify.BalloonTipIcon = "Warning"
$notify.Visible = $true
$notify.ShowBalloonTip({duration * 1000})
Start-Sleep -Seconds {duration + 2}
$notify.Visible = $false
$notify.Dispose()
'''
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, timeout=duration + 10, text=True,
                encoding="utf-8", errors="replace"
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

        # 3. Fallback to console
        self._print_fallback(title, message)

    def _notify_macos(self, title: str, message: str, duration: int):
        """macOS: osascript display notification."""
        try:
            safe_title = title.replace('"', '\\"')
            safe_msg = self._truncate(message, 200).replace('"', '\\"')
            applescript = f'display notification "{safe_msg}" with title "{safe_title}"'
            subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True, timeout=5, text=True,
            )
        except Exception:
            self._print_fallback(title, message)

    def _notify_linux(self, title: str, message: str, duration: int):
        """Linux: notify-send."""
        try:
            safe_msg = self._truncate(message, 200)
            subprocess.run(
                ["notify-send", "-t", str(duration * 1000), title, safe_msg],
                capture_output=True, timeout=5, text=True,
            )
        except Exception:
            self._print_fallback(title, message)

    def _print_fallback(self, title: str, message: str):
        """Print to stderr as last resort."""
        print(f"\n🔔 {title}", file=sys.stderr)
        print(f"   {self._truncate(message, 200)}", file=sys.stderr)

    def _truncate(self, text: str, max_len: int = 200) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."
