# robot2_manual_only.py
# Pure MANUAL driving over UDP controller.
# - Arrow keys or WASD to steer.
# - SPACE = immediate stop.
# - Q     = quit.
# - Set USE_DECAY=False to keep last speed until changed.

import time
import msvcrt  # Windows-only
from Controller import UDP_Controller, DataType

# ---- config ----
IP, PORT     = "0.0.0.0", 8500
MAX_SPEED    = 2.0
STEP         = 1.0
USE_DECAY    = True   # <<< set False if you don't want coast-down
DECAY        = 0.96   # ignored if USE_DECAY=False
DT           = 0.01   # loop period (s)
LOG_KEYS     = True

def clip(v, lo, hi): 
    return max(lo, min(hi, v))

def log(*args, **kwargs):
    if LOG_KEYS:
        print(*args, **kwargs)

def run():
    ctrl = UDP_Controller(ip=IP, port=PORT)

    # Required variables for your driver (even if unused here)
    ctrl.addVariable("left_speed",  DataType.FLOAT, 0.0)
    ctrl.addVariable("right_speed", DataType.FLOAT, 0.0)
    ctrl.addVariable("sensor",      DataType.STRING, "")   # dummy
    ctrl.addVariable("stopinput",   DataType.STRING, "")   # dummy
    ctrl.start()

    left = right = 0.0

    try:
        while True:
            key_seen = False

            # --- read all pending keystrokes ---
            while msvcrt.kbhit():
                key_seen = True
                ch = msvcrt.getch()

                # Arrow keys arrive as a two-byte sequence
                if ch in (b'\xe0', b'\x00'):
                    ch = msvcrt.getch()
                    if ch == b'H':   # UP
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                        log(f"UP     L={left:+.2f} R={right:+.2f}")
                    elif ch == b'P': # DOWN
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                        log(f"DOWN   L={left:+.2f} R={right:+.2f}")
                    elif ch == b'K': # LEFT
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                        log(f"LEFT   L={left:+.2f} R={right:+.2f}")
                    elif ch == b'M': # RIGHT
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                        log(f"RIGHT  L={left:+.2f} R={right:+.2f}")
                else:
                    c = ch.lower()
                    if c == b'w':
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                        log(f"W      L={left:+.2f} R={right:+.2f}")
                    elif c == b's':
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                        log(f"S      L={left:+.2f} R={right:+.2f}")
                    elif c == b'a':
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                        log(f"A      L={left:+.2f} R={right:+.2f}")
                    elif c == b'd':
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                        log(f"D      L={left:+.2f} R={right:+.2f}")
                    elif c == b' ':
                        left = right = 0.0
                        log("SPACE  STOP")
                    elif c == b'q':
                        log("Q      QUIT")
                        raise KeyboardInterrupt

            # --- optional coast-down ---
            if USE_DECAY and not key_seen:
                left  *= DECAY
                right *= DECAY
                if abs(left)  < 1e-3: left  = 0.0
                if abs(right) < 1e-3: right = 0.0

            # --- write outputs ---
            ctrl.setValue("left_speed", left)
            ctrl.setValue("right_speed", right)

            time.sleep(DT)

    except KeyboardInterrupt:
        pass
    finally:
        # safety stop
        ctrl.setValue("left_speed", 0.0)
        ctrl.setValue("right_speed", 0.0)
        ctrl.close()

if __name__ == "__main__":
    run()
