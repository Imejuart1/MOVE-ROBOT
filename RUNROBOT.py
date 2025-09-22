# mini_robot_udp.py
from Controller import UDP_Controller
import time

def parse_sensor(s):
    s = (s or "")[:8].ljust(8, "0")     # "01000000"
    return [1 if c == "1" else 0 for c in s]

BASE_SPEED = 0.6
STEER_GAIN = 0.4
WEIGHTS = [-3,-2,-1,-0.5, 0.5,1,2,3]    # left→right rays

if __name__ == "__main__":
    ctrl = UDP_Controller(ip="127.0.0.1", port=8400)  # must match the component
    ctrl.addVariable("sensor", "str", "")
    ctrl.addVariable("left_speed", "float", 0.0)
    ctrl.addVariable("right_speed", "float", 0.0)
    ctrl.start()  # opens the UDP link via Gateway  :contentReference[oaicite:6]{index=6}

    try:
        while True:
            bits = parse_sensor(ctrl.getValue("sensor"))
            steer = sum(w*b for w,b in zip(WEIGHTS, bits))
            left  = max(-1.0, min(1.0, BASE_SPEED - STEER_GAIN*steer))
            right = max(-1.0, min(1.0, BASE_SPEED + STEER_GAIN*steer))
            ctrl.setValue("left_speed", left)
            ctrl.setValue("right_speed", right)
            time.sleep(0.02)
    finally:
        ctrl.setValue("left_speed", 0.0)
        ctrl.setValue("right_speed", 0.0)
