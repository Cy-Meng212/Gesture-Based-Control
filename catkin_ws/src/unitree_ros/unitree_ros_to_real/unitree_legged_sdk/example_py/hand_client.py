import cv2
import mediapipe as mp
import socket
import time
import math
import numpy as np

HOST = '127.0.0.1'
PORT = 8888

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))
print("[Hand Client] Connected to server.")

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.8, min_tracking_confidence=0.8)
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)
last_sent = None
gesture_cooldown = 1.0  # 减少冷却时间
last_time_sent = time.time()
debug_mode = False

# 用于显示效果的变量
displayed_gesture = None
display_start_time = None
display_duration = 2.0  # 显示持续时间（秒）

def calculate_angle(a, b, c):
    """计算三点之间的角度"""
    a = np.array([a.x, a.y])
    b = np.array([b.x, b.y])
    c = np.array([c.x, c.y])
    
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    
    if angle > 180.0:
        angle = 360 - angle
        
    return angle

def finger_is_extended(landmarks, finger_indices):
    """检查手指是否伸直 - 基于角度计算"""
    mcp, pip, dip, tip = finger_indices
    angle = calculate_angle(landmarks[mcp], landmarks[pip], landmarks[tip])
    return angle > 160  # 角度大于160度认为是伸直

def thumb_is_extended_up(landmarks):
    """检查拇指是否向上伸直"""
    thumb_cmc = landmarks[1]
    thumb_mcp = landmarks[2] 
    thumb_ip = landmarks[3]
    thumb_tip = landmarks[4]
    
    # 拇指向上：tip的y坐标应该小于mcp的y坐标
    vertical_check = thumb_tip.y < thumb_mcp.y - 0.05
    
    # 角度检查：拇指应该是伸直的
    angle = calculate_angle(thumb_mcp, thumb_ip, thumb_tip)
    straight_check = angle > 150
    
    # 方向检查：拇指应该指向上方
    direction_vector_y = thumb_mcp.y - thumb_tip.y
    direction_check = direction_vector_y > 0.08
    
    return vertical_check and straight_check and direction_check

def thumb_is_extended_down(landmarks):
    """检查拇指是否向下伸直"""
    thumb_mcp = landmarks[2]
    thumb_ip = landmarks[3] 
    thumb_tip = landmarks[4]
    
    # 拇指向下：tip的y坐标应该大于mcp的y坐标
    vertical_check = thumb_tip.y > thumb_mcp.y + 0.05
    
    # 角度检查
    angle = calculate_angle(thumb_mcp, thumb_ip, thumb_tip)
    straight_check = angle > 150
    
    # 方向检查
    direction_vector_y = thumb_tip.y - thumb_mcp.y  
    direction_check = direction_vector_y > 0.08
    
    return vertical_check and straight_check and direction_check

def is_fist(landmarks):
    """检测握拳 - 所有手指都弯曲"""
    finger_indices = [
        [5, 6, 7, 8],    # 食指
        [9, 10, 11, 12], # 中指  
        [13, 14, 15, 16], # 无名指
        [17, 18, 19, 20]  # 小指
    ]
    
    # 检查所有手指都弯曲
    all_fingers_bent = True
    for finger in finger_indices:
        if finger_is_extended(landmarks, finger):
            all_fingers_bent = False
            break
    
    # 拇指检查 - 拇指应该贴在其他手指上（不向上也不向下伸直）
    thumb_not_up = not thumb_is_extended_up(landmarks)
    thumb_not_down = not thumb_is_extended_down(landmarks)
    thumb_check = thumb_not_up and thumb_not_down
    
    # 额外检查：所有指尖都应该接近手掌
    fingertips = [8, 12, 16, 20]
    palm_center = landmarks[0]  # 手腕作为参考
    tips_close_to_palm = all(
        abs(landmarks[tip].y - palm_center.y) < 0.15 for tip in fingertips
    )
    
    return all_fingers_bent and thumb_check and tips_close_to_palm

