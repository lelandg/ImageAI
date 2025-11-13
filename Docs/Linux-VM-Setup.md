# Linux VM Setup for ImageAI Testing

This guide explains how to set up and test ImageAI on a Linux VM.

## Prerequisites

- Python 3.10 or higher
- Git
- Access to the shared `_transfer` folder for logs

## Installation Steps

### 1. Navigate to the Project Directory

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI
```

### 2. Create a Linux Virtual Environment

```bash
python3 -m venv .venv_linux
```

### 3. Activate the Virtual Environment

```bash
source .venv_linux/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: The `opencv-python` package is now included in requirements.txt as it's required for video creation features.

### 5. Verify Installation

Check that all required packages are installed:

```bash
pip list | grep -E "opencv|moviepy|Pillow|PySide6"
```

You should see:
- `opencv-python` (version 4.8.0 or higher)
- `moviepy` (for video processing)
- `Pillow` (for image handling)
- `PySide6` (for GUI, if testing GUI features)

## Running Tests

### Test Basic Functionality

```bash
# Show help
python3 main.py -h

# Test API (if you have keys configured)
python3 main.py -t
```

### Test Video Creation

Video creation requires:
1. A video project file (`.json`)
2. Generated images for each scene
3. OpenCV (`cv2`) for frame processing

```bash
# Example: Load and process a video project
python3 main.py --video-project path/to/project.json
```

## Debugging

### Check Logs

Logs are automatically copied to the `_transfer` folder for cross-platform access:

```bash
# View the latest log
cat _transfer/imageai_current.log

# Search for errors
grep -i "error\|exception" _transfer/imageai_current.log
```

### Common Issues

#### Missing cv2 Module

**Error**: `ModuleNotFoundError: No module named 'cv2'`

**Solution**:
```bash
source .venv_linux/bin/activate
pip install opencv-python>=4.8.0
```

#### PySide6 Installation Issues

If you don't need GUI features on Linux, you can skip PySide6:

```bash
# Install only CLI dependencies
pip install google-genai openai pillow requests moviepy opencv-python
```

#### Virtual Environment Not Activating

If `source .venv_linux/bin/activate` doesn't work:

```bash
# Use the full path to Python
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python3 main.py -h
```

## Configuration

### API Keys

API keys can be configured in several ways (in order of precedence):

1. **Environment variables**: `GOOGLE_API_KEY`, `OPENAI_API_KEY`
2. **User config directory**: `~/.config/ImageAI/config.json`
3. **Project config**: Generated via GUI settings or CLI prompts

### Cross-Platform Testing

The `_transfer` folder is shared between Windows and Linux environments:

- **Logs**: Automatically copied to `_transfer/imageai_current.log`
- **Test files**: Place test images, projects, etc. in `_transfer/` for easy access
- **Results**: Generated videos can be saved to `_transfer/` for viewing on Windows

## Limitations

### GUI Testing on Linux

The GUI requires:
- X11 or Wayland display server
- Qt platform plugins

If running headless or in WSL without X11:
- Use CLI mode only
- Test GUI features on Windows instead

### GPU Acceleration

- OpenCV uses CPU by default on Linux
- For GPU acceleration, install `opencv-python-headless` with CUDA support
- Video processing will be slower than on Windows with GPU

## Development Workflow

### Typical Test Cycle

1. **Edit code on Windows** (using PyCharm/IDE)
2. **Test on Linux VM**:
   ```bash
   cd /mnt/d/Documents/Code/GitHub/ImageAI
   source .venv_linux/bin/activate
   python3 main.py -t  # or other test commands
   ```
3. **Check logs** in `_transfer/imageai_current.log`
4. **Review results** on Windows (for generated images/videos)

### Keeping Environments in Sync

When dependencies change:

```bash
# On Linux
source .venv_linux/bin/activate
pip install -r requirements.txt --upgrade
```

## See Also

- **CodeMap.md**: Complete code navigation with line numbers
- **README.md**: General usage and features
- **Plans/**: Feature development plans and specifications
