import cv2
import mediapipe as mp
import socket
import time

HOST = '127.0.0.1'
PORT = 8888

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((HOST, PORT))
print("[Face Client] Connected to server.")

mp_face = mp.solutions.face_mesh
face_mesh = mp_face.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True)
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)
last_nose_y = None
last_jaw_x = None
last_sent = None
gesture_cooldown = 1.0  # 减少冷却时间
last_time_sent = time.time()

# 用于显示效果的变量
displayed_gesture = None
display_start_time = None
display_duration = 2.0  # 显示持续时间（秒）
debug_mode = False

# 改进的手势检测参数
nose_threshold = 0.015  # 降低阈值，提高敏感度
jaw_threshold = 0.02
history_length = 5  # 保存历史数据用于更稳定的检测

# 历史数据
nose_history = []
jaw_history = []

def smooth_detection(current_value, history, threshold, gesture_type):
    """使用历史数据进行平滑检测"""
    history.append(current_value)
    if len(history) > history_length:
        history.pop(0)
    
    if len(history) < 3:
        return False
    
    if gesture_type == 'yes':
        # 检测连续的向下运动（点头）
        recent_changes = [history[i] - history[i-1] for i in range(1, len(history))]
        positive_changes = [change for change in recent_changes if change > threshold]
        return len(positive_changes) >= 2  # 至少2次连续向下运动
    
    elif gesture_type == 'no':
        # 检测左右摆动（摇头）
        recent_changes = [abs(history[i] - history[i-1]) for i in range(1, len(history))]
        large_changes = [change for change in recent_changes if change > threshold]
        return len(large_changes) >= 2  # 至少2次大幅度左右运动

# 修改手势到命令的映射
def map_gesture_to_command(gesture):
    """将面部手势映射到机器狗命令"""
    gesture_map = {
        'yes': 'open',    # 点头 → 前进
        'no': 'fist'      # 摇头 → 后退
    }
    return gesture_map.get(gesture)

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = face_mesh.process(rgb)
    
    gesture = None
    current_time = time.time()
    
    if result.multi_face_landmarks:
        lm = result.multi_face_landmarks[0].landmark
        nose_y = lm[1].y  # 鼻尖
        jaw_x = lm[152].x  # 下巴
        
        # 使用改进的检测方法
        if smooth_detection(nose_y, nose_history, nose_threshold, 'yes'):
            gesture = 'yes'
        elif smooth_detection(jaw_x, jaw_history, jaw_threshold, 'no'):
            gesture = 'no'
        
        # 调试信息
        if debug_mode and len(nose_history) > 1:
            nose_change = nose_y - nose_history[-2] if len(nose_history) > 1 else 0
            jaw_change = abs(jaw_x - jaw_history[-2]) if len(jaw_history) > 1 else 0
            print(f"Nose change: {nose_change:.4f}, Jaw change: {jaw_change:.4f}")
    
    # 发送手势到服务器
    if gesture and gesture != last_sent and current_time - last_time_sent > gesture_cooldown:
        command = map_gesture_to_command(gesture)
        if command:
            sock.sendall(command.encode())
            print(f"[Face Client] Sent gesture: {gesture} -> {command}")
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
    
    # 显示手势信息
    gesture_text = f"Gesture: {current_display_gesture}"
    cv2.putText(frame, gesture_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2)
    
    # 显示说明文字 - 更新为新的映射
    instructions = [
        "Face Gestures:",
        "Nod (Yes): Move Forward",
        "Shake head (No): Move Backward",
        "",
        "Hand gestures available too:",
        "Open hand = Forward",
        "Fist = Backward", 
        "Thumbs up = Stand",
        "Thumbs down = Sit",
        "Point up = Stop",
        "",
        "Instructions:",
        "- Face the camera clearly",
        "- Make deliberate movements",
        "- Hold gesture for 1-2 sec",
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
        elif "Nod" in instruction:
            color = (0, 255, 0)  # 绿色
        elif "Shake head" in instruction:
            color = (0, 0, 255)  # 红色
            
        cv2.putText(frame, instruction, (400, 50 + i * 22), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    # 显示连接状态
    cv2.putText(frame, "Connected to server", (20, 80), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # 显示冷却状态
    time_since_last = current_time - last_time_sent
    if time_since_last < gesture_cooldown:
        cooldown_text = f"Cooldown: {gesture_cooldown - time_since_last:.1f}s"
        cv2.putText(frame, cooldown_text, (20, 110), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
    cv2.imshow("Face Gesture Client", frame)
    if cv2.waitKey(5) & 0xFF == 27:  # ESC键退出
        break

cap.release()
sock.close()
cv2.destroyAllWindows()
