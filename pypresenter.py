#!/usr/bin/env python3
"""
Activate some nice features of the norwii N97s presenter: spotlight, laser.

Norwii97s functions as an air mouse when you hold the spotlight button. 
Pressing the spotlight button sends Ctrl+L, releasing it sends Ctrl+A.
Pressing the erase button sends 'e'
Pressing the annotate button sends Ctrl+P (and a mouse click?), releasing it sends Ctrl+A.
It is possible to reprogram them (I think).

The laser is not really needed, as the norwii switches between "spotlight" and
"normal air mouse mode" when double clicking the spotlight button. In normal air
mouse mode you can just activate the standard laser pointer of slides or ppt.

Almost perfect for norwii on linux (and using google slides).
Fine for macos, but can create a spotlight ghost in specific situations (but always removed in next trigger).

requirements:
 PySide6
 pynput

and additionally on macos:
 objc 
"""
__version__ = "20251206"

import sys
import threading
import os
import configparser
from pathlib import Path
from pynput import keyboard

# nuitka needs pyside instead of pyqt
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QObject, QTimer, QPoint, QPointF, QRect
from PySide6.QtGui import QPainter, QBrush, QColor, QRadialGradient, QCursor, QScreen, QPen
from PySide6.QtCore import Signal as pyqtSignal

IS_DARWIN = sys.platform == "darwin"
if IS_DARWIN:
    try:
        import objc
        from ctypes import c_void_p
        from Cocoa import (
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSStatusWindowLevel,
            NSBorderlessWindowMask,
            NSNonactivatingPanelMask,
        )
        # AppKit to get frontmostApplication / reactivate apps
        from AppKit import NSWorkspace, NSRunningApplication          
    except Exception as e:
        print("Warning: PyObjC not available or failed to import. macOS-specific behavior will not be applied.")
        print("Install with: pip install pyobjc")
        IS_DARWIN = False
    
    
hotkey_listener = None

