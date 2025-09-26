# hybrid_auto_teleop.py
# Auto-straight by default; switch to manual on key press; revert to auto after idle.
# If stopinput == [24,0,0], override with STOP->TURN->STRAIGHT sequence.
# After 4s from the first [24,0,0], DISABLE AUTO (manual only).
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
TURN_SPEED     = 3  # wheel speed for turn (-90 in place)
STRAIGHT_SPEED = 3
  # wheel speed for straight move

# ---- auto lockout after first stop event ----
AUTO_LOCKOUT_AFTER = 6.0  # seconds after first [24,0,0] to disable AUTO

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
    seq_armed   = True    # one-shot latch for the first trigger only
    prev_stop_high = False  # for rising-edge detect

    # first stop trigger timing (for auto lockout)
    first_stop_time = None
    auto_blocked = False  # when True, AUTO is disabled (manual-only)

    # --- print-on-change state for raw_stop ---
    prev_raw_stop = object()  # sentinel so first value always prints

    print(f"""
Hybrid controller running.
AUTO = straight at {FORWARD_SPEED}. MANUAL on any key; back to AUTO after {IDLE_BACK_TO_AUTO}s idle.
If stopinput = [24,0,0] => STOP->TURN->STRAIGHT (one-shot).
After {AUTO_LOCKOUT_AFTER}s from first [24,0,0], AUTO is disabled (manual-only).
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
                seq_armed  = False                 # permanently disarm sequence re-triggers
                seq_state  = "STOP"
                seq_timer  = 0.0
                if first_stop_time is None:
                    first_stop_time = now          # start lockout timer
                print("\n[SEQ] Triggered by stopinput [24,0,0] (one-shot)")

            # --- enforce auto lockout after first stop event ---
            if (not auto_blocked) and (first_stop_time is not None) and (now - first_stop_time >= AUTO_LOCKOUT_AFTER):
                auto_blocked = True
                # stop the robot if it was cruising in AUTO and switch to MANUAL-only
                left = right = 0.0
                mode = "MANUAL"
                print("\n[AUTO LOCKOUT] AUTO disabled; manual-only control now.")

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
                # only return to AUTO if not blocked
                if (mode == "MANUAL") and (now - last_key_time) >= IDLE_BACK_TO_AUTO and (not auto_blocked):
                    mode = "AUTO"
                    left = right = 0.0

            # --- control update ---
            if mode == "AUTO":
                # if auto is blocked, ensure no motion
                if auto_blocked:
                    left = right = 0.0
                else:
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

            # --- HUD ---
            if now - last_hud > 0.3:
                auto_flag = "LOCKED" if auto_blocked else "OK"
                print(f"[{mode} | AUTO:{auto_flag}] L={left:+.2f} R={right:+.2f}   ", end="\r")
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
