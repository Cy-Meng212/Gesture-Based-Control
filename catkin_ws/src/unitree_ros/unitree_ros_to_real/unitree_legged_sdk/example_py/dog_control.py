#!/usr/bin/python

import time
import threading
import sys
import math

sys.path.append('../lib/python/amd64')
import robot_interface as sdk

# ========== UDP Setup ==========
HIGHLEVEL = 0xee
udp = sdk.UDP(HIGHLEVEL, 8080, "192.168.123.161", 8082)

cmd = sdk.HighCmd()
state = sdk.HighState()
udp.InitCmdData(cmd)

# ========== Thread Lock ==========
is_busy = False
lock = threading.Lock()

# ========== Speed Control ==========
current_speed = 0.2  # 默认速度
speed_increment = 0.1
max_speed = 0.5
min_speed = 0.1

# ========== Continuous Movement Control ==========
is_moving = False
movement_direction = 0  # 0: stopped, 1: forward, -1: backward
movement_thread = None
stop_movement = False

def _init_cmd_fields():
    """初始化所有字段到官方示例的默认值"""
    cmd.mode = 0           # 0: idle/stand, 1: forced stand, 2: walk continous, …
    cmd.gaitType = 0
    cmd.speedLevel = 0
    cmd.footRaiseHeight = 0
    cmd.bodyHeight = 0.0
    cmd.euler = [0.0, 0.0, 0.0]
    cmd.velocity = [0.0, 0.0]
    cmd.yawSpeed = 0.0
    cmd.reserve = 0

def send_body_height(height, duration_ms=1000):
    """Send body height command to robot."""
    t0 = time.time()
    while (time.time() - t0) * 1000 < duration_ms:
        time.sleep(0.002)
        udp.Recv()
        udp.GetRecv(state)

        _init_cmd_fields()
        cmd.mode = 1               # forced stand
        cmd.bodyHeight = height

        udp.SetSend(cmd)
        udp.Send()

def send_euler(roll=0.0, pitch=0.0, yaw=0.0, duration_ms=500):
    """Send body orientation (euler angles) command to robot."""
    t0 = time.time()
    while (time.time() - t0) * 1000 < duration_ms:
        time.sleep(0.002)
        udp.Recv()
        udp.GetRecv(state)

        _init_cmd_fields()
        cmd.mode = 1               # forced stand
        cmd.euler = [roll, pitch, yaw]

        udp.SetSend(cmd)
        udp.Send()

def send_movement(vx=0.0, vy=0.0, vyaw=0.0, duration_ms=1000):
    """Send movement command to robot."""
    t0 = time.time()
    while (time.time() - t0) * 1000 < duration_ms:
        time.sleep(0.002)
        udp.Recv()
        udp.GetRecv(state)

        _init_cmd_fields()
        cmd.mode = 2               # continuous walk
        cmd.gaitType = 1           # trot gait
        cmd.velocity = [vx, vy]
        cmd.yawSpeed = vyaw

        udp.SetSend(cmd)
        udp.Send()

def send_stop(duration_ms=500):
    """Send stop command to robot (forced stand, zero velocity)."""
    t0 = time.time()
    while (time.time() - t0) * 1000 < duration_ms:
        time.sleep(0.002)
        udp.Recv()
        udp.GetRecv(state)

        _init_cmd_fields()
        cmd.mode = 1               # forced stand

        udp.SetSend(cmd)
        udp.Send()

def reset_pose(duration_ms=1000):
    """Reset robot pose to neutral (body height=0, euler=0)."""
    print("[Action] Resetting robot pose...")
    send_body_height(0.0, duration_ms)
    send_euler(0.0, 0.0, 0.0, duration_ms)
    print("[Action] Reset completed.")