# -------------------------
# Configuration file
# -------------------------
class Config:
    CONFIG_DIR = Path.home() / ".config" / "pypresenter"
    CONFIG_FILE = CONFIG_DIR / "config.ini"

    def __init__(self):
        # default settings. values in config override these
        self.MODES = ["SPOTLIGHT_HOLD", "LASER"]
        self.SPOT_RADIUS = 200.0
        self.BACKGROUND_ALPHA = 155
        self.SPOT_RING_THICKNESS = 0.05
        self.SPOT_RING_COLOR_R = 255
        self.SPOT_RING_COLOR_G = 105
        self.SPOT_RING_COLOR_B = 180
        self.SPOT_RING_COLOR_A = 255
        self.LASER_MAX_TRAIL_LENGTH = 15
        self.LASER_BASE_RADIUS = 12.0
        self.LASER_HEAD_MULTIPLIER = 1.5
        self.LASER_COLOR_R = 255
        self.LASER_COLOR_G = 0
        self.LASER_COLOR_B = 0
        self.LASER_COLOR_A = 255
        self.LASER_MIN_ALPHA = 25

        self.SPOT_RING_COLOR = QColor(self.SPOT_RING_COLOR_R, self.SPOT_RING_COLOR_G,
                                      self.SPOT_RING_COLOR_B, self.SPOT_RING_COLOR_A)
        self.LASER_COLOR_BASE = QColor(self.LASER_COLOR_R, self.LASER_COLOR_G,
                                       self.LASER_COLOR_B, self.LASER_COLOR_A)
        self._update_values()


    def create_default_config_file(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser()
        config['General'] = {'modes': ', '.join(self.MODES)}
        config['Spotlight'] = {
            'spot_radius': str(self.SPOT_RADIUS),
            'background_alpha': str(self.BACKGROUND_ALPHA),
            'ring_thickness': str(self.SPOT_RING_THICKNESS),
            'ring_color_rgba': f"{self.SPOT_RING_COLOR_R}, {self.SPOT_RING_COLOR_G}, {self.SPOT_RING_COLOR_B}, {self.SPOT_RING_COLOR_A}",
        }
        config['Laser'] = {
            'max_trail_length': str(self.LASER_MAX_TRAIL_LENGTH),
            'base_radius': str(self.LASER_BASE_RADIUS),
            'head_multiplier': str(self.LASER_HEAD_MULTIPLIER),
            'color_rgba': f"{self.LASER_COLOR_R}, {self.LASER_COLOR_G}, {self.LASER_COLOR_B}, {self.LASER_COLOR_A}",
            'min_alpha': str(self.LASER_MIN_ALPHA),
        }
        with open(self.CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        print(f"Created default configuration file: {self.CONFIG_FILE}")

    def load_config(self):
        parser = configparser.ConfigParser()
        if not self.CONFIG_FILE.exists():
            self.create_default_config_file()
            parser.read(self.CONFIG_FILE)
        else:
            parser.read(self.CONFIG_FILE)

        def parse_color_rgba(rgba_str):
            try:
                r, g, b, a = map(lambda x: int(x.strip()), rgba_str.split(','))
                return QColor(r, g, b, a)
            except Exception as e:
                print(f"Error parsing color string '{rgba_str}': {e}. Using default.")
                return None

        if 'General' in parser and 'modes' in parser['General']:
            modes_str = parser['General']['modes']
            self.MODES = [m.strip().upper() for m in modes_str.split(',') if m.strip()]

        if 'Spotlight' in parser:
            s_cfg = parser['Spotlight']
            self.SPOT_RADIUS = s_cfg.getfloat('spot_radius', self.SPOT_RADIUS)
            self.BACKGROUND_ALPHA = s_cfg.getint('background_alpha', self.BACKGROUND_ALPHA)
            self.SPOT_RING_THICKNESS = s_cfg.getfloat('ring_thickness', self.SPOT_RING_THICKNESS)
            ring_color = parse_color_rgba(s_cfg.get('ring_color_rgba', ''))
            if ring_color is not None:
                self.SPOT_RING_COLOR = ring_color

        if 'Laser' in parser:
            l_cfg = parser['Laser']
            self.LASER_MAX_TRAIL_LENGTH = l_cfg.getint('max_trail_length', self.LASER_MAX_TRAIL_LENGTH)
            self.LASER_BASE_RADIUS = l_cfg.getfloat('base_radius', self.LASER_BASE_RADIUS)
            self.LASER_HEAD_MULTIPLIER = l_cfg.getfloat('head_multiplier', self.LASER_HEAD_MULTIPLIER)
            self.LASER_MIN_ALPHA = l_cfg.getint('min_alpha', self.LASER_MIN_ALPHA)
            laser_color = parse_color_rgba(l_cfg.get('color_rgba', ''))
            if laser_color is not None:
                self.LASER_COLOR_BASE = laser_color

        self._update_values()
        print(f"Configuration loaded from {self.CONFIG_FILE}.")

    def _update_values(self):
        """
        define the values to be used later on
          SPOT_RING_COLOR and LASER_COLOR_BASE are directly defined in init and load
        """
        self.BACKGROUND_COLOR = QColor(0, 0, 0, self.BACKGROUND_ALPHA)
        self.OPAQUE_BLACK = QColor(0, 0, 0, 255)

        # make brushes
        self.hole_brush = QBrush(self.OPAQUE_BLACK)

        pink = QColor(self.SPOT_RING_COLOR)
        pink0 = QColor(pink)
        pink0.setAlpha(0)

        blur_width = self.SPOT_RING_THICKNESS
        hole_fraction = 1-2*blur_width
        self.hole_radius = float(self.SPOT_RADIUS)*(hole_fraction+blur_width)

        pink_grad = QRadialGradient(QPointF(0,0), self.SPOT_RADIUS, QPointF(0,0))
        pink_grad.setColorAt(0.0, QColor(0, 0, 0, 0))            # Center: Transparent
        pink_grad.setColorAt(hole_fraction, pink0)               # Start of Pink at full transparency
        pink_grad.setColorAt(hole_fraction+blur_width, pink)     # Max opaque pink at some distance
        pink_grad.setColorAt(1.0, QColor(0, 0, 0, 0))            # End at Pink at 100/255 transparency
        self.rim_brush = pink_grad

        self.rim_radius = float(self.SPOT_RADIUS)

        
global_config = Config()
global_config.load_config()

# -------------------------
# Global state to be accessed by thread
# -------------------------
class GlobalState:
    def __init__(self, config):
        self.config = config
        if self.config.MODES:
            self.mode_index = 0
            self.current_mode = self.config.MODES[self.mode_index]
        else:
            self.mode_index = 0
            self.current_mode = "SPOTLIGHT_HOLD"
        self.is_toggled_on = False # True only if SPOTLIGHT_TOGGLE mode is on

    def cycle_mode(self):
        if not self.config.MODES:
            return "SPOTLIGHT_HOLD"
        # Reset toggle state on mode cycle
        self.is_toggled_on = False
        self.mode_index = (self.mode_index + 1) % len(self.config.MODES)
        self.current_mode = self.config.MODES[self.mode_index]
        return self.current_mode

    # Helper method to check if an effect should be painted (kept for logic clarity)
    def should_show_effect(self):
        if self.current_mode == "SPOTLIGHT_TOGGLE":
            return self.is_toggled_on
        # SPOTLIGHT_HOLD and LASER are driven by hotkey press/release,
        # but the request is for the overlay to always be shown, 
        # so we rely on the internal `overlay_active` state in the widget
        # which is toggled by the hotkeys.
        return True

global_state = GlobalState(global_config)

# -------------------------
# Signals
# -------------------------
class KeyboardSignalEmitter(QObject):
    # Signals now reflect controlling the 'effect' drawing, not the window's 'overlay'
    effect_activate = pyqtSignal()
    effect_deactivate = pyqtSignal()
    mode_changed = pyqtSignal(str)
    screen_changed = pyqtSignal()
    app_quit = pyqtSignal()

# -------------------------
# PresenterOverlay
# -------------------------
class PresenterOverlay(QWidget):
    _current_geometry = None
    
    def __init__(self, initial_geometry: QRect, emitter: QObject, config: Config):
        super().__init__()
        self.config = config
        self.emitter = emitter # Store emitter reference for screen check

        # --- internal state first ---
        self.overlay_active = False 
        self.mouse_pos = QPoint(0, 0)
        self.laser_trail = []
        # which mode flags (updated on mode change)
        self.is_spotlight_mode = False
        self.is_laser_mode = False

        # Timer: used for laser animation and also a lower-rate spotlight poll when needed.
        self.interval_laser = 30
        self.interval_spotlight = 30 

        self.timer = QTimer(self)
        self.timer.setInterval(self.interval_laser)
        self.timer.timeout.connect(self._on_timer_tick)
        
        # QTimer to check for screen changes (e.g., projector connected/disconnected)
        self.screen_check_timer = QTimer(self)
        self.screen_check_timer.setInterval(1000) # Check every 1 second
        self.screen_check_timer.timeout.connect(self._check_screen_change)
        
        # Window flags: keep ToolTip plus TransparentForInput to be click-through
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.ToolTip |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Set initial geometry and store it
        self.setGeometry(initial_geometry)
        PresenterOverlay._current_geometry = initial_geometry

        # connect signals
        self.emitter.mode_changed.connect(self._on_mode_changed)
        self.emitter.screen_changed.connect(self._on_screen_changed)
        self.emitter.effect_activate.connect(self.activate_effect) 
        self.emitter.effect_deactivate.connect(self.deactivate_effect) 
        
        # Initial setup: The overlay should be shown immediately and always
        try:
            # WA_ShowWithoutActivating prevents the window from stealing focus on macOS
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            # older PySide/PyQt names compatibility
            try:
                self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            except Exception:
                pass
        
        self.show()
        self.raise_()
        
        # Start the screen check timer immediately
        self.screen_check_timer.start()

        # macOS: make persistent overlay (will noop on linux)
        if IS_DARWIN:
            QTimer.singleShot(50, self.make_persistent_overlay)

        # Enable mouse tracking *only* for internal events
        self.setMouseTracking(True)
        
        # Initial mode setup to start the timer if needed
        self._update_mode_flags()
        self._update_timer_state()
        
    def _on_screen_changed(self):
        print("Screen geometry changed. Adjusting overlay position.")
        
        # Preserve active state
        was_active = self.overlay_active
        
        # Deactivate before changing geometry to clear state
        self.deactivate_effect(is_mode_switch=True) 

        geom = self._get_current_screen_geometry()
        self.setGeometry(geom)
        
        # 4. Force an immediate repaint on the NEW geometry to ensure the window manager
        # clears the new region's composition buffer.
        self.update() 
        
        # 5. Restore active state if it was on, but with a small delay timer.
        # This queues activate_effect() to run after the current screen geometry change
        # and subsequent paint events are fully processed by the system.
        if was_active:
            QTimer.singleShot(150, self.activate_effect) # a delay is needed on macos
                
    def _check_screen_change(self):
        new_geom = self._get_current_screen_geometry()
        
        # Compare current stored geometry with the new geometry
        if new_geom != PresenterOverlay._current_geometry:
            PresenterOverlay._current_geometry = new_geom
            # Emit signal to handle the screen switch logic in the main thread
            self.emitter.screen_changed.emit()


    # -----------------
    # mode handling
    # -----------------
    def _on_mode_changed(self, new_mode: str):
        print(f"MODE SWITCHED: {new_mode}")
        
        # Clear effect state/trail
        self.deactivate_effect(is_mode_switch=True) 
        self._update_mode_flags() # Update new flags
        
        self.update() # Repaint the whole window to force clear the composition mode
        self._update_timer_state() # Start/stop timer based on new mode

    def _update_mode_flags(self):
        m = global_state.current_mode
        self.is_spotlight_mode = (m in ["SPOTLIGHT_HOLD", "SPOTLIGHT_TOGGLE"])
        self.is_laser_mode = (m == "LASER")

    def _update_timer_state(self):
        if self.is_laser_mode:
            self.timer.setInterval(self.interval_laser)
            if not self.timer.isActive():
                self.timer.start()
        elif self.is_spotlight_mode:
            self.timer.setInterval(self.interval_spotlight)
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()
            
    # -----------------
    # activation / deactivation of the EFFECT
    # -----------------
    def activate_effect(self):
        if not self.overlay_active:
            self.overlay_active = True

            # On macOS, record the current frontmost app
            if IS_DARWIN:
                try:
                    workspace = NSWorkspace.sharedWorkspace()
                    front = workspace.frontmostApplication()
                    self._previous_frontmost_app = front
                except Exception:
                    self._previous_frontmost_app = None
                    
            # Set the initial mouse position and force a repaint
            self.mouse_pos = self.mapFromGlobal(QCursor.pos())
            self.update() 

    def deactivate_effect(self, is_mode_switch=False):
        if self.overlay_active:
            self.overlay_active = False
            self.laser_trail.clear()
            
            # Force a repaint to draw the clear background (fully transparent)
            self.update() 
            
            # Only try to restore focus on an actual deactivation, not a mode switch
            if IS_DARWIN and not is_mode_switch and getattr(self, "_previous_frontmost_app", None) is not None:
                try:
                    def _reactivate():
                        try:
                            self._previous_frontmost_app.activateWithOptions_(0)
                        except Exception:
                            try:
                                pid = int(self._previous_frontmost_app.processIdentifier())
                                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
                                if app is not None:
                                    app.activateWithOptions_(0)
                            except Exception:
                                pass
                        finally:
                            self._previous_frontmost_app = None

                    QTimer.singleShot(30, _reactivate)
                except Exception:
                    self._previous_frontmost_app = None

    # -----------------
    # timer tick: update cursor position and handle laser trail decay
    # -----------------
    def _on_timer_tick(self):
        
        # 1. Get new position
        pos = QCursor.pos()
        local_pos = self.mapFromGlobal(pos)
        
        needs_repaint = False
        
        if local_pos == self.mouse_pos:
            # Only update for laser trail decay if mouse hasn't moved
            if self.is_laser_mode and len(self.laser_trail) > 1:
                self.laser_trail.pop(0)
                needs_repaint = True
        else:
            self.mouse_pos = local_pos
            needs_repaint = True
            
            # --- Handle LASER trail animation ---
            if self.is_laser_mode and self.overlay_active:
                self.laser_trail.append(QPointF(self.mouse_pos))
                if len(self.laser_trail) > self.config.LASER_MAX_TRAIL_LENGTH:
                    self.laser_trail.pop(0)

        if needs_repaint and self.overlay_active:
            self.update()


    # -----------------
    # geometry helper
    # -----------------
    def _get_current_screen_geometry(self):
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos)
        if screen is None:
            return QApplication.primaryScreen().geometry()
        return screen.geometry()

    # -----------------
    # paint event
    # -----------------
    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing) 
    
            # Always clear the previous frame fully transparently
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.fillRect(self.rect(), QColor(0,0,0,0)) 

            if not self.overlay_active:
                return

            # Spotlight drawing
            if self.is_spotlight_mode:
                center = QPointF(self.mouse_pos)
                
                # 1. Draw dim background  
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.fillRect(self.rect(), self.config.BACKGROUND_COLOR)
                
                # 2. Cut transparent hole
                painter.setBrush(self.config.hole_brush)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut) 
                painter.drawEllipse(center,  
                                    self.config.hole_radius,
                                    self.config.hole_radius)
        
                # 3. Draw rim around hole
                self.config.rim_brush.setCenter(center)
                self.config.rim_brush.setFocalPoint(center)
                painter.setBrush(self.config.rim_brush)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.drawEllipse(center,
                                    self.config.rim_radius,
                                    self.config.rim_radius)
                return
                
            # Laser drawing
            elif self.is_laser_mode:
                if not self.laser_trail:
                    return
                
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                total = len(self.laser_trail)
                for i, pos in enumerate(self.laser_trail):
                    # compute alpha and radius
                    if total > 1:
                        t = i / float(total - 1)
                    else:
                        t = 1.0
                    alpha = int(self.config.LASER_MIN_ALPHA + (255 - self.config.LASER_MIN_ALPHA) * t)
                    radius = self.config.LASER_BASE_RADIUS
                    if i == total - 1:
                        radius *= self.config.LASER_HEAD_MULTIPLIER
                        alpha = 255
                    color = QColor(self.config.LASER_COLOR_BASE)
                    color.setAlpha(alpha)
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(pos, radius, radius)

    # macOS persistent overlay adjustments
    def make_persistent_overlay(self):
        if not IS_DARWIN:
            return
        try:
            view_ptr = int(self.winId())
            nsview = objc.objc_object(c_void_p=view_ptr)
            nswindow = nsview.window()
            if nswindow is None:
                QTimer.singleShot(50, self.make_persistent_overlay)
                return
            try:
                nswindow.setStyleMask_(NSBorderlessWindowMask | NSNonactivatingPanelMask)
            except Exception:
                pass
            try:
                behavior = (
                    NSWindowCollectionBehaviorCanJoinAllSpaces
                    | NSWindowCollectionBehaviorFullScreenAuxiliary
                    | NSWindowCollectionBehaviorIgnoresCycle
                )
                nswindow.setCollectionBehavior_(behavior)
            except Exception:
                pass
            try:
                nswindow.setHidesOnDeactivate_(False)
            except Exception:
                pass
            try:
                nswindow.setLevel_(NSStatusWindowLevel)
            except Exception:
                pass
            try:
                nswindow.setIgnoresMouseEvents_(True)
            except Exception:
                pass
            try:
                nswindow.orderFrontRegardless()
            except Exception:
                pass
            self._nswindow = nswindow
            print("macOS: NSWindow adjusted for persistent overlay.")
        except Exception as exc:
            print("make_persistent_overlay failed:", exc)

