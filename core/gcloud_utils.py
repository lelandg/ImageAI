"""Google Cloud authentication utilities."""

import subprocess
import platform
import os
from typing import Optional, Tuple
from pathlib import Path

# Check if Google Cloud AI Platform is available
try:
    from google.cloud import aiplatform
    from google.auth import default as google_auth_default
    from google.auth.exceptions import DefaultCredentialsError
    GCLOUD_AVAILABLE = True
except ImportError:
    aiplatform = None
    google_auth_default = None
    DefaultCredentialsError = Exception
    GCLOUD_AVAILABLE = False


def find_gcloud_command() -> Optional[str]:
    """Find the gcloud command on various platforms."""
    system = platform.system()
    
    # On Windows, try where.exe first
    if system == "Windows":
        try:
            result = subprocess.run(
                ["where.exe", "gcloud"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                paths = result.stdout.strip().split('\n')
                if paths and paths[0]:
                    return paths[0]  # Return first found path
        except Exception:
            pass
        
        # Try common Windows installation paths
        common_paths = [
            r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
            r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
            os.path.expanduser(r"~\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"),
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
    
    # On WSL, check for both Linux gcloud and Windows gcloud
    elif "microsoft" in platform.uname().release.lower():
        # First try Linux gcloud
        try:
            result = subprocess.run(
                ["which", "gcloud"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        # Then try Windows gcloud from WSL
        wsl_paths = [
            "/mnt/c/Program Files/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd",
            "/mnt/c/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd",
        ]
        # Also check user directories
        if os.path.exists("/mnt/c/Users/"):
            for user_dir in os.listdir("/mnt/c/Users/"):
                user_gcloud = f"/mnt/c/Users/{user_dir}/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd"
                if os.path.exists(user_gcloud):
                    wsl_paths.append(user_gcloud)
        
        for path in wsl_paths:
            if os.path.exists(path):
                return path
    
    # Default Unix/Linux/Mac
    else:
        try:
            result = subprocess.run(
                ["which", "gcloud"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
    
    return None


def get_gcloud_project_id() -> Optional[str]:
    """Get the current Google Cloud project ID."""
    if not GCLOUD_AVAILABLE:
        return None
    try:
        gcloud_cmd = find_gcloud_command()
        if not gcloud_cmd:
            return None
        
        result = subprocess.run(
            [gcloud_cmd, "config", "get-value", "project"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=(platform.system() == "Windows")  # Use shell on Windows for .cmd files
        )
        if result.returncode == 0:
            project_id = result.stdout.strip()
            if project_id and project_id != "(unset)":
                return project_id
    except Exception:
        pass
    return None


def check_gcloud_auth_status() -> Tuple[bool, str]:
    """Check if gcloud is authenticated. Returns (is_authenticated, status_message)."""
    if not GCLOUD_AVAILABLE:
        return False, "Google Cloud AI Platform library not installed. Run: pip install google-cloud-aiplatform"
    
    try:
        gcloud_cmd = find_gcloud_command()
        if not gcloud_cmd:
            system = platform.system()
            if system == "Windows":
                return False, ("Google Cloud CLI not found. Please:\n"
                              "1. Install from: https://cloud.google.com/sdk/docs/install\n"
                              "2. Restart your terminal/PowerShell\n"
                              "3. Run: gcloud auth application-default login")
            elif "microsoft" in platform.uname().release.lower():
                return False, ("Google Cloud CLI not found. Either:\n"
                              "1. Install in WSL: sudo snap install google-cloud-cli --classic\n"
                              "2. Or run from PowerShell where gcloud is installed")
            else:
                return False, "Google Cloud CLI not installed. Visit: https://cloud.google.com/sdk/docs/install"
        
        # Check authentication status
        result = subprocess.run(
            [gcloud_cmd, "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=(platform.system() == "Windows")  # Use shell on Windows for .cmd files
        )
        
        if result.returncode == 0:
            # Also check if APIs are enabled
            project_id = get_gcloud_project_id()
            if project_id:
                return True, f"Authenticated with Google Cloud (Project: {project_id})"
            else:
                return True, "Authenticated with Google Cloud (No project set)"
        else:
            # Check specific error messages
            if result.stderr:
                stderr_lower = result.stderr.lower()
                if "quota project" in stderr_lower:
                    return False, ("Authentication found but quota project not set.\n"
                                  "Run: gcloud auth application-default set-quota-project YOUR_PROJECT_ID")
                elif "could not find default credentials" in stderr_lower:
                    return False, ("Not authenticated. Please run:\n"
                                  "gcloud auth application-default login")
            else:
                return False, ("Not authenticated. Please run:\n"
                              "gcloud auth application-default login\n\n"
                              "This will open your browser to authenticate.")
    except subprocess.TimeoutExpired:
        return False, "Timeout checking authentication. gcloud may be updating or slow."
    except Exception as e:
        return False, f"Error checking authentication: {str(e)}"