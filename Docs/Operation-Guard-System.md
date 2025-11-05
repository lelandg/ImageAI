# Operation Guard System for Dialogs

## Overview

The Operation Guard System prevents crashes and race conditions when users attempt to trigger multiple simultaneous async operations in dialogs (e.g., pressing Ctrl+Enter multiple times while an LLM request is processing).

## Architecture

### Core Components (in `gui/dialog_utils.py`)

1. **`OperationGuardMixin`**: Base mixin class that provides operation state tracking and input blocking
2. **`InputBlockerEventFilter`**: Qt event filter that blocks all user input during operations
3. **`@guard_operation`**: Decorator that guards methods from being called during active operations

### How It Works

1. **Before Operation Starts**:
   - Decorator checks if an operation is already running
   - If running, shows warning in status console and blocks the call
   - If not running, allows the operation to proceed

2. **During Operation**:
   - `start_operation()` is called to mark operation as active
   - Event filter is installed to block ALL user input (keyboard, mouse, shortcuts)
   - UI remains responsive for paint events
   - Status console displays warnings if user tries to trigger new operations

3. **After Operation Completes**:
   - `end_operation()` is called to mark operation as complete
   - Event filter is removed, re-enabling user input
   - Ready for next operation

## Benefits

### For Users
- **No crashes** from rapid input or impatience
- **Clear feedback** via status console when operations are blocked
- **Consistent behavior** across all dialogs
- **Visual feedback** - UI shows operation in progress

### For Developers
- **Simple integration** - just inherit mixin and add decorator
- **Centralized logic** - all protection code in one place
- **Flexible** - can customize blocking behavior per dialog
- **Maintainable** - single source of truth for operation guards

## Updated Dialogs

All LLM-based dialogs have been updated with the operation guard system:

1. **`enhanced_prompt_dialog.py`** - Prompt Enhancement
2. **`prompt_generation_dialog.py`** - Prompt Generation
3. **`prompt_question_dialog.py`** - LLM Questions
4. **`reference_image_dialog.py`** - Image Analysis

## Usage Example

### Basic Implementation

```python
from .dialog_utils import OperationGuardMixin, guard_operation

class MyDialog(QDialog, OperationGuardMixin):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Create UI first
        self.init_ui()

        # Initialize operation guard AFTER UI (needs status_console)
        self.init_operation_guard(block_all_input=True)

    @guard_operation("Processing Data")
    def process_data(self):
        """Process data asynchronously."""
        # Validation checks
        if not self.data:
            return

        # Disable UI
        self.process_btn.setEnabled(False)

        # Mark operation as started (enables input blocking)
        self.start_operation("Processing Data")

        # Start async operation
        self.start_worker_thread()

    def on_process_complete(self, result):
        """Handle completion."""
        # Re-enable UI
        self.process_btn.setEnabled(True)

        # End operation (disables input blocking)
        self.end_operation()

    def on_process_error(self, error):
        """Handle error."""
        # Re-enable UI
        self.process_btn.setEnabled(True)

        # End operation (disables input blocking)
        self.end_operation()
```

### Key Points

1. **Inherit from `OperationGuardMixin`** in addition to `QDialog`
2. **Call `init_operation_guard()`** AFTER UI is created (needs `status_console`)
3. **Use `@guard_operation` decorator** on methods that start async operations
4. **Call `start_operation()`** when starting the async work
5. **Call `end_operation()`** in BOTH success AND error handlers

## Configuration Options

### `init_operation_guard()` Parameters

```python
self.init_operation_guard(
    block_all_input=True,      # If True, blocks ALL input during operations
    block_focus_changes=False  # If True, also blocks focus changes
)
```

### `@guard_operation` Parameters

```python
@guard_operation(
    operation_name="My Operation",  # Name shown in warnings (defaults to method name)
    show_warning=True,              # Show warning in status console if blocked
    log_warning=True                # Log warning to console/file if blocked
)
```

## What Gets Blocked

During an operation, the following user inputs are blocked:

- ✅ **Mouse clicks** (press, release, double-click)
- ✅ **Keyboard input** (key press, key release)
- ✅ **Keyboard shortcuts** (including Ctrl+Enter, etc.)
- ✅ **Shortcut overrides**
- ✅ **Focus changes** (optional)

