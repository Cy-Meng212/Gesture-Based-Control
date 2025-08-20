# Gesture-Based-Control

#  Files

catkin_ws/src/unitree_ros/unitree_ros_to_real/unitree_legged_sdk/example_py/

server.py        # TCP server: receives gesture tokens, debounces, forwards to control

hand_client.py   # Client: camera + MediaPipe Hands → sends tokens over TCP

face_client.py   # Client: camera + head nod/shake detection → sends tokens

dog_control.py   # Maps tokens to Unitree SDK commands (sends UDP to the robot)


#Requirements

Python 3.8+

Python packages (minimum): pip install opencv-python mediapipe numpy

Unitree Legg#ed SDK installed on the machine that runs dog_control.py

To let dog_control.py reach the robot, the control computer must join the robot’s Wi-Fi hotspot:

SSID: Unitree_Go498507A

Password: 00000000


##Quick Start

1. Start the server
   
   cd catkin_ws/src/unitree_ros/unitree_ros_to_real/unitree_legged_sdk/example_py
   
   python server.py

3. Run the clients(hand/face)
   
   #terminal 2: hand gestures
   
   python hand_client.py
   
   #terminal 3: head gestures
   
   python face_client.py
   

