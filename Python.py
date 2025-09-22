import time
from Controller import UDP_Controller

if __name__ == '__main__':

    _controller = UDP_Controller()
    _controller.addVariable("digital_inputs1", "byte", 0)
    _controller.addVariable("digital_inputs2", "byte", 0)
    _controller.addVariable("digital_outputs1", "byte", 0)
    _controller.addVariable("digital_outputs2", "byte", 0)
    _controller.addVariable("linear_drive", "int", 0)
    _controller.start()

    #Initialize variables
    object_count = 0
    temp_bool1 = False
    Count_Flag1 = False
        
    while True:
        #Reading inputs
        [IN7,IN6,IN5,IN4,IN3,Drive_Rev,Drive_Fwd,Toggle_Sw] = _controller.getMappedValue("digital_inputs1")     
        [IN15,IN14,IN13,IN12,IN11,IN10,IN9,IN8] = _controller.getMappedValue("digital_inputs2")     
        linear_drive = _controller.getValue("linear_drive") 
        
        #Start Conveyor
        Motor = Green_Indicator = Toggle_Sw
        Red_Indicator = not Motor
        
        #Drive
        Move_Fwd = Drive_Fwd
        Move_Rev = Drive_Rev
        
        if Move_Fwd or Move_Rev:
            print('Linear drive feedback:' + str(linear_drive))
        
        #Flag photo-electric sensor
        Count_Flag1 = IN8 and not temp_bool1
        temp_bool1 = IN8
        
        #Count non metal objects
        if Count_Flag1:
            object_count = object_count + 1
            print(object_count)
                 
        #Writing outputs
        _controller.setMappedValue("digital_outputs1", [False, Move_Fwd, Move_Rev, Red_Indicator, False, Green_Indicator, False, Motor])
        time.sleep(1e-5)