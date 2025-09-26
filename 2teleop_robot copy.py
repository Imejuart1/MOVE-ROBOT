# robot2_one_signal_manual_log.py
# Robot 2 (UDP 0.0.0.0:8500)
# Single-signal behavior:
#   • Start in AUTO: straight cruise.
#   • First 24V rising edge => STOP -> TURN LEFT (TURN_TIME) -> STRAIGHT 4s -> STOP.
#   • Then AUTO is disabled and MANUAL takes over (keys always available).
# Logging: only manual actions are logged (no other prints).

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
IDLE_BACK_TO_AUTO = 1.5   # only before the one-shot is completed

# ---- one-shot sequence ----
STOP_PAUSE      = 0.2     # brief stop before turning
TURN_TIME       = 1.5     # in-place left time
TURN_SPEED      = 2.7# in-place left: L=-, R=+
STRAIGHT_TIME   = 11
STRAIGHT_SPEED  = 3.5

# ---- edge handling ----
EDGE_DEBOUNCE   = 0.12    # seconds between accepted rising edges

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
    auto_enabled = True    # set False after the one-shot finishes

    # outputs
    left = right = FORWARD_SPEED  # start cruising immediately

    # one-shot state
    seq_state     = "IDLE"   # IDLE | STOP | TURN | STRAIGHT
    seq_timer     = 0.0
    sequence_done = False    # True after STRAIGHT completes

    # edge tracking
    last_edge_time = 0.0
    prev_high = stopinput_is_high24(ctrl.getValue("stopinput"))  # avoid false edge if high at boot

    # manual timing
    last_key_time = 0.0

    try:
        while True:
            now = time.time()

            # ---------- read stopinput & detect edge ----------
            raw = ctrl.getValue("stopinput")
            high = stopinput_is_high24(raw)
            rising = high and not prev_high and (now - last_edge_time >= EDGE_DEBOUNCE)
            prev_high = high
            if rising:
                last_edge_time = now

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
                # if operator grabs control mid-sequence, cancel it
                seq_state = "IDLE"
                seq_timer = 0.0
                last_key_time = now

            # ---------- AUTO logic (one-shot sequence) ----------
            if mode == "AUTO" and auto_enabled:
                if not sequence_done:
                    if seq_state == "IDLE":
                        if rising:
                            seq_state = "STOP"
                            seq_timer = 0.0
                            left = right = 0.0
                        else:
                            # keep cruising until event
                            left = right = FORWARD_SPEED
                    else:
                        # sequence running
                        seq_timer += AUTO_DT
                        if seq_state == "STOP":
                            left = right = 0.0
                            if seq_timer >= STOP_PAUSE:
                                seq_state, seq_timer = "TURN", 0.0
                        elif seq_state == "TURN":
                            left, right = -TURN_SPEED, +TURN_SPEED
                            if seq_timer >= TURN_TIME:
                                seq_state, seq_timer = "STRAIGHT", 0.0
                        elif seq_state == "STRAIGHT":
                            left = right = STRAIGHT_SPEED
                            if seq_timer >= STRAIGHT_TIME:
                                # sequence done -> stop and hand over to manual (auto disabled)
                                left = right = 0.0
                                sequence_done = True
                                auto_enabled = False
                                mode = "MANUAL"
                                seq_state, seq_timer = "IDLE", 0.0
                dt = AUTO_DT
            else:
                # MANUAL: decay toward zero unless keys are pressed
                left  *= DECAY
                right *= DECAY
                if abs(left)  < 1e-3: left  = 0.0
                if abs(right) < 1e-3: right = 0.0

                # Before the one-shot is done, allow return-to-auto after idle
                if (not sequence_done) and auto_enabled and (now - last_key_time) >= IDLE_BACK_TO_AUTO:
                    mode = "AUTO"
                    left = right = FORWARD_SPEED

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
        # manual_log(f"{time.time():.3f}s MANUAL stop")  # optional final log

if __name__ == "__main__":
    run()