The following remain responsive:

- ✅ **Paint events** (UI stays responsive visually)
- ✅ **Close events** (user can still cancel/close dialog)
- ✅ **Timer events** (progress updates continue)

## Error Handling

The system handles edge cases gracefully:

- **Multiple start attempts**: Warns and blocks subsequent starts
- **End without start**: Warns but doesn't crash
- **Dialog close during operation**: Properly disconnects signals and cleans up
- **Thread cleanup**: Ensures threads are properly terminated

## Testing

To test the system:

1. Open any LLM dialog (Enhance Prompt, Generate Prompts, etc.)
2. Start an operation (e.g., click "Enhance")
3. Try to:
   - Press Ctrl+Enter multiple times
   - Click the button rapidly
   - Press other keyboard shortcuts
   - Click other UI elements

**Expected behavior**: All input is blocked, warnings appear in status console

## Migration Guide

### For Existing Dialogs

To add operation guarding to an existing dialog:

1. **Import the system**:
   ```python
   from .dialog_utils import OperationGuardMixin, guard_operation
   ```

2. **Add mixin to class**:
   ```python
   class MyDialog(QDialog, OperationGuardMixin):  # Add OperationGuardMixin
   ```

3. **Initialize in `__init__`** (AFTER `init_ui()`):
   ```python
   self.init_ui()
   self.init_operation_guard(block_all_input=True)  # Add this
   ```

4. **Add decorator to operation methods**:
   ```python
   @guard_operation("Operation Name")  # Add decorator
   def my_operation(self):
   ```

5. **Add start/end calls**:
   ```python
   def my_operation(self):
       # ... validation ...
       self.start_operation("Operation Name")  # Add this
       # ... start async work ...

   def on_complete(self, result):
       # ... process result ...
       self.end_operation()  # Add this

   def on_error(self, error):
       # ... handle error ...
       self.end_operation()  # Add this
   ```

6. **Remove manual checks** (if any):
   ```python
   # DELETE THIS - no longer needed:
   if self.thread and self.thread.isRunning():
       return
   ```

## Future Enhancements

Potential improvements for future versions:

- **Progress indication**: Show progress bar during blocked operations
- **Queue operations**: Allow queuing operations instead of blocking
- **Timeout handling**: Auto-cancel operations that take too long
- **Granular blocking**: Block only specific widgets instead of all input
- **Operation history**: Track operation durations for performance monitoring

## Troubleshooting

### "Operation already in progress" warning shown incorrectly

**Cause**: Missing `end_operation()` call in error handler or completion handler.

**Solution**: Ensure `end_operation()` is called in BOTH success and error paths.

### Input not being blocked

**Cause**: `init_operation_guard()` called before UI is created, or `block_all_input=False`.

**Solution**:
1. Call `init_operation_guard()` AFTER `init_ui()`
2. Ensure `block_all_input=True` (default)

### Status console warnings not showing

**Cause**: Status console not available when mixin tries to access it.

**Solution**: Ensure dialog has a `self.status_console` attribute before calling `init_operation_guard()`.

### Decorator not working

**Cause**: Dialog class doesn't inherit from `OperationGuardMixin`.

**Solution**: Add `OperationGuardMixin` to class inheritance: `class MyDialog(QDialog, OperationGuardMixin):`

## Related Files

- **`gui/dialog_utils.py`**: Core operation guard system implementation
- **`gui/enhanced_prompt_dialog.py`**: Example implementation (prompt enhancement)
- **`gui/prompt_generation_dialog.py`**: Example implementation (prompt generation)
- **`gui/prompt_question_dialog.py`**: Example implementation (LLM questions)
- **`gui/reference_image_dialog.py`**: Example implementation (image analysis)

## Version History

- **2025-11-05**: Initial implementation
  - Created `OperationGuardMixin` and `InputBlockerEventFilter`
  - Added `@guard_operation` decorator
  - Updated 4 core LLM dialogs with operation guarding
  - Centralized all operation protection logic

---

*This system was created to fix crashes when users pressed Ctrl+Enter multiple times during LLM operations.*