def continuous_movement_loop():
    """连续运动循环 - 在独立线程中运行"""
    global is_moving, movement_direction, current_speed, stop_movement
    
    while not stop_movement:
        if is_moving and movement_direction != 0:
            try:
                time.sleep(0.002)
                udp.Recv()
                udp.GetRecv(state)

                _init_cmd_fields()
                cmd.mode = 2               # continuous walk
                cmd.gaitType = 1           # trot gait
                cmd.velocity = [current_speed * movement_direction, 0]

                udp.SetSend(cmd)
                udp.Send()
            except Exception as e:
                print(f"[Error] Movement loop error: {e}")
                break
        else:
            time.sleep(0.01)  # 短暂等待，避免占用过多CPU

def start_continuous_movement(direction):
    """开始连续运动"""
    global is_moving, movement_direction, movement_thread, stop_movement
    
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Cannot start movement.")
            return
        
        # 停止之前的运动
        stop_continuous_movement()
        
        is_moving = True
        movement_direction = direction
        stop_movement = False
        
        # 启动运动线程
        movement_thread = threading.Thread(target=continuous_movement_loop, daemon=True)
        movement_thread.start()
        
        direction_text = "forward" if direction == 1 else "backward"
        print(f"[Action] Starting continuous {direction_text} movement at speed {current_speed}")

def stop_continuous_movement():
    """停止连续运动"""
    global is_moving, movement_direction, stop_movement
    
    if is_moving:
        print("[Action] Stopping continuous movement...")
        is_moving = False
        movement_direction = 0
        stop_movement = True
        
        # 发送停止命令
        send_stop(200)
        print("[Action] Continuous movement stopped.")

# ========== Original API Functions ==========

def stand():
    """Command the robot to stand."""
    global is_busy
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Ignoring 'stand' command.")
            return
        is_busy = True

    try:
        # 先停止任何连续运动
        stop_continuous_movement()
        
        print("[Action] Robot dog is standing...")
        send_body_height(0.15, duration_ms=2000)
        print("[Action] Standing completed.")
        reset_pose(1000)
    finally:
        is_busy = False

def sit():
    """Command the robot to sit."""
    global is_busy
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Ignoring 'sit' command.")
            return
        is_busy = True

    try:
        # 先停止任何连续运动
        stop_continuous_movement()
        
        print("[Action] Robot dog is sitting...")
        send_body_height(-0.2, duration_ms=2000)
        print("[Action] Sitting completed.")
        reset_pose(1000)
    finally:
        is_busy = False

def move_forward():
    """开始连续前进"""
    start_continuous_movement(1)

def move_backward():
    """开始连续后退"""
    start_continuous_movement(-1)

def speed_up():
    """Increase robot movement speed."""
    global current_speed
    old_speed = current_speed
    current_speed = min(current_speed + speed_increment, max_speed)
    print(f"[Action] Speed increased from {old_speed:.1f} to {current_speed:.1f} m/s")
    
    # 如果正在运动，速度变化会立即生效
    if is_moving:
        direction_text = "forward" if movement_direction == 1 else "backward"
        print(f"[Action] Now moving {direction_text} at new speed {current_speed}")

def speed_down():
    """Decrease robot movement speed."""
    global current_speed
    old_speed = current_speed
    current_speed = max(current_speed - speed_increment, min_speed)
    print(f"[Action] Speed decreased from {old_speed:.1f} to {current_speed:.1f} m/s")
    
    # 如果正在运动，速度变化会立即生效
    if is_moving:
        direction_text = "forward" if movement_direction == 1 else "backward"
        print(f"[Action] Now moving {direction_text} at new speed {current_speed}")

def stop():
    """Command the robot to stop movement and stand."""
    global is_busy
    
    print("[Action] Robot dog is stopping...")
    stop_continuous_movement()
    
    with lock:
        is_busy = False  # 允许立即中断任何动作
    
    print("[Action] Stop completed.")

def unknown():
    """Handle unknown command."""
    print("[Warning] Received unknown gesture. No action taken.")

# ========== New Emotion Response Functions ==========