# -------------------------
# Hotkey manager
# -------------------------
def start_overlay_hotkey_manager():
    global emitter, global_state, hotkey_listener

    def handle_mode_switch():
        new_mode = global_state.cycle_mode()
        emitter.mode_changed.emit(new_mode)

    def handle_activate():
        if global_state.current_mode == "SPOTLIGHT_TOGGLE":
            if not global_state.is_toggled_on:
                emitter.effect_activate.emit()
                global_state.is_toggled_on = True
            else:
                emitter.effect_deactivate.emit()
                global_state.is_toggled_on = False
        elif global_state.current_mode in ["SPOTLIGHT_HOLD", "LASER"]:
            emitter.effect_activate.emit()

    def handle_deactivate():
        if global_state.current_mode in ["SPOTLIGHT_HOLD", "LASER"]:
            emitter.effect_deactivate.emit()
        return True

    def handle_quit():
        global hotkey_listener
        print("\n[Application Shutdown] Received Ctrl+Q. Initiating clean exit.")
        if hotkey_listener:
            hotkey_listener.stop()
        emitter.app_quit.emit()

    hotkeys = {
        '<ctrl>+l': handle_activate,
        '<ctrl>+a': handle_deactivate,
        'e': handle_mode_switch,
        '<ctrl>+q': handle_quit
    }

    h = keyboard.GlobalHotKeys(hotkeys)
    hotkey_listener = h
    h.start()

# -------------------------
# Main application
# -------------------------
def main():
    app = QApplication(sys.argv)

    # Helper function to get initial geometry
    def _get_current_screen_geometry():
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos)
        if screen is None:
            return QApplication.primaryScreen().geometry()
        return screen.geometry()

    initial_geometry = _get_current_screen_geometry()

    global emitter
    emitter = KeyboardSignalEmitter() 

    # We rely on the overlay's internal logic and signals for updates
    overlay = PresenterOverlay(initial_geometry, emitter, global_config)

    # the overlay manages its own activation/deactivation/screen logic
    emitter.app_quit.connect(app.quit)

    hotkey_thread = threading.Thread(target=start_overlay_hotkey_manager, daemon=True)
    hotkey_thread.start()

    print(f"Mode Switch Key: 'e'")
    print(f"Norwii Action Keys: Ctrl+L (Press) / Ctrl+A (Release)")
    print(f"To exit cleanly, use the hotkey: Ctrl+Q")
    print("-" * 50)
    print("Overlay is now always shown. Effect (Spotlight/Laser) is toggled by hotkeys.")

    try:
        sys.exit(app.exec())
    finally:
        pass

if __name__ == '__main__':
    emitter = None
    main()