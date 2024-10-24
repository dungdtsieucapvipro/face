import cv2
import mediapipe as mp
import tkinter as tk
from tkinter import messagebox, Toplevel, Label, Entry, Button
from PIL import Image, ImageTk
import threading
import os
import json
import queue

# Khởi tạo Mediapipe và các mô-đun
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

# Đường dẫn lưu ảnh và thông tin
IMG_PATH = './imgs'
INFO_PATH = './face_info.json'

if not os.path.exists(IMG_PATH):
    os.makedirs(IMG_PATH)

# Biến điều khiển camera
cap = None
running = False
frame = None
face_info = {}  # Biến để lưu thông tin khuôn mặt (tên, tuổi và tọa độ)
face_queue = queue.Queue()  # Hàng đợi để lưu các khuôn mặt chưa có thông tin

# Hàm lưu thông tin khuôn mặt vào file JSON
def save_face_info_to_file():
    with open(INFO_PATH, 'w') as file:
        json.dump(face_info, file)

# Hàm tải thông tin khuôn mặt từ file JSON
def load_face_info_from_file():
    global face_info
    if os.path.exists(INFO_PATH):
        with open(INFO_PATH, 'r') as file:
            face_info = json.load(file)

# Hàm so sánh bounding box của khuôn mặt để tìm khuôn mặt đã được lưu
def is_same_face(new_bbox, saved_bbox):
    # Tính khoảng cách giữa các tọa độ
    threshold = 0.1  # Đặt một ngưỡng để so sánh
    return abs(new_bbox['xmin'] - saved_bbox['xmin']) < threshold and \
           abs(new_bbox['ymin'] - saved_bbox['ymin']) < threshold and \
           abs(new_bbox['width'] - saved_bbox['width']) < threshold and \
           abs(new_bbox['height'] - saved_bbox['height']) < threshold

# Hàm xử lý nhận diện khuôn mặt và thêm vào hàng đợi nếu chưa có thông tin
def capture_face():
    global frame
    if frame is not None:
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        with mp_face_detection.FaceDetection(min_detection_confidence=0.5) as face_detection:
            results = face_detection.process(image_rgb)
            if results.detections:
                for detection in results.detections:
                    # Lấy bounding box của khuôn mặt
                    bboxC = detection.location_data.relative_bounding_box
                    h, w, c = frame.shape
                    bbox = {
                        'xmin': bboxC.xmin,
                        'ymin': bboxC.ymin,
                        'width': bboxC.width,
                        'height': bboxC.height
                    }

                    # Kiểm tra xem khuôn mặt đã có trong face_info chưa
                    face_exists = False
                    for face_id, info in face_info.items():
                        if is_same_face(bbox, info['bbox']):
                            face_exists = True
                            break

                    # Nếu khuôn mặt chưa có, mở cửa sổ nhập thông tin và chụp ảnh
                    if not face_exists:
                        x, y, w_box, h_box = int(bboxC.xmin * w), int(bboxC.ymin * h), int(bboxC.width * w), int(bboxC.height * h)
                        face_img = frame[y:y + h_box, x:x + w_box]
                        open_info_window(face_img, bbox)
# Hàm xử lý lần lượt từng khuôn mặt chưa có thông tin
def process_next_face():
    if not face_queue.empty():
        face_img, bbox = face_queue.get()
        open_info_window(face_img, bbox)
    else:
        print("Hàng đợi khuôn mặt đã trống.")  # Khi không còn khuôn mặt nào trong hàng đợi