def is_open(landmarks):
    """检测张开手掌 - 所有手指都伸直分开"""
    finger_indices = [
        [5, 6, 7, 8],    # 食指
        [9, 10, 11, 12], # 中指
        [13, 14, 15, 16], # 无名指  
        [17, 18, 19, 20]  # 小指
    ]
    
    # 检查所有手指都伸直
    all_fingers_extended = all(
        finger_is_extended(landmarks, finger) for finger in finger_indices
    )
    
    # 拇指也要伸直（但不一定向上）
    thumb_angle = calculate_angle(landmarks[2], landmarks[3], landmarks[4])
    thumb_extended = thumb_angle > 140
    
    # 检查手指分开程度
    fingertips = [4, 8, 12, 16, 20]
    spread_distances = []
    for i in range(len(fingertips) - 1):
        dist = abs(landmarks[fingertips[i]].x - landmarks[fingertips[i+1]].x)
        spread_distances.append(dist)
    
    fingers_spread = all(dist > 0.03 for dist in spread_distances)
    
    return all_fingers_extended and thumb_extended and fingers_spread

def is_thumbs_up(landmarks):
    """检测竖拇指 - 只有拇指向上，其他手指弯曲"""
    # 拇指必须向上伸直
    thumb_up = thumb_is_extended_up(landmarks)
    
    # 其他四指必须弯曲
    finger_indices = [
        [5, 6, 7, 8],    # 食指
        [9, 10, 11, 12], # 中指
        [13, 14, 15, 16], # 无名指
        [17, 18, 19, 20]  # 小指
    ]
    
    other_fingers_bent = all(
        not finger_is_extended(landmarks, finger) for finger in finger_indices
    )
    
    # 额外检查：拇指应该是最高的点
    thumb_tip = landmarks[4]
    other_fingertips = [8, 12, 16, 20]
    thumb_highest = all(
        thumb_tip.y < landmarks[tip].y - 0.03 for tip in other_fingertips
    )
    
    return thumb_up and other_fingers_bent and thumb_highest

def is_thumbs_down(landmarks):
    """检测拇指向下 - 只有拇指向下，其他手指弯曲"""
    # 拇指必须向下伸直
    thumb_down = thumb_is_extended_down(landmarks)
    
    # 其他四指必须弯曲
    finger_indices = [
        [5, 6, 7, 8],    # 食指
        [9, 10, 11, 12], # 中指
        [13, 14, 15, 16], # 无名指
        [17, 18, 19, 20]  # 小指
    ]
    
    other_fingers_bent = all(
        not finger_is_extended(landmarks, finger) for finger in finger_indices
    )
    
    # 额外检查：拇指应该是最低的点
    thumb_tip = landmarks[4]
    other_fingertips = [8, 12, 16, 20]
    thumb_lowest = all(
        thumb_tip.y > landmarks[tip].y + 0.03 for tip in other_fingertips
    )
    
    return thumb_down and other_fingers_bent and thumb_lowest

def is_pointing_up(landmarks):
    """检测竖食指 - 只有食指向上，其他手指弯曲"""
    # 食指必须伸直向上
    index_extended = finger_is_extended(landmarks, [5, 6, 7, 8])
    index_tip = landmarks[8]
    index_mcp = landmarks[5]
    index_pointing_up = index_tip.y < index_mcp.y - 0.05
    
    # 其他手指必须弯曲（包括拇指）
    other_finger_indices = [
        [9, 10, 11, 12], # 中指
        [13, 14, 15, 16], # 无名指
        [17, 18, 19, 20]  # 小指
    ]
    
    other_fingers_bent = all(
        not finger_is_extended(landmarks, finger) for finger in other_finger_indices
    )
    
    # 拇指不能向上伸直
    thumb_not_up = not thumb_is_extended_up(landmarks)
    
    # 食指应该是最高的点
    other_fingertips = [4, 12, 16, 20]
    index_highest = all(
        index_tip.y < landmarks[tip].y - 0.03 for tip in other_fingertips
    )
    
    return index_extended and index_pointing_up and other_fingers_bent and thumb_not_up and index_highest

