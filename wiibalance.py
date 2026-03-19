import platform
import sys
import threading
import time

import pygame

raw_data = [0.0, 0.0, 0.0, 0.0]  # TL, TR, BL, BR
filtered_raw = [0.0, 0.0, 0.0, 0.0]
aButton = False
tare_offset = [0.0, 0.0, 0.0, 0.0]
exact_mode = False
NOISE_FLOOR_LBS = 0.01       # drop tiny sensor drift in normal mode
NOISE_FLOOR_LBS_EXACT = 0.0001  # lighter floor in exact mode to keep precision
TARE_STEP = 0.1  # per-click tare adjustment in lbs
SMOOTH_ALPHA = 0.25  # 0=no smoothing, 1=no memory

BG_COLOR = (20, 24, 36)
BOARD_COLOR = (210, 215, 225)
PAD_BASE_COLOR = (80, 140, 220)
DOT_COLOR = (255, 70, 70)
TEXT_COLOR = (240, 240, 240)
BTN_COLOR = (60, 80, 120)
BTN_COLOR_HOVER = (90, 120, 170)
BTN_COLOR_ACTIVE = (120, 170, 80)


def _get_adjusted_data():
    # Subtract tare, then zero out tiny sensor drift using a small noise floor.
    floor = NOISE_FLOOR_LBS_EXACT if exact_mode else NOISE_FLOOR_LBS
    adjusted = [max(0.0, filtered_raw[i] - tare_offset[i]) for i in range(4)]
    return [0.0 if val < floor else val for val in adjusted]


def _update_filtered():
    for i in range(4):
        filtered_raw[i] = (SMOOTH_ALPHA * raw_data[i]) + ((1 - SMOOTH_ALPHA) * filtered_raw[i])

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
        adjusted = _get_adjusted_data()
        total_weight = sum(adjusted)
        if not exact_mode and total_weight <= 5:
            total_weight = 0.0000000001  # Prevent divide-by-zero while idle
        elif total_weight <= 0:
            total_weight = 0.0000000001

        top = adjusted[0] + adjusted[1]
        bottom = adjusted[2] + adjusted[3]
        left = adjusted[0] + adjusted[2]
        right = adjusted[1] + adjusted[3]

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
        # norm_data = [min(1.0, max(0.0, val / total_weight)) for val in adjusted]

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

            _update_filtered()
            send_hid_output(device)

### --- Windows Input (HID) + Output (vJoy) ---
elif platform.system() == "Windows":
    import hid
    import pyvjoy

    VJOY_DEVICE_ID = 1

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

    def _clamp_axis(val):
        return max(VJOY_MIN, min(VJOY_MAX, val))

    def _ensure_vjoy_device(device_id=VJOY_DEVICE_ID):
        try:
            j = pyvjoy.VJoyDevice(device_id)
            j.reset()
            # Center axes once to validate the device is usable.
            j.set_axis(pyvjoy.HID_USAGE_X, VJOY_CENTER)
            j.set_axis(pyvjoy.HID_USAGE_Y, VJOY_CENTER)
            return j
        except pyvjoy.exceptions.vJoyException:
            return None

    def create_virtual_joystick(max_wait=10.0, interval=1.0):
        start = time.time()
        attempt = 1
        while time.time() - start < max_wait:
            j = _ensure_vjoy_device()
            if j:
                return j
            print(
                f"vJoy device not available (attempt {attempt}). "
                "Open vJoyConf, ensure device 1 exists with X/Y axes enabled, "
                "then keep this app running—will retry."
            )
            attempt += 1
            time.sleep(interval)
        raise SystemExit("vJoy device missing; configure it in vJoyConf and rerun.")

    def send_hid_output(j):
        adjusted = _get_adjusted_data()
        total_weight = sum(adjusted)
        if not exact_mode and total_weight <= 5:
            total_weight = 0.0000000001  # Prevent divide-by-zero while idle
        elif total_weight <= 0:
            total_weight = 0.0000000001

        top = adjusted[0] + adjusted[1]
        bottom = adjusted[2] + adjusted[3]
        left = adjusted[0] + adjusted[2]
        right = adjusted[1] + adjusted[3]

        # Match red dot direction
        x = (right - left) / total_weight
        y = (top - bottom) / total_weight

        # Clamp to range [-1, 1]
        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))

        # Convert to vJoy range [0x1, 0x8000] where 0x4000 is center
        joy_x = _clamp_axis(int((x + 1.0) / 2.0 * (VJOY_MAX - VJOY_MIN) + VJOY_MIN))
        joy_y = _clamp_axis(int((y + 1.0) / 2.0 * (VJOY_MAX - VJOY_MIN) + VJOY_MIN))

        try:
            j.set_axis(pyvjoy.HID_USAGE_X, joy_x)
            j.set_axis(pyvjoy.HID_USAGE_Y, joy_y)
        except pyvjoy.exceptions.vJoyException:
            print(
                "vJoy rejected axis update. Attempting to reinitialize vJoy device..."
            )
            new_j = _ensure_vjoy_device()
            if new_j:
                joystick_handle = new_j
                joystick_handle.set_axis(pyvjoy.HID_USAGE_X, joy_x)
                joystick_handle.set_axis(pyvjoy.HID_USAGE_Y, joy_y)
                return joystick_handle
            print(
                "vJoy still unavailable. Verify vJoy service is running and device has X/Y axes enabled."
            )
            raise

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

                _update_filtered()
                send_hid_output(joystick)

            elif report_id == 0x20:
                # Status report — re-set reporting mode (board resets after sync)
                board.write(_pad_report([0x12, 0x04, 0x34]))


