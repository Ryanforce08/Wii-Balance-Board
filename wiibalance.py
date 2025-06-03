import platform
import threading
import pygame
import sys
import time
import math

raw_data = [0.0, 0.0, 0.0, 0.0]  # TL, TR, BL, BR
aButton = False

### --- Linux Input + HID Output ---
if platform.system() == "Linux":
    import evdev
    import uinput
    from evdev import ecodes

    device = None

    def create_virtual_joystick():
        events = [
            uinput.ABS_X + (0, 255, 0, 0),
            uinput.ABS_Y + (0, 255, 0, 0),
            # uinput.ABS_RX + (0, 255, 0, 0),
            # uinput.ABS_RY + (0, 255, 0, 0),
            # uinput.ABS_Z + (0, 255, 0, 0),
            # uinput.ABS_RZ + (0, 255, 0, 0),
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

        # Match red dot direction
        x = (right - left) / total_weight
        y = (top - bottom) / total_weight

        # Clamp to range [-1, 1]
        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))
        print(f"X: {x:.3f}, Y: {y:.3f}")

        # Convert to joystick range [0, 255] where 128 is center
        joy_x = int((x + 1) * 127.5)
        joy_y = int((y + 1) * 127.5)

        device.emit(uinput.ABS_X, joy_x)
        device.emit(uinput.ABS_Y, joy_y)

        # Send raw pressures as analogs
        # norm_data = [min(1.0, max(0.0, val / total_weight)) for val in raw_data]

        # device.emit(uinput.ABS_RX, int(norm_data[0] * 255))
        # device.emit(uinput.ABS_RY, int(norm_data[1] * 255))
        # device.emit(uinput.ABS_Z, int(norm_data[2] * 255))
        # device.emit(uinput.ABS_RZ, int(norm_data[3] * 255))

    def start_board_reader():
        global device
        device = create_virtual_joystick()
        send_hid_output(device)

        def get_board_device():
            devices = [
                path
                for path in evdev.list_devices()
                if evdev.InputDevice(path).name == "Nintendo Wii Remote Balance Board"
            ]
            return evdev.InputDevice(devices[0]) if devices else None

        print("Waiting for balance board (Linux)...")
        board = None
        while not board:
            board = get_board_device()
            time.sleep(0.5)

        print("Balance board found, please step on.")

        while True:
            event = board.read_one()
            if event is None:
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
                aButton = event.value
                if aButton:
                    device.emit(uinput.BTN_A, 1)
                else:
                    device.emit(uinput.BTN_A, 0)

            send_hid_output(device)

elif platform.system() == "Windows":
    import pywinusb.hid as hid

    USAGE_Z = 0x32
    USAGE_RX = 0x33
    USAGE_RY = 0x34
    USAGE_RZ = 0x35

    def parse_weights(data):
        if len(data) < 25:
            raise ValueError("Data too short")
        
        def get_weight(start):
            return int.from_bytes(data[start:start+4], byteorder="little") / 100 * 2.2046

        top_left = get_weight(9)
        top_right = get_weight(13)
        bottom_left = get_weight(17)
        bottom_right = get_weight(21)
        if sum([top_left, top_right, bottom_left, bottom_right]) < 3.0:
            return [0.0,0.0,0.0,0.0]

        return [top_left, top_right, bottom_left, bottom_right]

    def balance_board_handler(data):
        try:
            raw_data[:] = parse_weights(data)
            # print(raw_data)
        except Exception as e:
            print("Parse error:", e)

    def find_balance_board():
        all_hids = hid.find_all_hid_devices()
        for dev in all_hids:
            if dev.vendor_id == 0x1234 and dev.product_id == 0xbead:
                print(dev)
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
        board.set_raw_data_handler(balance_board_handler)
            
        

### --- Pygame Visualizer ---
def draw_board(screen, font):
    screen.fill((30, 30, 30))
    w, h = screen.get_size()

    board_rect = pygame.Rect(w // 4, h // 4, w // 2, h // 2)
    pygame.draw.rect(screen, (200, 200, 200), board_rect, border_radius=20)

    pad_radius = 30
    sensor_positions = [
        (board_rect.left + pad_radius, board_rect.top + pad_radius),  # TL
        (board_rect.right - pad_radius, board_rect.top + pad_radius),  # TR
        (board_rect.left + pad_radius, board_rect.bottom - pad_radius),  # BL
        (board_rect.right - pad_radius, board_rect.bottom - pad_radius),  # BR
    ]

    max_val = max(max(raw_data), 1.0)
    total_weight = sum(raw_data)

    for i, pos in enumerate(sensor_positions):
        intensity = max(min(255, int(255 * (raw_data[i] / max_val))),0)
        color = (intensity, 100, max(min(abs(255 - intensity),255),0))
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
    screen.blit(weight, (board_rect.right / 2, w / 1.25))
    pygame.display.flip()

### --- Main ---
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