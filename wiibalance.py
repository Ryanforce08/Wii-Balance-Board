import platform
import sys
import threading
import time

import pygame

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

### --- Windows Input (HID) + Output (vJoy) ---
elif platform.system() == "Windows":
    import hid
    import pyvjoy

    NINTENDO_VID = 0x057E
    BALANCE_BOARD_PID = 0x0306

    joystick = None

    # vJoy axis range: 0x1 to 0x8000 (1 to 32768), center = 0x4000 (16384)
    VJOY_MIN = 0x1
    VJOY_MAX = 0x8000
    VJOY_CENTER = 0x4000

    # Default calibration values (overwritten when board is read)
    # Each sensor has 3 calibration points: [0 kg, 17 kg, 34 kg]
    calibration = {
        "TR": [7500, 13000, 18500],
        "BR": [7500, 13000, 18500],
        "TL": [7500, 13000, 18500],
        "BL": [7500, 13000, 18500],
    }

    def create_virtual_joystick():
        """Acquire vJoy device 1."""
        j = pyvjoy.VJoyDevice(1)
        j.reset()
        return j

    def send_hid_output(j):
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

        # Convert to vJoy range [0x1, 0x8000] where 0x4000 is center
        joy_x = int((x + 1.0) / 2.0 * (VJOY_MAX - VJOY_MIN) + VJOY_MIN)
        joy_y = int((y + 1.0) / 2.0 * (VJOY_MAX - VJOY_MIN) + VJOY_MIN)

        j.set_axis(pyvjoy.HID_USAGE_X, joy_x)
        j.set_axis(pyvjoy.HID_USAGE_Y, joy_y)

    # -- Wiimote HID protocol helpers --

    def _pad_report(data, size=22):
        """Pad an output report to the Wiimote output report size."""
        return data + [0x00] * (size - len(data))

    def _write_register(board, address, data_bytes):
        """Write data to a Wiimote register (report 0x16)."""
        addr = [(address >> 16) & 0xFF, (address >> 8) & 0xFF, address & 0xFF]
        report = [0x16, 0x04] + addr + [len(data_bytes)] + list(data_bytes)
        board.write(_pad_report(report))

    def _read_register(board, address, size):
        """Request a read from a Wiimote register (report 0x17)."""
        addr = [(address >> 16) & 0xFF, (address >> 8) & 0xFF, address & 0xFF]
        size_bytes = [(size >> 8) & 0xFF, size & 0xFF]
        report = [0x17, 0x04] + addr + size_bytes
        board.write(_pad_report(report))

    def _wait_for_report(board, report_id, timeout=2.0):
        """Read until a specific input report arrives, or timeout."""
        board.set_nonblocking(True)
        start = time.time()
        while time.time() - start < timeout:
            data = board.read(64)
            if data and data[0] == report_id:
                board.set_nonblocking(False)
                return data
            time.sleep(0.01)
        board.set_nonblocking(False)
        return None

    def _read_calibration(board):
        """Read calibration data from the balance board extension registers."""
        global calibration
        cal_raw = bytearray(32)

        # First chunk: 16 bytes from 0xA40024
        _read_register(board, 0xA40024, 0x10)
        resp = _wait_for_report(board, 0x21)
        if resp:
            n = ((resp[3] >> 4) & 0x0F) + 1
            cal_raw[0:n] = bytes(resp[6 : 6 + n])

        # Second chunk: 8 bytes from 0xA40034
        _read_register(board, 0xA40034, 0x08)
        resp = _wait_for_report(board, 0x21)
        if resp:
            n = ((resp[3] >> 4) & 0x0F) + 1
            cal_raw[16 : 16 + n] = bytes(resp[6 : 6 + n])

        # Parse: 3 groups (0 kg, 17 kg, 34 kg) × 4 sensors × 2 bytes BE
        sensors = ["TR", "BR", "TL", "BL"]
        for group in range(3):
            for i, sensor in enumerate(sensors):
                offset = group * 8 + i * 2
                val = (cal_raw[offset] << 8) | cal_raw[offset + 1]
                if val != 0:
                    calibration[sensor][group] = val

        print(f"Calibration loaded: {calibration}")

    def _calc_weight(raw_val, sensor):
        """Convert a raw sensor value to pounds using calibration data."""
        cal = calibration[sensor]
        if raw_val < cal[1]:
            if cal[1] == cal[0]:
                return 0.0
            kg = 17.0 * (raw_val - cal[0]) / (cal[1] - cal[0])
        else:
            if cal[2] == cal[1]:
                return 17.0 * 2.20462
            kg = 17.0 + 17.0 * (raw_val - cal[1]) / (cal[2] - cal[1])
        return max(0.0, kg * 2.20462)

    def start_board_reader():
        global joystick, aButton

        joystick = create_virtual_joystick()
        send_hid_output(joystick)

        print("Waiting for balance board (Windows)...")
        print("Make sure the board is paired via Bluetooth and press the sync button.")

        board = None
        while board is None:
            for dev_info in hid.enumerate(NINTENDO_VID, BALANCE_BOARD_PID):
                try:
                    board = hid.device()
                    board.open_path(dev_info["path"])
                    board.set_nonblocking(False)
                    name = dev_info.get("product_string", "Wii Balance Board")
                    print(f"Found: {name}")
                    break
                except Exception as e:
                    print(f"Could not open device: {e}")
                    board = None
            if board is None:
                time.sleep(1.0)

        # Initialize the extension controller (new-style init)
        _write_register(board, 0xA400F0, [0x55])
        time.sleep(0.1)
        _write_register(board, 0xA400FB, [0x00])
        time.sleep(0.1)

        # Read calibration data
        _read_calibration(board)

        # Set data reporting mode: continuous, 0x34 = buttons + 19 ext bytes
        board.write(_pad_report([0x12, 0x04, 0x34]))
        time.sleep(0.1)

        # Turn on LED 1 so user knows we're connected
        board.write(_pad_report([0x11, 0x10]))

        print("Balance board initialized, please step on.")

        board.set_nonblocking(False)
        while True:
            try:
                data = board.read(64)
            except Exception:
                print("Board disconnected, attempting to reconnect...")
                board = None
                while board is None:
                    for dev_info in hid.enumerate(NINTENDO_VID, BALANCE_BOARD_PID):
                        try:
                            board = hid.device()
                            board.open_path(dev_info["path"])
                            board.set_nonblocking(False)
                            print("Reconnected!")
                            board.write(_pad_report([0x12, 0x04, 0x34]))
                            break
                        except Exception:
                            board = None
                    if board is None:
                        time.sleep(1.0)
                continue

            if not data or len(data) < 12:
                continue

            report_id = data[0]

            if report_id == 0x34:
                # Button data — A button is bit 3 of byte 2
                new_a = bool(data[2] & 0x08)
                if new_a != aButton:
                    aButton = new_a
                    joystick.set_button(1, int(aButton))

                # Extension data: 4 sensors × 2 bytes big-endian starting at byte 3
                tr = (data[3] << 8) | data[4]
                br = (data[5] << 8) | data[6]
                tl = (data[7] << 8) | data[8]
                bl = (data[9] << 8) | data[10]

                raw_data[0] = _calc_weight(tl, "TL")
                raw_data[1] = _calc_weight(tr, "TR")
                raw_data[2] = _calc_weight(bl, "BL")
                raw_data[3] = _calc_weight(br, "BR")

                send_hid_output(joystick)

            elif report_id == 0x20:
                # Status report — re-set reporting mode (board resets after sync)
                board.write(_pad_report([0x12, 0x04, 0x34]))


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
        intensity = max(min(255, int(255 * (raw_data[i] / max_val))), 0)
        color = (intensity, 100, max(min(abs(255 - intensity), 255), 0))
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