def angry_reaction():
    """生气反应：后退两步然后坐下"""
    global is_busy
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Ignoring 'angry_reaction' command.")
            return
        is_busy = True

    try:
        print("[Emotion] Angry reaction: backing away and sitting...")
        
        # 停止任何连续运动
        stop_continuous_movement()
        
        # 后退两步
        send_movement(vx=-0.3, duration_ms=2000)  # 后退2秒
        time.sleep(0.5)  # 短暂停顿
        
        # 坐下
        send_body_height(-0.2, duration_ms=2000)
        print("[Emotion] Angry reaction completed.")
        
    finally:
        is_busy = False

def sad_reaction():
    """悲伤反应：靠近两步然后坐下"""
    global is_busy
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Ignoring 'sad_reaction' command.")
            return
        is_busy = True

    try:
        print("[Emotion] Sad reaction: approaching and sitting...")
        
        # 停止任何连续运动
        stop_continuous_movement()
        
        # 靠近两步
        send_movement(vx=0.2, duration_ms=2000)  # 前进2秒
        time.sleep(0.5)  # 短暂停顿
        
        # 坐下
        send_body_height(-0.2, duration_ms=2000)
        print("[Emotion] Sad reaction completed.")
        
    finally:
        is_busy = False

def happy_reaction():
    """高兴反应：左右摇摆身体"""
    global is_busy
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Ignoring 'happy_reaction' command.")
            return
        is_busy = True

    try:
        print("[Emotion] Happy reaction: body swaying...")
        
        # 停止任何连续运动
        stop_continuous_movement()
        
        # 确保站立状态
        send_body_height(0.0, duration_ms=500)
        
        # 左右摇摆身体（通过roll角度）
        sway_cycles = 3  # 摇摆3次
        sway_angle = 0.35  # 摇摆角度（弧度）
        
        for i in range(sway_cycles):
            # 向左摇摆
            send_euler(roll=sway_angle, duration_ms=800)
            time.sleep(0.2)
            
            # 向右摇摆
            send_euler(roll=-sway_angle, duration_ms=800)
            time.sleep(0.2)
        
        # 回到中性位置
        send_euler(roll=0.0, duration_ms=500)
        print("[Emotion] Happy reaction completed.")
        
    finally:
        is_busy = False

def fear_reaction():
    """害怕反应：快速后退并蹲低"""
    global is_busy
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Ignoring 'fear_reaction' command.")
            return
        is_busy = True

    try:
        print("[Emotion] Fear reaction: retreating and crouching...")
        
        # 停止任何连续运动
        stop_continuous_movement()
        
        # 快速后退
        send_movement(vx=-0.4, duration_ms=1500)  # 快速后退1.5秒
        time.sleep(0.3)
        
        # 蹲得很低
        send_body_height(-0.25, duration_ms=1500)
        print("[Emotion] Fear reaction completed.")
        
    finally:
        is_busy = False

def surprise_reaction():
    """惊讶反应：快速站立"""
    global is_busy
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Ignoring 'surprise_reaction' command.")
            return
        is_busy = True

    try:
        print("[Emotion] Surprise reaction: quick standing...")
        
        # 停止任何连续运动
        stop_continuous_movement()
        
        # 快速站立到较高位置
        send_body_height(0.2, duration_ms=1000)  # 快速站高
        time.sleep(0.5)
        
        # 回到正常高度
        send_body_height(0.0, duration_ms=1000)
        print("[Emotion] Surprise reaction completed.")
        
    finally:
        is_busy = False

def disgust_reaction():
    """厌恶反应：转身避开"""
    global is_busy
    with lock:
        if is_busy:
            print("[Warning] Robot is busy. Ignoring 'disgust_reaction' command.")
            return
        is_busy = True

    try:
        print("[Emotion] Disgust reaction: turning away...")
        
        # 停止任何连续运动
        stop_continuous_movement()
        
        # 转身（yaw旋转）
        send_movement(vyaw=1.0, duration_ms=2000)  # 转身2秒
        time.sleep(0.5)
        
        # 稍微后退
        send_movement(vx=-0.2, duration_ms=1000)
        print("[Emotion] Disgust reaction completed.")
        
    finally:
        is_busy = False
        