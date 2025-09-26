# robot2_level_stop_on_24v.py
# Robot 2 (UDP 0.0.0.0:8500)
# Level-based behavior:
#   • AUTO: if stopinput < 24V => straight cruise; if >= 24V => stop.
#   • MANUAL keys (W/S/A/D or arrows, SPACE stop, Q quit) always available.
#   • Only manual actions are logged. After idle, returns to AUTO.

import time
from ast import literal_eval
import msvcrt  # Windows-only
from Controller import UDP_Controller, DataType

# ---- manual logger (only output if enabled) ----
ENABLE_MANUAL_LOG = True
def manual_log(*args, **kwargs):
    if ENABLE_MANUAL_LOG:
        print(*args, **kwargs)

# ---- network ----
IP, PORT = "0.0.0.0", 8500

# ---- auto cruise ----
FORWARD_SPEED = 6.0
AUTO_DT       = 0.02

# ---- manual control ----
MAX_SPEED = 7.0
STEP      = 1.0
DECAY     = 0.96
MANUAL_DT = 0.01
IDLE_BACK_TO_AUTO = 1.5

def clip(v, lo, hi): return max(lo, min(hi, v))

def stopinput_is_high24(raw):
    """True if stopinput indicates >=24V on the first element."""
    try:
        if isinstance(raw, str):
            raw = literal_eval(raw)
        if isinstance(raw, (list, tuple)) and raw:
            return float(raw[0]) >= 24.0
    except Exception:
        pass
    return False

def run():
    ctrl = UDP_Controller(ip=IP, port=PORT)
    ctrl.addVariable("left_speed",  DataType.FLOAT, 0.0)
    ctrl.addVariable("right_speed", DataType.FLOAT, 0.0)
    ctrl.addVariable("sensor",      DataType.STRING, "")
    ctrl.addVariable("stopinput",   DataType.STRING, "")
    ctrl.start()

    # modes
    mode = "AUTO"          # "AUTO" or "MANUAL"

    # outputs
    left = right = 0.0

    # manual timing
    last_key_time = 0.0

    try:
        while True:
            now = time.time()

            # ---------- read stopinput (level) ----------
            high24 = stopinput_is_high24(ctrl.getValue("stopinput"))

            # ---------- manual keys (only manual logs here) ----------
            key_seen = False

            def log_state(tag):
                manual_log(f"{time.time():.3f}s {tag}  L={left:+.2f} R={right:+.2f}")

            while msvcrt.kbhit():
                key_seen = True
                ch = msvcrt.getch()
                if ch in (b'\xe0', b'\x00'):
                    ch = msvcrt.getch()
                    if ch == b'H':   # Up
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                        log_state("MANUAL key=UP")
                    elif ch == b'P': # Down
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                        log_state("MANUAL key=DOWN")
                    elif ch == b'K': # Left
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                        log_state("MANUAL key=LEFT")
                    elif ch == b'M': # Right
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                        log_state("MANUAL key=RIGHT")
                else:
                    c = ch.lower()
                    if c == b'w':
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                        log_state("MANUAL key=W")
                    elif c == b's':
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                        log_state("MANUAL key=S")
                    elif c == b'a':
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                        log_state("MANUAL key=A")
                    elif c == b'd':
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                        log_state("MANUAL key=D")
                    elif c == b' ':
                        left = right = 0.0
                        log_state("MANUAL key=SPACE stop")
                    elif c == b'q':
                        log_state("MANUAL key=Q quit")
                        raise KeyboardInterrupt

            if key_seen:
                if mode != "MANUAL":
                    manual_log(f"{time.time():.3f}s MANUAL start")
                mode = "MANUAL"
                last_key_time = now

            # ---------- mode logic ----------
            if mode == "AUTO":
                # Level-based: 0V => cruise, 24V => stop
                if high24:
                    left = right = 0.0
                else:
                    left = right = FORWARD_SPEED
                dt = AUTO_DT
            else:
                # MANUAL: decay toward zero unless keys pressed
                left  *= DECAY
                right *= DECAY
                if abs(left)  < 1e-3: left  = 0.0
                if abs(right) < 1e-3: right = 0.0

                # after idle, return to AUTO (then level rule applies)
                if (now - last_key_time) >= IDLE_BACK_TO_AUTO:
                    mode = "AUTO"
                dt = MANUAL_DT

            # ---------- write ----------
            ctrl.setValue("left_speed", left)
            ctrl.setValue("right_speed", right)
            time.sleep(dt)

    except KeyboardInterrupt:
        pass
    finally:
        ctrl.setValue("left_speed", 0.0)
        ctrl.setValue("right_speed", 0.0)
        ctrl.close()

if __name__ == "__main__":
    run()
