"""
Keyboard Emulator Module
Uses Linux evdev/uinput to emulate keyboard input
Works on Armbian Linux kernel (Radxa Rock 5b compatible)
"""

import time
import logging
from evdev import UInput, ecodes as e

logger = logging.getLogger(__name__)


class KeyboardEmulator:
    """
    Keyboard emulator using Linux uinput.
    Requires permissions to access /dev/uinput (usually root or input group).
    """
    
    # Mapping of common characters to key codes
    CHAR_TO_KEY = {
        'a': e.KEY_A, 'b': e.KEY_B, 'c': e.KEY_C, 'd': e.KEY_D, 'e': e.KEY_E,
        'f': e.KEY_F, 'g': e.KEY_G, 'h': e.KEY_H, 'i': e.KEY_I, 'j': e.KEY_J,
        'k': e.KEY_K, 'l': e.KEY_L, 'm': e.KEY_M, 'n': e.KEY_N, 'o': e.KEY_O,
        'p': e.KEY_P, 'q': e.KEY_Q, 'r': e.KEY_R, 's': e.KEY_S, 't': e.KEY_T,
        'u': e.KEY_U, 'v': e.KEY_V, 'w': e.KEY_W, 'x': e.KEY_X, 'y': e.KEY_Y,
        'z': e.KEY_Z,
        '0': e.KEY_0, '1': e.KEY_1, '2': e.KEY_2, '3': e.KEY_3, '4': e.KEY_4,
        '5': e.KEY_5, '6': e.KEY_6, '7': e.KEY_7, '8': e.KEY_8, '9': e.KEY_9,
        ' ': e.KEY_SPACE, '\n': e.KEY_ENTER, '\t': e.KEY_TAB,
        '-': e.KEY_MINUS, '=': e.KEY_EQUAL, '[': e.KEY_LEFTBRACE,
        ']': e.KEY_RIGHTBRACE, ';': e.KEY_SEMICOLON, "'": e.KEY_APOSTROPHE,
        '`': e.KEY_GRAVE, '\\': e.KEY_BACKSLASH, ',': e.KEY_COMMA,
        '.': e.KEY_DOT, '/': e.KEY_SLASH,
    }
    
    # Characters that require shift key
    SHIFT_CHARS = {
        'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f', 'G': 'g',
        'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n',
        'O': 'o', 'P': 'p', 'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u',
        'V': 'v', 'W': 'w', 'X': 'x', 'Y': 'y', 'Z': 'z',
        '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7',
        '*': '8', '(': '9', ')': '0',
        '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\',
        ':': ';', '"': "'", '<': ',', '>': '.', '?': '/',
        '~': '`',
    }
    
    def __init__(self):
        """Initialize the virtual keyboard device."""
        try:
            # Create a virtual keyboard device
            self.ui = UInput()
            logger.info("Virtual keyboard device created successfully")
        except PermissionError:
            logger.error("Permission denied to access /dev/uinput. Run as root or add user to input group.")
            raise
        except Exception as e:
            logger.error(f"Failed to create virtual keyboard: {e}")
            raise
    
    def __del__(self):
        """Clean up the virtual device."""
        if hasattr(self, 'ui'):
            try:
                self.ui.close()
            except Exception:
                pass
    
    def send_key(self, key_name, delay=0.1):
        """
        Send a single key press and release.
        
        Args:
            key_name: Key name (e.g., 'KEY_A', 'KEY_ENTER') or evdev key code
            delay: Delay after keypress in seconds
        """
        try:
            # Get key code
            if isinstance(key_name, str):
                if hasattr(e, key_name):
                    key_code = getattr(e, key_name)
                else:
                    raise ValueError(f"Unknown key: {key_name}")
            else:
                key_code = key_name
            
            # Press key
            self.ui.write(e.EV_KEY, key_code, 1)
            self.ui.syn()
            
            # Small delay
            time.sleep(0.01)
            
            # Release key
            self.ui.write(e.EV_KEY, key_code, 0)
            self.ui.syn()
            
            # Delay before next key
            if delay > 0:
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Error sending key {key_name}: {e}")
            raise
    
    def send_key_combination(self, keys, delay=0.1):
        """
        Send a key combination (e.g., Ctrl+C).
        
        Args:
            keys: List of key names to press simultaneously
            delay: Delay after the combination in seconds
        """
        try:
            # Get key codes
            key_codes = []
            for key_name in keys:
                if hasattr(e, key_name):
                    key_codes.append(getattr(e, key_name))
                else:
                    raise ValueError(f"Unknown key: {key_name}")
            
            # Press all keys
            for key_code in key_codes:
                self.ui.write(e.EV_KEY, key_code, 1)
                self.ui.syn()
                time.sleep(0.01)
            
            # Release all keys in reverse order
            for key_code in reversed(key_codes):
                self.ui.write(e.EV_KEY, key_code, 0)
                self.ui.syn()
                time.sleep(0.01)
            
            # Delay
            if delay > 0:
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Error sending key combination {keys}: {e}")
            raise
    
    def type_char(self, char, delay=0.05):
        """
        Type a single character.
        
        Args:
            char: Character to type
            delay: Delay after typing in seconds
        """
        try:
            # Check if character requires shift
            if char in self.SHIFT_CHARS:
                base_char = self.SHIFT_CHARS[char]
                if base_char in self.CHAR_TO_KEY:
                    key_code = self.CHAR_TO_KEY[base_char]
                    
                    # Press shift
                    self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                    self.ui.syn()
                    time.sleep(0.01)
                    
                    # Press key
                    self.ui.write(e.EV_KEY, key_code, 1)
                    self.ui.syn()
                    time.sleep(0.01)
                    
                    # Release key
                    self.ui.write(e.EV_KEY, key_code, 0)
                    self.ui.syn()
                    time.sleep(0.01)
                    
                    # Release shift
                    self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                    self.ui.syn()
                else:
                    logger.warning(f"Character '{char}' not supported")
                    return
            
            # Regular character
            elif char.lower() in self.CHAR_TO_KEY:
                key_code = self.CHAR_TO_KEY[char.lower()]
                
                # Press and release
                self.ui.write(e.EV_KEY, key_code, 1)
                self.ui.syn()
                time.sleep(0.01)
                
                self.ui.write(e.EV_KEY, key_code, 0)
                self.ui.syn()
            else:
                logger.warning(f"Character '{char}' not supported")
                return
            
            # Delay
            if delay > 0:
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Error typing character '{char}': {e}")
            raise
    
    def type_text(self, text, delay=0.05):
        """
        Type a string of text.
        
        Args:
            text: Text to type
            delay: Delay between characters in seconds
        """
        for char in text:
            self.type_char(char, delay)
        logger.info(f"Typed {len(text)} characters")
