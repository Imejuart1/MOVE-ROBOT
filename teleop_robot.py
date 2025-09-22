# hybrid_auto_teleop.py
# Auto-straight by default; switch to manual on key press; revert to auto after idle.
# Windows-only (msvcrt). For Mac/Linux, swap msvcrt with pynput.

import time
import msvcrt
from Controller import UDP_Controller, DataType

# ---- network ----
IP, PORT = "0.0.0.0", 8400

# ---- auto mode ----
FORWARD_SPEED = 6.0        # straight speed in AUTO
AUTO_DT       = 0.02       # update rate in AUTO

# ---- manual mode ----wwwwwwwwwwwwwwwwwwwwwwwwwwwwww
MAX_SPEED = 7.0            # clip for wheel speeds (model may cap at ±1.0)
STEP      = 1.0            # increment per key press
DECAY     = 0.96           # natural slow down when no key is held
MANUAL_DT = 0.01           # update rate in MANUAL

# ---- switching behavior ----
IDLE_BACK_TO_AUTO = 2.0    # seconds without keys to switch back to AUTO

def clip(v, lo, hi): return max(lo, min(hi, v))

def run():
    ctrl = UDP_Controller(ip=IP, port=PORT)
    ctrl.addVariable("left_speed",  DataType.FLOAT, 0.0)
    ctrl.addVariable("right_speed", DataType.FLOAT, 0.0)
    ctrl.addVariable("sensor",      DataType.STRING, "")  # optional
    ctrl.start()

    mode = "AUTO"                # "AUTO" or "MANUAL"
    left = right = 0.0
    last_key_time = 0.0
    last_hud = 0.0

    print(f"""
Hybrid controller running.
AUTO = straight at {FORWARD_SPEED}. MANUAL on any key; back to AUTO after {IDLE_BACK_TO_AUTO}s idle.

Controls (MANUAL):
  W/Up    forward
  S/Down  backward
  A/Left  turn left
  D/Right turn right
  Space   stop
  Q       quit
""")

    try:
        while True:
            # --- read keys (if any) ---
            key_seen = False
            while msvcrt.kbhit():
                key_seen = True
                ch = msvcrt.getch()
                if ch in (b'\xe0', b'\x00'):  # arrow prefix
                    ch = msvcrt.getch()
                    if ch == b'H':   # Up
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                    elif ch == b'P': # Down
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                    elif ch == b'K': # Left
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                    elif ch == b'M': # Right
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                else:
                    c = ch.lower()
                    if c == b'w':
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                    elif c == b's':
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                    elif c == b'a':
                        left  = clip(left  - STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right + STEP, -MAX_SPEED, MAX_SPEED)
                    elif c == b'd':
                        left  = clip(left  + STEP, -MAX_SPEED, MAX_SPEED)
                        right = clip(right - STEP, -MAX_SPEED, MAX_SPEED)
                    elif c == b' ':
                        left = right = 0.0
                    elif c == b'q':
                        raise KeyboardInterrupt

            now = time.time()

            # --- switching logic ---
            if key_seen:
                if mode != "MANUAL":
                    # entering manual: keep current left/right (don’t jump)
                    pass
                mode = "MANUAL"
                last_key_time = now
            else:
                if mode == "MANUAL" and (now - last_key_time) >= IDLE_BACK_TO_AUTO:
                    # back to auto
                    mode = "AUTO"
                    left = right = 0.0  # optionally reset before auto takes over

            # --- control update ---
            if mode == "AUTO":
                left = right = FORWARD_SPEED
                ctrl.setValue("left_speed", left)
                ctrl.setValue("right_speed", right)
                dt = AUTO_DT
            else:
                # manual decay
                left  *= DECAY
                right *= DECAY
                if abs(left)  < 1e-3: left  = 0.0
                if abs(right) < 1e-3: right = 0.0
                ctrl.setValue("left_speed", left)
                ctrl.setValue("right_speed", right)
                dt = MANUAL_DT

            # HUD occasionally
            if now - last_hud > 0.3:
                print(f"[{mode}] L={left:+.2f} R={right:+.2f}  sensor={ctrl.getValue('sensor')}", end="\r")
                last_hud = now

            time.sleep(dt)

    except KeyboardInterrupt:
        pass
    finally:
        ctrl.setValue("left_speed", 0.0)
        ctrl.setValue("right_speed", 0.0)
        ctrl.close()
        print("\nStopped.")

if __name__ == "__main__":
    run()
