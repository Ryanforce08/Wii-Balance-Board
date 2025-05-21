import platform
import threading
import pygame
import sys
import time
import math

raw_data = [0.0, 0.0, 0.0, 0.0]  # TL, TR, BL, BR
aButton = False

if platform.system() == "Linux":
    import evdev
    import uinput
    from evdev import ecodes

    device = None

    def create_virtual_joystick():
        events = [
            uinput.ABS_X + (0, 255, 0, 0),
            uinput.ABS_Y + (0, 255, 0, 0),
            uinput.BTN_A,
        ]
        return uinput.Device(events, name="Wii Balance Board HID")

    def send_hid_output(device):
        total_weight = sum(raw_data)
        if total_weight <= 5:
            total_weight = 0.0000000001  # Prevent divide-by-zero

        top = raw_data[0] + raw_data[1]
        bottom = raw_data[2] + raw_data[3]
        left = raw_data[0] + raw_data[2]
        right = raw_data[1] + raw_data[3]

        x = (right - left) / total_weight
        y = (top - bottom) / total_weight

        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))

        joy_x = int((x + 1) * 127.5)
        joy_y = int((y + 1) * 127.5)

        device.emit(uinput.ABS_X, joy_x)
        device.emit(uinput.ABS_Y, joy_y)

    def start_board_reader():
        global device
        device = create_virtual_joystick()

        def get_board_device():
            devices = [d for d in evdev.list_devices()
                       if evdev.InputDevice(d).name == "Nintendo Wii Remote Balance Board"]
            return evdev.InputDevice(devices[0]) if devices else None

        print("Waiting for Balance Board (Linux)...")
        board = None
        while not board:
            board = get_board_device()
            time.sleep(0.5)
        print("Balance Board found.")

        for event in board.read_loop():
            if event.type != ecodes.EV_ABS:
                continue

            if event.code == ecodes.ABS_HAT1X:
                raw_data[0] = (event.value / 100) * 2.2046
            elif event.code == ecodes.ABS_HAT0X:
                raw_data[1] = (event.value / 100) * 2.2046
            elif event.code == ecodes.ABS_HAT1Y:
                raw_data[2] = (event.value / 100) * 2.2046
            elif event.code == ecodes.ABS_HAT0Y:
                raw_data[3] = (event.value / 100) * 2.2046
            elif event.code == ecodes.BTN_A:
                global aButton
                aButton = event.value
                device.emit(uinput.BTN_A, aButton)

            send_hid_output(device)

elif platform.system() == "Windows":
    import pywinusb.hid as hid
    import pyvjoy

    j = pyvjoy.VJoyDevice(1)

    def parse_balance_board(data):
        # Report ID 0x32 has weight info at fixed locations
        top_left = (data[4] << 8 | data[5]) / 100.0 * 2.2046
        top_right = (data[6] << 8 | data[7]) / 100.0 * 2.2046
        bottom_left = (data[8] << 8 | data[9]) / 100.0 * 2.2046
        bottom_right = (data[10] << 8 | data[11]) / 100.0 * 2.2046
        return [top_left, top_right, bottom_left, bottom_right]

    def send_joystick_output():
        total_weight = sum(raw_data)
        if total_weight <= 5:
            total_weight = 0.0000000001

        top = raw_data[0] + raw_data[1]
        bottom = raw_data[2] + raw_data[3]
        left = raw_data[0] + raw_data[2]
        right = raw_data[1] + raw_data[3]

        x = (right - left) / total_weight
        y = (top - bottom) / total_weight

        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))

        joy_x = int((x + 1) * 16383.5)
        joy_y = int((y + 1) * 16383.5)

        j.set_axis(pyvjoy.HID_USAGE_X, joy_x)
        j.set_axis(pyvjoy.HID_USAGE_Y, joy_y)

        j.set_button(1, 1 if aButton else 0)

    def balance_board_handler(data):
        global raw_data
        try:
            raw_data[:] = parse_balance_board(data)
            send_joystick_output()
        except Exception as e:
            print("Parse error:", e)

    def find_balance_board():
        all_hids = hid.find_all_hid_devices()
        for dev in all_hids:
            if dev.vendor_id == 0x057e and dev.product_id == 0x0306:
                return dev
        return None

    def start_board_reader():
        print("Waiting for Balance Board (Windows)...")
        board = None
        while not board:
            board = find_balance_board()
            time.sleep(0.5)
        print("Balance Board found.")

        board.open()
        board.set_raw_data_handler(lambda data: balance_board_handler(data.raw_data))

### --- Pygame GUI ---
def draw_board(screen, font):
    screen.fill((30, 30, 30))
    w, h = screen.get_size()

    board_rect = pygame.Rect(w // 4, h // 4, w // 2, h // 2)
    pygame.draw.rect(screen, (200, 200, 200), board_rect, border_radius=20)

    pad_radius = 30
    sensor_positions = [
        (board_rect.left + pad_radius, board_rect.top + pad_radius),
        (board_rect.right - pad_radius, board_rect.top + pad_radius),
        (board_rect.left + pad_radius, board_rect.bottom - pad_radius),
        (board_rect.right - pad_radius, board_rect.bottom - pad_radius),
    ]

    max_val = max(max(raw_data), 1.0)
    total_weight = sum(raw_data)

    for i, pos in enumerate(sensor_positions):
        intensity = min(255, int(255 * (raw_data[i] / max_val)))
        color = (intensity, 100, 255 - intensity)
        pygame.draw.circle(screen, color, pos, pad_radius)
        label = font.render(f"{raw_data[i]:.1f} Lbs", True, (0, 0, 0))
        screen.blit(label, (pos[0] - 20, pos[1] - 10))

    if total_weight > 0:
        top = raw_data[0] + raw_data[1]
        bottom = raw_data[2] + raw_data[3]
        left = raw_data[0] + raw_data[2]
        right = raw_data[1] + raw_data[3]

        x = (right - left) / total_weight
        y = (bottom - top) / total_weight

        cx = board_rect.centerx + int((board_rect.width // 2 - 20) * x)
        cy = board_rect.centery + int((board_rect.height // 2 - 20) * y)
        pygame.draw.circle(screen, (255, 0, 0), (cx, cy), 10)

    weight = font.render(f"Total Weight: {total_weight:.1f} Lbs", True, (255, 255, 255))
    screen.blit(weight, (w // 2 - 80, int(h * 0.85)))
    pygame.display.flip()


### --- Main Loop ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((600, 600))
    pygame.display.set_caption("Wii Balance Board Visualizer + HID")
    font = pygame.font.SysFont(None, 24)

    reader_thread = threading.Thread(target=start_board_reader, daemon=True)
    reader_thread.start()

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        draw_board(screen, font)
        clock.tick(30)

if __name__ == "__main__":
    main()
