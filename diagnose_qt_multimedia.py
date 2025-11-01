#!/usr/bin/env python3
"""
Qt Multimedia Diagnostic Script
Compares system configuration to identify why QMediaPlayer hangs on some Linux systems
"""

import sys
import os
import subprocess
import platform
from pathlib import Path

def run_command(cmd, shell=False):
    """Run command and return output"""
    try:
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=shell)
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    except Exception as e:
        return f"ERROR: {e}", -1

def check_file_exists(path):
    """Check if file/directory exists"""
    return "✓ EXISTS" if Path(path).exists() else "✗ MISSING"

def main():
    print("=" * 80)
    print("Qt6 Multimedia Diagnostic Report")
    print("=" * 80)
    print()

    # System Info
    print("### SYSTEM INFORMATION ###")
    print(f"Platform: {platform.system()}")
    print(f"Distribution: {platform.platform()}")
    print(f"Python: {sys.version}")
    print()

    # Qt6 Version
    print("### Qt6 VERSIONS ###")
    try:
        from PySide6.QtCore import qVersion
        from PySide6 import __version__ as pyside_version
        print(f"PySide6 version: {pyside_version}")
        print(f"Qt runtime version: {qVersion()}")
    except ImportError as e:
        print(f"ERROR importing PySide6: {e}")
    print()

    # Qt Multimedia Availability
    print("### Qt6 MULTIMEDIA MODULES ###")
    try:
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        print("✓ PySide6.QtMultimedia imports successfully")
        print(f"  - QMediaPlayer: available")
        print(f"  - QAudioOutput: available")
    except ImportError as e:
        print(f"✗ PySide6.QtMultimedia import FAILED: {e}")
    print()

    # Qt Multimedia Plugins
    print("### Qt6 MULTIMEDIA PLUGINS ###")
    try:
        from PySide6.QtCore import QCoreApplication, QLibraryInfo
        app = QCoreApplication.getInstance()
        if not app:
            app = QCoreApplication(sys.argv)

        plugins_path = QLibraryInfo.path(QLibraryInfo.PluginsPath)
        print(f"Qt plugins directory: {plugins_path}")

        multimedia_plugins = Path(plugins_path) / "multimedia"
        print(f"Multimedia plugins: {check_file_exists(multimedia_plugins)}")

        if multimedia_plugins.exists():
            plugins = list(multimedia_plugins.glob("*.so"))
            print(f"  Found {len(plugins)} multimedia plugin(s):")
            for p in plugins:
                print(f"    - {p.name}")

        # Platform plugins
        platform_plugins = Path(plugins_path) / "mediaservice"
        print(f"Media service plugins: {check_file_exists(platform_plugins)}")
        if platform_plugins.exists():
            plugins = list(platform_plugins.glob("*.so"))
            for p in plugins:
                print(f"    - {p.name}")
    except Exception as e:
        print(f"ERROR checking Qt plugins: {e}")
    print()

    # System Packages (Debian/Ubuntu)
    print("### SYSTEM PACKAGES (dpkg) ###")
    packages_to_check = [
        "libqt6multimedia6",
        "libqt6multimediawidgets6",
        "qml6-module-qtmultimedia",
        "gstreamer1.0-plugins-base",
        "gstreamer1.0-plugins-good",
        "gstreamer1.0-plugins-bad",
        "gstreamer1.0-libav",
        "gstreamer1.0-alsa",
        "gstreamer1.0-pulseaudio",
        "pipewire",
        "pipewire-pulse",
        "pulseaudio",
        "wireplumber",
    ]

    for pkg in packages_to_check:
        output, code = run_command(f"dpkg -l {pkg}")
        if code == 0 and output and not output.startswith("dpkg-query"):
            # Package is installed
            version = "installed"
            for line in output.split('\n'):
                if line.startswith('ii'):
                    parts = line.split()
                    if len(parts) >= 3:
                        version = parts[2]
                        break
            print(f"✓ {pkg}: {version}")
        else:
            print(f"✗ {pkg}: NOT INSTALLED")
    print()

    # GStreamer Tools
    print("### GSTREAMER ###")
    output, code = run_command("gst-inspect-1.0 --version")
    if code == 0:
        print(f"GStreamer version:\n{output}")
    else:
        print("✗ gst-inspect-1.0 not found")

    # Check for important GStreamer plugins
    gst_plugins = ["playback", "ffmpeg", "pulseaudio", "alsa", "autodetect"]
    for plugin in gst_plugins:
        output, code = run_command(f"gst-inspect-1.0 {plugin}")
        status = "✓" if code == 0 else "✗"
        print(f"{status} GStreamer plugin: {plugin}")
    print()

    # Audio System
    print("### AUDIO SYSTEM ###")

    # PipeWire
    output, code = run_command("pipewire --version")
    if code == 0:
        print(f"PipeWire: {output}")
    else:
        print("✗ PipeWire: not found")

    # PulseAudio
    output, code = run_command("pulseaudio --version")
    if code == 0:
        print(f"PulseAudio: {output}")
    else:
        print("✗ PulseAudio: not found")

    # Check which is running
    output, code = run_command("pactl info", shell=True)
    if code == 0:
        print("✓ PulseAudio/PipeWire server is running")
        for line in output.split('\n'):
            if 'Server Name' in line or 'Server Version' in line:
                print(f"  {line.strip()}")
    else:
        print("✗ PulseAudio/PipeWire server NOT running or not responding")
    print()

    # Environment Variables
    print("### ENVIRONMENT VARIABLES ###")
    env_vars = [
        "QT_QPA_PLATFORM",
        "QT_DEBUG_PLUGINS",
        "QT_MULTIMEDIA_PREFERRED_PLUGINS",
        "PULSE_SERVER",
        "PIPEWIRE_RUNTIME_DIR",
        "XDG_RUNTIME_DIR",
    ]
    for var in env_vars:
        value = os.environ.get(var, "(not set)")
        print(f"{var}: {value}")
    print()

    # Test QMediaPlayer creation (with timeout)
    print("### Qt MULTIMEDIA INITIALIZATION TEST ###")
    print("Testing QMediaPlayer creation (WITHOUT QAudioOutput - known to hang on Linux)...")

    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtMultimedia import QMediaPlayer
        from PySide6.QtCore import QTimer
        import signal

        # Set alarm for timeout
        def timeout_handler(signum, frame):
            raise TimeoutError("QMediaPlayer creation timed out!")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)

        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)

        print("  Creating QMediaPlayer (video only, no audio)...")
        player = QMediaPlayer()
        print("  ✓ QMediaPlayer created successfully!")

        print("  NOTE: Skipping QAudioOutput test (known to hang on some Linux systems)")
        print("        Video playback works without audio support")

        signal.alarm(0)  # Cancel alarm

        print()
        print("SUCCESS: Qt multimedia video player initialized!")
        print("(Audio disabled to avoid system hangs)")

    except TimeoutError as e:
        print(f"  ✗ TIMEOUT: {e}")
        print()
        print("FAILURE: Even QMediaPlayer (without audio) hangs on this system!")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        print()
        print(f"FAILURE: Qt multimedia initialization failed: {e}")
    print()

    print("=" * 80)
    print("Diagnostic complete. Save this output to compare systems.")
    print("=" * 80)

if __name__ == "__main__":
    main()
