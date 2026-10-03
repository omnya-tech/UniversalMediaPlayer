import logging

logger = logging.getLogger("omnya")

try:
    import winsound
except ImportError:
    winsound = None

def play_completion_chime():
    if winsound is None:
        return
    try:
        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        logger.debug("Failed to play completion chime", exc_info=True)

def play_error_chime():
    if winsound is None:
        return
    try:
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        logger.debug("Failed to play error chime", exc_info=True)