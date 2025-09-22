# manual_teleop.py
# Drive the Simumatik mini-robot with keyboard (WASD / Arrow keys).
# Requires your Controller.py in the same folder.
# Windows-only (msvcrt). For Mac/Linux, use pynput instead.

import time
import msvcrt
from Controller import UDP_Controller, DataType

# --- network ---
IP, PORT = "0.0.0.0", 8400

# --- motion tuning ---
MAX_SPEED = 7.0    # clip for wheel speeds (model may cap at ±1.0)
STEP      = 1.0    # increment per key press
DECAY     = 0.96   # natural slow down when no key is pressed
LOOP_DT   = 0.01   # control loop period

def clip(v, lo, hi): 
    return max(lo, min(hi, v))

def run():
    ctrl = UDP_Controller(ip=IP, port=PORT)
    ctrl.addVariable("left_speed",  DataType.FLOAT, 0.0)
    ctrl.addVariable("right_speed", DataType.FLOAT, 0.0)
    ctrl.addVariable("sensor",      DataType.STRING, "")  # optional info
    ctrl.start()

    left = right = 0.0
    last_hud = 0.0

    print("""
Manual teleop running.
Controls:
  W/Up    = forward
  S/Down  = backward
  A/Left  = turn left
  D/Right = turn right
  Space   = stop
  Q       = quit
""")

    try:
        while True:
            # --- read keys ---
            while msvcrt.kbhit():
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

            # --- natural slowdown ---
            left  *= DECAY
            right *= DECAY
            if abs(left)  < 1e-3: left  = 0.0
            if abs(right) < 1e-3: right = 0.0

            # --- send to sim ---
            ctrl.setValue("left_speed", left)
            ctrl.setValue("right_speed", right)

            # --- HUD ---
            now = time.time()
            if now - last_hud > 0.3:
                print(f"L={left:+.2f} R={right:+.2f}  sensor={ctrl.getValue('sensor')}", end="\r")
                last_hud = now

            time.sleep(LOOP_DT)

    except KeyboardInterrupt:
        pass
    finally:
        ctrl.setValue("left_speed", 0.0)
        ctrl.setValue("right_speed", 0.0)
        ctrl.close()
        print("\nStopped.")

if __name__ == "__main__":
    run()
