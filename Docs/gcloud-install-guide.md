# Google Cloud SDK (gcloud CLI) Installation & Setup Guide

*Last Updated: 2025-01-04*

This guide covers installing the Google Cloud SDK (gcloud CLI) on Linux, macOS, and Windows (PowerShell), including authentication and project configuration.

## Table of Contents
1. [Quick Start](#quick-start)
2. [System Requirements](#system-requirements)
3. [Linux Installation](#linux-installation)
4. [macOS Installation](#macos-installation)
5. [Windows Installation (PowerShell)](#windows-installation-powershell)
6. [Authentication & Project Setup](#authentication--project-setup)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

---

## Quick Start

### Universal Steps (All Platforms)

After platform-specific installation:

```bash
# 1. Initialize gcloud (handles login and project setup)
gcloud init

# 2. Or set project directly if already authenticated
gcloud config set project YOUR-PROJECT-ID

# 3. Verify installation
gcloud version
gcloud auth list
gcloud config list
```

---

## System Requirements

- **Python**: 3.9 to 3.14 (3.9 support ends January 2026)
- **Operating Systems**:
  - Linux: Any modern distribution
  - macOS: 10.9+ (Intel or Apple Silicon)
  - Windows: 8.1+ or Server 2012+
- **Disk Space**: ~150MB for x86_64, ~60MB for ARM

---

## Linux Installation

### Option 1: Quick Install (x86_64)

```bash
# Download archive (150.7 MB)
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz

# Extract
tar -xf google-cloud-cli-linux-x86_64.tar.gz

# Install (adds to PATH, enables completion)
./google-cloud-sdk/install.sh

# Open new terminal, then initialize
gcloud init
```

### Option 2: Package Manager (Debian/Ubuntu)

```bash
# Add Google Cloud's GPG key
sudo apt-get install apt-transport-https ca-certificates gnupg curl
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

# Add repository
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Install
sudo apt-get update && sudo apt-get install google-cloud-cli

# Initialize
gcloud init
```

### Option 3: Package Manager (Red Hat/Fedora/CentOS)

```bash
# Configure repository
sudo tee -a /etc/yum.repos.d/google-cloud-sdk.repo << EOM
[google-cloud-cli]
name=Google Cloud CLI
baseurl=https://packages.cloud.google.com/yum/repos/cloud-sdk-el9-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
EOM

# Install
sudo dnf install google-cloud-cli

# Initialize
gcloud init
```

### ARM/32-bit Linux

```bash
# For ARM (57.2 MB)
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-arm.tar.gz

# For 32-bit x86 (57.3 MB)
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86.tar.gz

# Extract and install (same process as x86_64)
tar -xf google-cloud-cli-linux-*.tar.gz
./google-cloud-sdk/install.sh
```

---

## macOS Installation

### Step 1: Check Your Architecture

```bash
# Returns 'arm64' for Apple Silicon, 'x86_64' for Intel
uname -m
```

### Step 2: Download & Install

#### For Apple Silicon (M1/M2/M3)

```bash
# Download ARM version (57.3 MB)
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-arm.tar.gz

# Extract
tar -xf google-cloud-cli-darwin-arm.tar.gz

# Install
./google-cloud-sdk/install.sh

# Initialize (in new terminal)
gcloud init
```

#### For Intel Macs

```bash
# Download x86_64 version (57.3 MB)
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-x86_64.tar.gz

# Extract
tar -xf google-cloud-cli-darwin-x86_64.tar.gz

# Install
./google-cloud-sdk/install.sh

# Initialize (in new terminal)
gcloud init
```

### macOS Notes

- Installation script offers to install Python 3.13 if needed
- May require Xcode Command Line Tools: `xcode-select --install`
- Works with both bash and zsh (default since Catalina)

---

## Windows Installation (PowerShell)

### Option 1: GUI Installer (Recommended)

1. Download: [GoogleCloudSDKInstaller.exe](https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe)
2. Run installer (double-click)
3. Keep defaults selected:
   - ✅ Install Python bundle
   - ✅ Start Cloud SDK Shell
   - ✅ Run gcloud init
4. Follow initialization prompts

### Option 2: PowerShell Automated

```powershell
# Download installer
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:Temp\GoogleCloudSDKInstaller.exe")

# Run installer
& $env:Temp\GoogleCloudSDKInstaller.exe
```

### PowerShell 7 Compatibility

If using PowerShell 7+, add to your profile:

```powershell
# Edit profile
notepad $PROFILE

# Add this line:
$PSNativeCommandArgumentPassing = "Legacy"

# Save and reload
. $PROFILE
```

### Windows Notes

- Installer includes bundled Python (recommended)
- Automatically adds to PATH
- Default location: `%LOCALAPPDATA%\Google\Cloud SDK`
- Config stored in: `%APPDATA%\gcloud`

---

## Authentication & Project Setup

### Method 1: Interactive Setup (Recommended for First Time)

```bash
gcloud init
```

This interactive wizard:
1. Prompts for Google account login
2. Lists available projects
3. Sets default project
4. Optionally configures default compute region/zone

### Method 2: Manual Configuration

#### Step 1: Authenticate

```bash
# Browser-based login (opens browser automatically)
gcloud auth login

# For remote/SSH sessions (provides URL to open manually)
gcloud auth login --no-launch-browser
```

#### Step 2: Set Project ID

```bash
# Set project (use project ID, not display name)
gcloud config set project YOUR-PROJECT-ID

# Example
gcloud config set project my-project-123456
```

#### Step 3: Verify Configuration

```bash
# Show current configuration
gcloud config list

# Show just the project
gcloud config get-value project
```

### Method 3: Application Default Credentials

For applications using Google Cloud client libraries:

```bash
# Set up ADC for local development
gcloud auth application-default login
```

This creates credentials at:
- Linux/macOS: `~/.config/gcloud/application_default_credentials.json`
- Windows: `%APPDATA%\gcloud\application_default_credentials.json`

### Using Service Accounts (Production)

**Recommended: Service Account Impersonation**

```bash
# Login with your user account first
gcloud auth login

# Impersonate service account (no key file needed)
gcloud config set auth/impersonate_service_account SA-NAME@PROJECT.iam.gserviceaccount.com
```

**Alternative: Workload Identity Federation (Best for CI/CD)**

```bash
# Authenticate using external credentials (AWS, Azure, etc.)
gcloud auth login --cred-file=path/to/config.json
```

**Avoid: Service Account Keys (Security Risk)**

```bash
# Only if no other option - keys are security risk!
gcloud auth activate-service-account --key-file=path/to/key.json
```

---

## Managing Multiple Projects

### Using Configurations

Create separate configurations for different projects/environments:

```bash
# Create configuration for work project
gcloud config configurations create work
gcloud config set project work-project-id
gcloud config set account work@company.com

# Create configuration for personal project
gcloud config configurations create personal
gcloud config set project personal-project-id
gcloud config set account personal@gmail.com

# List configurations
gcloud config configurations list

# Switch between configurations
gcloud config configurations activate work
gcloud config configurations activate personal

# Use specific configuration for one command
gcloud compute instances list --configuration=work
```

### Environment Variables

```bash
# Override project for session
export CLOUDSDK_CORE_PROJECT=my-project-id

# Override configuration
export CLOUDSDK_ACTIVE_CONFIG_NAME=work
```

---

## Verification

### Essential Verification Commands

```bash
# 1. Check version
gcloud version

# 2. Show authenticated accounts
gcloud auth list

# 3. Show current configuration
gcloud config list

# 4. Show current project
gcloud config get-value project

# 5. List accessible projects
gcloud projects list

# 6. Run diagnostics
gcloud info --run-diagnostics
```

### Complete Verification Script

```bash
#!/bin/bash

echo "=== Google Cloud SDK Verification ==="
echo ""

echo "1. Version:"
gcloud version --format="value(version.version_string)"

echo ""
echo "2. Active Account:"
gcloud config get-value account

echo ""
echo "3. Active Project:"
gcloud config get-value project

echo ""
echo "4. Configuration:"
gcloud config list

echo ""
echo "5. Network Connectivity:"
gcloud compute zones list --limit=1 &>/dev/null && echo "✓ Connected to Google Cloud" || echo "✗ Connection failed"

echo ""
echo "=== Verification Complete ==="
```

---

## Troubleshooting

### Common Issues & Solutions

#### "gcloud: command not found"

**Linux/macOS:**
```bash
# Re-run install script
./google-cloud-sdk/install.sh

# Or manually add to PATH
echo 'export PATH="$HOME/google-cloud-sdk/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Windows:**
- Restart PowerShell/terminal after installation
- Run installer again and ensure PATH option is selected

#### Python Issues

**"Python interpreter not found"**

```bash
# Linux/macOS - Set Python explicitly
export CLOUDSDK_PYTHON=/usr/bin/python3

# Windows PowerShell
$env:CLOUDSDK_PYTHON = "C:\Python312\python.exe"
```

**Multiple Python versions:**

```bash
# Check which Python gcloud is using
gcloud info --format="value(config.paths.global_config_dir)"

# Force specific version
export CLOUDSDK_PYTHON=/path/to/preferred/python3
```

#### Authentication Issues

**"You do not currently have an active account selected"**

```bash
# Re-authenticate
gcloud auth login

# Or set active account
gcloud config set account your-email@example.com
```

**"The caller does not have permission"**

```bash
# Verify correct project
gcloud config get-value project

# Switch project if needed
gcloud config set project correct-project-id

# Check your permissions in Cloud Console
```

#### Network/Proxy Issues

**Behind corporate proxy:**

```bash
# Set proxy configuration
gcloud config set proxy/type http
gcloud config set proxy/address proxy.company.com
gcloud config set proxy/port 8080

# With authentication
gcloud config set proxy/username your-username
gcloud config set proxy/password your-password
```

#### PowerShell 7 Issues

```powershell
# Temporary fix
$PSNativeCommandArgumentPassing = "Legacy"

# Permanent fix - add to profile
Add-Content $PROFILE '$PSNativeCommandArgumentPassing = "Legacy"'
```

### Debug Commands

```bash
# Verbose output for debugging
gcloud compute instances list --verbosity=debug

# Show gcloud info and paths
gcloud info

# Show log file location
gcloud info --show-log

# Test network connectivity
gcloud compute zones list --limit=1
```

---

## Best Practices

### For Development

1. **Use `gcloud init`** for initial setup
2. **Create configurations** for different projects/environments
3. **Use user account** authentication (not service accounts)
4. **Enable command completion** for better CLI experience
5. **Set explicit project** to avoid mistakes

### For Production/CI/CD

1. **Use Workload Identity** or service account impersonation
2. **Never use service account key files** (security risk)
3. **Set project explicitly** in scripts: `--project=PROJECT_ID`
4. **Use JSON output** for parsing: `--format=json`
5. **Disable prompts** for automation: `gcloud config set core/disable_prompts true`

### Security

1. **Never commit credentials** to version control
2. **Use principle of least privilege** for IAM
3. **Rotate credentials regularly**: `gcloud auth revoke && gcloud auth login`
4. **Audit access**: Review `gcloud auth list` periodically
5. **Use short-lived tokens** when possible

### Team Collaboration

1. **Document project IDs** clearly (not just display names)
2. **Share configuration templates** for consistency
3. **Use organization policies** to enforce security
4. **Create setup scripts** for new team members
5. **Document required IAM roles** for tasks

---

## Quick Reference

```bash
# Authentication
gcloud auth login                    # Interactive login
gcloud auth login --no-launch-browser # For SSH sessions
gcloud auth list                     # List accounts
gcloud auth revoke                   # Logout

# Configuration
gcloud init                          # Full setup wizard
gcloud config list                   # Show configuration
gcloud config set project PROJECT_ID # Set project
gcloud config configurations list    # List all configs
gcloud config configurations activate NAME # Switch config

# Projects
gcloud projects list                 # List accessible projects
gcloud config get-value project      # Show current project

# Updates
gcloud components update             # Update SDK
gcloud components list              # List components
gcloud components install COMPONENT # Install component

# Help
gcloud help                         # General help
gcloud compute instances create --help # Command-specific help
```

---

## Additional Resources

- **Official Installation Guide**: https://cloud.google.com/sdk/docs/install
- **Authentication Guide**: https://cloud.google.com/sdk/docs/authorizing
- **Command Reference**: https://cloud.google.com/sdk/gcloud/reference
- **Configuration Guide**: https://cloud.google.com/sdk/docs/configurations
- **Support**: Stack Overflow tag `google-cloud-sdk`

---

*Note: This guide is based on Google Cloud SDK documentation as of January 2025. Always refer to official documentation for the latest updates.*