# Hàm mở cửa sổ nhập thông tin cho khuôn mặt mới
def open_info_window(face_img, face_bbox):
    def save_info():
        name = entry_name.get()
        age = entry_age.get()

        if not name or not age:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đầy đủ tên và tuổi.")
            return

        # Tạo một ID duy nhất cho khuôn mặt và lưu thông tin
        face_id = len(face_info) + 1
        face_info[face_id] = {'name': name, 'age': age, 'bbox': face_bbox}

        # Lưu ảnh khuôn mặt với tên và tuổi
        img_name = os.path.join(IMG_PATH, f"{name}_{age}.jpg")
        cv2.imwrite(img_name, face_img)

        # Lưu thông tin vào file
        save_face_info_to_file()

        messagebox.showinfo("Chụp Ảnh", f"Ảnh đã được lưu tại {img_name}")
        info_window.destroy()

        # Sau khi lưu thông tin, xử lý khuôn mặt tiếp theo trong hàng đợi
        process_next_face()

    # Tạo cửa sổ mới để nhập tên và tuổi
    info_window = Toplevel(root)
    info_window.title("Thông tin ảnh")

    Label(info_window, text="Tên:").grid(row=0, column=0)
    entry_name = Entry(info_window)
    entry_name.grid(row=0, column=1)

    Label(info_window, text="Tuổi:").grid(row=1, column=0)
    entry_age = Entry(info_window)
    entry_age.grid(row=1, column=1)

    # Hiển thị ảnh khuôn mặt đã cắt
    face_img_resized = cv2.resize(face_img, (150, 150))  # Thay đổi kích thước ảnh cho phù hợp
    face_img_tk = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(face_img_resized, cv2.COLOR_BGR2RGB)))

    Label(info_window, image=face_img_tk).grid(row=2, column=0, columnspan=2)
    info_window.image = face_img_tk  # Lưu tham chiếu để tránh ảnh bị xóa

    # Nút lưu thông tin
    Button(info_window, text="Lưu", command=save_info).grid(row=3, column=0, columnspan=2)

# Hàm bắt đầu camera
def start_program():
    global cap, running
    if not running:
        cap = cv2.VideoCapture(0)
        running = True
        threading.Thread(target=detect_face).start()

# Hàm xử lý nhận diện khuôn mặt
def detect_face():
    global cap, running, frame, face_info

    with mp_face_detection.FaceDetection(min_detection_confidence=0.5) as face_detection:
        while running and cap.isOpened():
            success, image = cap.read()
            if not success:
                print("Không thể lấy được khung hình từ camera.")
                break

            # Chuyển ảnh từ BGR sang RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Nhận diện khuôn mặt
            results = face_detection.process(image_rgb)

            # Vẽ các hộp bao quanh khuôn mặt được nhận diện và hiển thị thông tin
            if results.detections:
                for detection in results.detections:
                    mp_drawing.draw_detection(image, detection)

                    # Lấy bounding box của khuôn mặt
                    bboxC = detection.location_data.relative_bounding_box
                    h, w, c = image.shape
                    bbox = {
                        'xmin': bboxC.xmin,
                        'ymin': bboxC.ymin,
                        'width': bboxC.width,
                        'height': bboxC.height
                    }
                    x, y, w_box, h_box = int(bboxC.xmin * w), int(bboxC.ymin * h), int(bboxC.width * w), int(bboxC.height * h)

                    # Kiểm tra xem khuôn mặt đã có trong face_info không
                    for face_id, info in face_info.items():
                        if is_same_face(bbox, info['bbox']):
                            # Hiển thị tên và tuổi nếu đã lưu thông tin
                            text = f"{info['name']}, {info['age']} tuổi"
                            cv2.putText(image, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

            # Cập nhật khung hình hiện tại
            frame = image

            # Hiển thị khung hình đã nhận diện
            cv2.imshow('Face Detection', image)

            # Nhấn 'q' để thoát vòng lặp
            if cv2.waitKey(5) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

# Hàm dừng camera
def stop_program():
    global running
    if running:
        running = False

# Hàm thoát chương trình
def quit_program():
    stop_program()
    # Lưu thông tin vào file trước khi thoát chương trình
    save_face_info_to_file()
    root.quit()

# Tạo giao diện với Tkinter
root = tk.Tk()
root.title("Face Detection Program")

# Nút bắt đầu chương trình
btn_start = tk.Button(root, text="Chạy chương trình", command=start_program)
btn_start.pack(pady=10)

# Nút dừng chương trình
btn_stop = tk.Button(root, text="Dừng chương trình", command=stop_program)
btn_stop.pack(pady=10)

# Nút thoát chương trình
btn_quit = tk.Button(root, text="Thoát chương trình", command=quit_program)
btn_quit.pack(pady=10)

# Nút chụp ảnh khuôn mặt
btn_capture = tk.Button(root, text="Chụp ảnh khuôn mặt", command=capture_face)
btn_capture.pack(pady=10)

# Tải thông tin khuôn mặt từ file khi khởi động chương trình
load_face_info_from_file()

# Khởi chạy giao diện
root.mainloop()
