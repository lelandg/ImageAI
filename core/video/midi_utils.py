"""
MIDI utility functions with runtime checking
"""

import logging

logger = logging.getLogger(__name__)

def check_midi_available():
    """Check if MIDI libraries are available at runtime"""
    try:
        import pretty_midi
        import mido
        logger.debug("MIDI libraries available")
        return True, None
    except ImportError as e:
        error_msg = f"MIDI libraries not installed: {e}"
        logger.warning(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"MIDI library error: {e}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

def get_midi_processor():
    """Get MidiProcessor instance if available"""
    available, error = check_midi_available()
    if not available:
        error_msg = error or "MIDI processing libraries not installed. Please install: pip install pretty-midi mido"
        logger.error(f"Cannot create MidiProcessor: {error_msg}")
        raise ImportError(error_msg)
    
    from core.video.midi_processor import MidiProcessor
    return MidiProcessor()