#!/usr/bin/env python3
"""
ImageAI - AI Image Generation Tool

A desktop GUI and CLI application for AI image generation using Google Gemini
and OpenAI (DALL-E) APIs.
"""

import sys
import os
import warnings

# Set environment variables before any imports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow info messages
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN custom operations message

# Suppress warnings before any imports that might trigger them
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*GetPrototype.*')
warnings.filterwarnings('ignore', message='pkg_resources is deprecated as an API')
warnings.filterwarnings('ignore', category=DeprecationWarning, module='pkg_resources')

# Install import hook to patch protobuf on first import
import builtins
_original_import = builtins.__import__
_patched = False

def _patched_import(name, *args, **kwargs):
    global _patched
    result = _original_import(name, *args, **kwargs)

    # Patch protobuf modules after they're imported but before they're used
    if not _patched and name.startswith('google.protobuf'):
        _patched = True
        try:
            # Patch MessageFactory if it exists
            if 'google.protobuf.message_factory' in sys.modules:
                _mf = sys.modules['google.protobuf.message_factory']
                if hasattr(_mf, 'MessageFactory'):
                    mf_class = _mf.MessageFactory
                    if not hasattr(mf_class, 'GetPrototype') and hasattr(mf_class, 'GetMessageClass'):
                        mf_class.GetPrototype = lambda self, desc: self.GetMessageClass(desc)

            # Patch SymbolDatabase if it exists
            if 'google.protobuf.symbol_database' in sys.modules:
                _sdb = sys.modules['google.protobuf.symbol_database']
                if hasattr(_sdb, 'Default'):
                    try:
                        db = _sdb.Default()
                        if not hasattr(db.__class__, 'GetPrototype') and hasattr(db.__class__, 'GetMessageClass'):
                            db.__class__.GetPrototype = lambda self, desc: self.GetMessageClass(desc)
                    except:
                        pass
        except:
            pass

    return result

builtins.__import__ = _patched_import

from pathlib import Path

# Now safe to import logging
import logging
logging.getLogger('tensorflow').setLevel(logging.ERROR)

# Global flag to track initialization phase
_initialization_complete = False


def main():
    """Main entry point for ImageAI."""
    # Defer all logging until after protobuf is fully patched
    import builtins
    _orig_print = builtins.print
    _deferred_messages = []

    def _deferred_print(*args, **kwargs):
        # Store messages to print later
        _deferred_messages.append((args, kwargs))

    # Temporarily replace print to defer output
    builtins.print = _deferred_print

    try:
        # Import anything that might trigger protobuf
        # This forces the import hook to run and patch protobuf
        try:
            import google.protobuf.message_factory
            import google.protobuf.symbol_database
        except ImportError:
            pass

        # Now restore print and set up logging
        builtins.print = _orig_print

        # Replay any deferred messages
        for args, kwargs in _deferred_messages:
            _orig_print(*args, **kwargs)

        # NOW it's safe to set up logging
        from core.logging_config import setup_logging
        log_file = setup_logging()

        # Set up exception handling
        import logging, threading

        # Use the global initialization flag
        global _initialization_complete

        def _log_unhandled(exc_type, exc_value, exc_traceback):
            # Suppress protobuf GetPrototype errors during initialization
            if not _initialization_complete and exc_type == AttributeError:
                if exc_value and "GetPrototype" in str(exc_value):
                    # Silently ignore this specific error during startup
                    return

            logger = logging.getLogger(__name__)
            logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
            print("\nAn unexpected error occurred. See ./imageai_current.log for details.")
        sys.excepthook = _log_unhandled

        def _thread_excepthook(args):
            logger = logging.getLogger(__name__)
            logger.error("Unhandled thread exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            print("\nA background thread error occurred. See ./imageai_current.log for details.")
        try:
            threading.excepthook = _thread_excepthook
        except Exception:
            pass

        def _unraisable_hook(unraisable):
            logger = logging.getLogger(__name__)
            logger.error(
                f"Unraisable exception in {unraisable.object!r}",
                exc_info=(unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback),
            )
        try:
            sys.unraisablehook = _unraisable_hook
        except Exception:
            pass

        # Wrap print for logging
        def _logged_print(*args, **kwargs):
            try:
                msg = " ".join(str(a) for a in args)
                # Suppress protobuf GetPrototype errors during initialization
                if not _initialization_complete and "GetPrototype" in msg:
                    return  # Don't print or log this error
                logging.getLogger("console").info(msg)
            except Exception:
                pass
            return _orig_print(*args, **kwargs)

        builtins.print = _logged_print

    except Exception as e:
        # If something goes wrong, restore print and show error
        builtins.print = _orig_print
        print(f"Failed to initialize: {e}")
        raise
    
    # Default to GUI mode when no arguments provided
    if len(sys.argv) == 1:
        # No arguments - launch GUI by default
        try:
            from gui import launch_gui
            launch_gui()
        except ImportError as e:
            # In WSL or when GUI deps missing, show helpful message
            print(f"GUI mode not available: {e}")
            print("\nTo install GUI dependencies: pip install PySide6")
            print("\nCLI mode is available. Quick start:")
            print("  python3 main.py -h                    # Show all options")
            print("  python3 main.py -t                    # Test API key")
            print("  python3 main.py -p 'your prompt'      # Generate image")
            print("  python3 main.py --help-api-key        # API key setup help")
            sys.exit(0)
    else:
        # Arguments provided - parse and handle CLI/GUI mode
        from cli import build_arg_parser, run_cli
        
        parser = build_arg_parser()
        args = parser.parse_args()
        
        # Check if --gui flag was explicitly provided
        if getattr(args, "gui", False):
            try:
                from gui import launch_gui
                launch_gui()
            except ImportError as e:
                print(f"Error: GUI dependencies not installed. {e}")
                print("Install with: pip install PySide6")
                sys.exit(1)
        else:
            # Run CLI with parsed arguments
            exit_code = run_cli(args)
            sys.exit(exit_code)


if __name__ == "__main__":
    main()