### --- Pygame Visualizer ---
def _layout_buttons(w, h, font, specs, max_cols=4):
    btn_w, btn_h = 140, 40
    spacing = 12
    layout = []
    rows = (len(specs) + max_cols - 1) // max_cols
    total_height = rows * btn_h + (rows - 1) * spacing
    start_y = h - total_height - 20
    for idx, spec in enumerate(specs):
        row = idx // max_cols
        col = idx % max_cols
        items_in_row = min(max_cols, len(specs) - row * max_cols)
        row_width = items_in_row * btn_w + (items_in_row - 1) * spacing
        start_x = (w - row_width) // 2
        rect = pygame.Rect(start_x + col * (btn_w + spacing), start_y + row * (btn_h + spacing), btn_w, btn_h)
        layout.append({"rect": rect, **spec})
    return layout


def _draw_button(screen, font, label, rect, active=False, hover=False):
    color = BTN_COLOR_ACTIVE if active else BTN_COLOR_HOVER if hover else BTN_COLOR
    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.rect(screen, (0, 0, 0), rect, width=2, border_radius=8)
    text = font.render(label, True, TEXT_COLOR)
    screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))


def draw_board(screen, font, button_layout, mouse_pos):
    screen.fill(BG_COLOR)
    w, h = screen.get_size()

    board_rect = pygame.Rect(w // 4, h // 4, w // 2, h // 2)
    pygame.draw.rect(screen, BOARD_COLOR, board_rect, border_radius=20)

    pad_radius = 30
    sensor_positions = [
        (board_rect.left + pad_radius, board_rect.top + pad_radius),  # TL
        (board_rect.right - pad_radius, board_rect.top + pad_radius),  # TR
        (board_rect.left + pad_radius, board_rect.bottom - pad_radius),  # BL
        (board_rect.right - pad_radius, board_rect.bottom - pad_radius),  # BR
    ]

    adjusted = _get_adjusted_data()
    max_val = max(max(adjusted), 1.0)
    total_weight = sum(adjusted)

    for i, pos in enumerate(sensor_positions):
        intensity = max(min(255, int(255 * (adjusted[i] / max_val))), 0)
        base = PAD_BASE_COLOR
        color = (
            min(255, base[0] + intensity // 3),
            min(255, base[1] + intensity // 4),
            min(255, base[2] + intensity // 5),
        )
        pygame.draw.circle(screen, color, pos, pad_radius)
        label = font.render(f"{adjusted[i]:.2f} lb", True, (10, 10, 10))
        screen.blit(label, (pos[0] - 28, pos[1] - 10))

    if total_weight > 0:
        top = adjusted[0] + adjusted[1]
        bottom = adjusted[2] + adjusted[3]
        left = adjusted[0] + adjusted[2]
        right = adjusted[1] + adjusted[3]

        x = (right - left) / total_weight
        y = (bottom - top) / total_weight

        cx = board_rect.centerx + int((board_rect.width // 2 - 20) * x)
        cy = board_rect.centery + int((board_rect.height // 2 - 20) * y)
        pygame.draw.circle(screen, DOT_COLOR, (cx, cy), 10)

    ounces = total_weight * 16.0
    weight = font.render(
        f"Total: {total_weight:.2f} Lbs / {ounces:.1f} oz   Mode: {'Exact' if exact_mode else 'Damped'}",
        True,
        TEXT_COLOR,
    )
    screen.blit(weight, (w // 2 - weight.get_width() // 2, board_rect.bottom + 10))

    # Draw buttons
    for btn in button_layout:
        hover = btn["rect"].collidepoint(mouse_pos)
        active = btn.get("active", False)
        _draw_button(screen, font, btn["label"], btn["rect"], active=active, hover=hover)

    pygame.display.flip()


### --- Main ---
def main():
    global exact_mode
    pygame.init()
    min_w, min_h = 600, 600
    screen = pygame.display.set_mode((700, 650), pygame.RESIZABLE)
    pygame.display.set_caption("Wii Balance Board Visualizer + HID")
    font = pygame.font.SysFont("Segoe UI", 24)

    button_specs = [
        {"label": "Tare", "action": "tare"},
        {"label": "Clear Tare", "action": "clear"},
        {"label": "Exact Mode", "action": "exact"},
        {"label": "TL +", "action": "corner", "corner": 0, "delta": TARE_STEP},
        {"label": "TL -", "action": "corner", "corner": 0, "delta": -TARE_STEP},
        {"label": "TR +", "action": "corner", "corner": 1, "delta": TARE_STEP},
        {"label": "TR -", "action": "corner", "corner": 1, "delta": -TARE_STEP},
        {"label": "BL +", "action": "corner", "corner": 2, "delta": TARE_STEP},
        {"label": "BL -", "action": "corner", "corner": 2, "delta": -TARE_STEP},
        {"label": "BR +", "action": "corner", "corner": 3, "delta": TARE_STEP},
        {"label": "BR -", "action": "corner", "corner": 3, "delta": -TARE_STEP},
    ]

    reader_thread = threading.Thread(target=start_board_reader, daemon=True)
    reader_thread.start()

    clock = pygame.time.Clock()
    while True:
        mouse_pos = pygame.mouse.get_pos()
        button_layout = _layout_buttons(*screen.get_size(), font, button_specs)
        # Mark active state for exact mode button
        for btn in button_layout:
            if btn["action"] == "exact":
                btn["active"] = exact_mode
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                new_w = max(min_w, event.w)
                new_h = max(min_h, event.h)
                screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for btn in button_layout:
                    if btn["rect"].collidepoint(event.pos):
                        if btn["action"] == "tare":
                            for i in range(4):
                                tare_offset[i] = raw_data[i]
                            print("Tare set to current readings.")
                        elif btn["action"] == "clear":
                            for i in range(4):
                                tare_offset[i] = 0.0
                            print("Tare reset to zero.")
                        elif btn["action"] == "exact":
                            exact_mode = not exact_mode
                            print(f"Exact mode {'ON' if exact_mode else 'OFF'}.")
                        elif btn["action"] == "corner":
                            idx = btn["corner"]
                            tare_offset[idx] = max(0.0, tare_offset[idx] + btn["delta"])
                            label = ["TL", "TR", "BL", "BR"][idx]
                            print(f"Tare {label} now {tare_offset[idx]:.2f} lb")
                        break
        draw_board(screen, font, button_layout, mouse_pos)
        clock.tick(30)


if __name__ == "__main__":
    main()
