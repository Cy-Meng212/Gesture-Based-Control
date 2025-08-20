import socket
import threading
import dog_control  # 使用增强版的dog_control

HOST = '0.0.0.0'
PORT = 8888

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)  # 可同时接受多个 client

print("[Listening] Waiting for clients...")
print("Supported commands:")
print(" Hand/Face gestures: open (forward), fist (backward), pointing_up (stop)")
print(" Hand gestures: thumbs_up -> yes (stand), thumbs_down -> no (sit)")
print(" Emotions (3 types): angry_reaction, sad_reaction, happy_reaction")

last_gesture = None
lock = threading.Lock()

def handle_client(conn, addr):
    global last_gesture
    print(f"[Connected] {addr}")
    
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                print(f"[Disconnected] {addr}")
                break
            
            # 处理接收到的文本
            text = data.decode(errors='ignore').strip().lower()
            if not text:
                continue
            
            # 拆分粘包（按行或空格）
            gestures = []
            for line in text.splitlines():
                gestures.extend(line.split())
            
            for gesture in gestures:
                with lock:
                    if gesture == last_gesture:
                        print(f"[Ignored] Gesture '{gesture}' (duplicate)")
                        continue
                    last_gesture = gesture
                
                print(f"[Gesture] ({addr}) => {gesture}")
                
                # 调用对应的动作 - 更新后的映射
                if gesture == 'open':
                    dog_control.move_forward()
                elif gesture == 'fist':
                    dog_control.move_backward()
                elif gesture == 'pointing_up':
                    dog_control.stop()
                elif gesture == 'yes':
                    dog_control.stand()
                elif gesture == 'no':
                    dog_control.sit()
                # 情绪反应命令 - 只支持3种情绪
                elif gesture == 'angry_reaction':
                    dog_control.angry_reaction()
                elif gesture == 'sad_reaction':
                    dog_control.sad_reaction()
                elif gesture == 'happy_reaction':
                    dog_control.happy_reaction()
                else:
                    print(f"[Warning] Unknown gesture: '{gesture}'")
                    dog_control.unknown()
                    
    except Exception as e:
        print(f"[Error] {addr} - {e}")
    finally:
        conn.close()
        print(f"[Connection Closed] {addr}")

# 主线程：等待多个 client
try:
    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
except KeyboardInterrupt:
    print("\n[Interrupted] Server shutting down...")
finally:
    server_socket.close()
    print("[Closed] Server socket closed.")