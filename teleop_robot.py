# hybrid_auto_teleop.py
# Auto-straight by default; switch to manual on key press; revert to auto after idle.
# If stopinput == [24,0,0], override with STOP->TURN->STRAIGHT sequence.
# Windows-only (msvcrt). For Mac/Linux, swap msvcrt with pynput.

import time
import msvcrt
from Controller import UDP_Controller, DataType

# ---- network ----
IP, PORT = "0.0.0.0", 8400

# ---- auto mode ----
FORWARD_SPEED = 6.0
AUTO_DT       = 0.02

# ---- manual mode ----
MAX_SPEED = 7.0
STEP      = 1.0
DECAY     = 0.96
MANUAL_DT = 0.01

# ---- switching behavior ----
IDLE_BACK_TO_AUTO = 2.0

# ---- stopinput sequence ----
STOP_TIME      = 1.0
TURN_TIME      = 1.5
STRAIGHT_TIME  = 2.0
TURN_SPEED     = 3.0   # wheel speed for turn (-90 in place)
STRAIGHT_SPEED = 5.0   # wheel speed for straight move

def clip(v, lo, hi): return max(lo, min(hi, v))

def run():
    ctrl = UDP_Controller(ip=IP, port=PORT)
    ctrl.addVariable("left_speed",  DataType.FLOAT, 0.0)
    ctrl.addVariable("right_speed", DataType.FLOAT, 0.0)
    ctrl.addVariable("sensor",      DataType.STRING, "")
    ctrl.addVariable("stopinput",   DataType.STRING, "")   # will receive "[24,0,0]" as string
    ctrl.start()

    mode = "AUTO"
    left = right = 0.0
    last_key_time = 0.0
    last_hud = 0.0

    # sequence state
    seq_state   = "IDLE"  # IDLE->STOP->TURN->STRAIGHT->IDLE
    seq_timer   = 0.0
    seq_active  = False   # running sequence
    seq_armed   = True    # <--- one-shot latch: only the FIRST trigger is accepted
    prev_stop_high = False  # for rising-edge detect

    # --- print-on-change state for raw_stop ---
    prev_raw_stop = object()  # sentinel so first value always prints

    print(f"""
Hybrid controller running.
AUTO = straight at {FORWARD_SPEED}. MANUAL on any key; back to AUTO after {IDLE_BACK_TO_AUTO}s idle.
If stopinput = [24,0,0] => overrides everything: STOP->TURN->STRAIGHT (one-shot).

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
            now = time.time()

            # --- check stopinput first ---
            raw_stop = ctrl.getValue("stopinput")

            # print only when raw_stop changes
            if raw_stop != prev_raw_stop:
                print("raw_stop:", raw_stop)
                prev_raw_stop = raw_stop

            # parse stopinput
            try:
                stop_vec = eval(raw_stop) if isinstance(raw_stop, str) else raw_stop
            except Exception:
                stop_vec = [0,0,0]

            stop_high = isinstance(stop_vec, (list, tuple)) and len(stop_vec) > 0 and float(stop_vec[0]) >= 24.0
            rising_edge = stop_high and not prev_stop_high
            prev_stop_high = stop_high  # update edge detector each loop

            # only trigger ONCE per run (seq_armed) and only on rising edge
            if seq_armed and not seq_active and seq_state == "IDLE" and rising_edge:
                seq_active = True
                seq_armed  = False   # <--- PERMANENTLY disarm after first trigger
                seq_state  = "STOP"
                seq_timer  = 0.0
                print("\n[SEQ] Triggered by stopinput [24,0,0] (one-shot)")

            # --- if in override sequence ---
            if seq_state != "IDLE":
                seq_timer += AUTO_DT
                if seq_state == "STOP" and seq_timer >= STOP_TIME:
                    seq_state, seq_timer = "TURN", 0.0
                elif seq_state == "TURN" and seq_timer >= TURN_TIME:
                    seq_state, seq_timer = "STRAIGHT", 0.0
                elif seq_state == "STRAIGHT" and seq_timer >= STRAIGHT_TIME:
                    seq_state, seq_timer = "IDLE", 0.0
                    seq_active = False  # finished; still disarmed (one-shot)

                # command outputs based on seq_state
                if seq_state == "STOP":
                    left = right = 0.0
                elif seq_state == "TURN":
                    left, right = +TURN_SPEED, -TURN_SPEED
                elif seq_state == "STRAIGHT":
                    left = right = STRAIGHT_SPEED

                ctrl.setValue("left_speed", left)
                ctrl.setValue("right_speed", right)
                time.sleep(AUTO_DT)
                continue  # skip manual/auto control until sequence done

            # --- manual key read ---
            key_seen = False
            while msvcrt.kbhit():
                key_seen = True
                ch = msvcrt.getch()
                if ch in (b'\xe0', b'\x00'):
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

            # --- switching logic ---
            if key_seen:
                mode = "MANUAL"
                last_key_time = now
            else:
                if mode == "MANUAL" and (now - last_key_time) >= IDLE_BACK_TO_AUTO:
                    mode = "AUTO"
                    left = right = 0.0

            # --- control update ---
            if mode == "AUTO":
                left = right = FORWARD_SPEED
                ctrl.setValue("left_speed", left)
                ctrl.setValue("right_speed", right)
                dt = AUTO_DT
            else:
                left  *= DECAY
                right *= DECAY
                if abs(left)  < 1e-3: left  = 0.0
                if abs(right) < 1e-3: right = 0.0
                ctrl.setValue("left_speed", left)
                ctrl.setValue("right_speed", right)
                dt = MANUAL_DT

            # --- HUD (no stopinput here to avoid extra prints) ---
            if now - last_hud > 0.3:
                print(f"[{mode}] L={left:+.2f} R={right:+.2f}             ", end="\r")
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