# 修改手势到命令的映射
def map_gesture_to_command(gesture):
    """将手势映射到机器狗命令"""
    gesture_map = {
        'open': 'open',           # 张开手掌 → 前进
        'fist': 'fist',           # 握拳 → 后退
        'thumbs_up': 'yes',       # 竖拇指 → 站立
        'thumbs_down': 'no',      # 拇指向下 → 蹲下
        'pointing_up': 'pointing_up'  # 食指向上 → 停止
    }
    return gesture_map.get(gesture)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)
    
    gesture = None
    confidence_scores = {}
    current_time = time.time()
    
    if result.multi_hand_landmarks:
        for hl in result.multi_hand_landmarks:
            # 绘制手部关键点
            mp_drawing.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)
            
            # 计算每种手势的置信度（用于调试）
            confidence_scores = {
                'fist': is_fist(hl.landmark),
                'open': is_open(hl.landmark),
                'thumbs_up': is_thumbs_up(hl.landmark),
                'thumbs_down': is_thumbs_down(hl.landmark),
                'pointing_up': is_pointing_up(hl.landmark)
            }
            
            # 严格的优先级检测 - 最特殊的手势优先
            if confidence_scores['pointing_up']:
                gesture = 'pointing_up'
            elif confidence_scores['thumbs_up']:
                gesture = 'thumbs_up'
            elif confidence_scores['thumbs_down']:
                gesture = 'thumbs_down'
            elif confidence_scores['fist']:
                gesture = 'fist'
            elif confidence_scores['open']:
                gesture = 'open'
            
            # 调试信息
            if debug_mode:
                print(f"Gesture confidence: {confidence_scores}")
                if gesture:
                    print(f"Detected gesture: {gesture}")
    
    # 发送手势到服务器
    if gesture and gesture != last_sent and current_time - last_time_sent > gesture_cooldown:
        command = map_gesture_to_command(gesture)
        if command:
            sock.sendall(command.encode())
            print(f"[Hand Client] Sent gesture: {gesture} -> {command}")
            last_sent = gesture
            last_time_sent = current_time
            
            # 设置显示效果
            displayed_gesture = f"{gesture} -> {command}"
            display_start_time = current_time
    
    # 确定当前显示的手势和颜色
    current_display_gesture = None
    text_color = (128, 128, 128)  # 默认灰色
    
    if displayed_gesture and display_start_time:
        if current_time - display_start_time < display_duration:
            # 在显示持续时间内，显示绿色
            current_display_gesture = displayed_gesture
            text_color = (0, 255, 0)  # 绿色
        else:
            # 超过显示时间，清除显示
            displayed_gesture = None
            display_start_time = None
    
    # 如果没有显示的手势，显示当前检测状态
    if not current_display_gesture:
        current_display_gesture = gesture if gesture else "None"
        if gesture:
            text_color = (0, 255, 255)  # 黄色表示检测到但未发送
        else:
            text_color = (128, 128, 128)  # 灰色表示无检测
    
    # 显示主要手势信息
    gesture_text = f"Gesture: {current_display_gesture}"
    cv2.putText(frame, gesture_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2)
    
    # 显示手势说明 - 更新为新的映射
    instructions = [
        "Hand Gestures:",
        "Open Hand: Move Forward",
        "Fist: Move Backward", 
        "Thumbs Up: Stand",
        "Thumbs Down: Sit",
        "Point Up: Stop Movement",
        "",
        "Instructions:",
        "- Show clear gestures",
        "- Hold for 1-2 seconds",
        "- Good lighting helps",
        "",
        "Colors:",
        "Green = Action sent",
        "Yellow = Detected", 
        "Gray = No gesture"
    ]
    
    for i, instruction in enumerate(instructions):
        if instruction == "":  # 空行
            continue
        color = (255, 255, 255)
        if "Green" in instruction:
            color = (0, 255, 0)
        elif "Yellow" in instruction:
            color = (0, 255, 255)
        elif "Gray" in instruction:
            color = (128, 128, 128)
        elif "Open Hand" in instruction:
            color = (0, 255, 0)  # 绿色
        elif "Fist" in instruction:
            color = (0, 0, 255)  # 红色
        elif "Thumbs Up" in instruction:
            color = (255, 255, 0)  # 青色
        elif "Thumbs Down" in instruction:
            color = (0, 165, 255)  # 橙色
        elif "Point Up" in instruction:
            color = (128, 0, 128)  # 紫色
            
        cv2.putText(frame, instruction, (400, 50 + i * 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    
    # 显示连接状态
    cv2.putText(frame, "Connected to server", (20, 80), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # 显示冷却状态
    time_since_last = current_time - last_time_sent
    if time_since_last < gesture_cooldown:
        cooldown_text = f"Cooldown: {gesture_cooldown - time_since_last:.1f}s"
        cv2.putText(frame, cooldown_text, (20, 110), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
    cv2.imshow("Hand Gesture Client", frame)
    if cv2.waitKey(5) & 0xFF == 27:  # ESC键退出
        break

cap.release()
sock.close()
cv2.destroyAllWindows()
