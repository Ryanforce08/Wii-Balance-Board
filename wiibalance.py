import platform
import threading
import pygame
import sys
import time
import math
import pywinusb.hid as hid

class WiiBalanceBoard:

    raw_data = [0.0, 0.0, 0.0, 0.0]  # TL, TR, BL, BR
    aButton = False

    def __init__(self,calibration_data  = {"top_left":[0, 0, 0],"top_right":[0, 0, 0],"bottom_left": [0, 0, 0],"bottom_right":[0, 0, 0],}) -> None:
        self.calibration = calibration_data

    def parse_balance_board(self,data: list[int]):
        if len(data) < 12:
            raise ValueError("Not enough data to parse Wii Balance Board report")

        top_right = (data[4] << 8) | data[5]
        bottom_right = (data[6] << 8) | data[7]
        top_left = (data[8] << 8) | data[9]
        bottom_left = (data[10] << 8) | data[11]
        
        return [
            top_left,
            top_right,
            bottom_left,
            bottom_right
        ]
    
    def interpolate(self, value, cal_0kg, cal_17kg, cal_34kg):
        # Prevent division by zero if calibration is not set
        if cal_17kg == cal_0kg or cal_34kg == cal_17kg:
            return 0.0
        if value < cal_17kg:
            return 17.0 * (value - cal_0kg) / (cal_17kg - cal_0kg)
        else:
            return 17.0 + 17.0 * (value - cal_17kg) / (cal_34kg - cal_17kg)

    def get_weights(self):
        return [
            self.interpolate(self.raw_data[0], *self.calibration["top_left"]),
            self.interpolate(self.raw_data[1], *self.calibration["top_right"]),
            self.interpolate(self.raw_data[2], *self.calibration["bottom_left"]),
            self.interpolate(self.raw_data[3], *self.calibration["bottom_right"])
        ]



    def find_balance_board(self):
        all_hids = hid.find_all_hid_devices()
        for dev in all_hids:
            if dev.vendor_id == 0x057e   and dev.product_id == 0x0306:
                return dev
        return None


    def balance_board_handler(self, data):
        try:
            self.raw_data = self.parse_balance_board(list(data))
            weights = self.get_weights()
            self.data = weights
        except Exception as e:
            print("Parse error:", e)

    def get_raw_data(self):
        return self.raw_data

    def _start_board_reader(self):
        print("Waiting for Balance Board (Windows)...")
        board = None
        while not board:
            board = self.find_balance_board()
            time.sleep(0.5)
        print("Balance Board found.")

        board.open()
        board.set_raw_data_handler(self.balance_board_handler)

    def _start_board_reader_cali(self):
        print("Waiting for Balance Board (Windows)...")
        board = None
        while not board:
            board = self.find_balance_board()
            time.sleep(0.5)
        print("Balance Board found.")

        board.open()
        board.set_raw_data_handler(self.parse_balance_board)

    def start(self):
        reader_thread = threading.Thread(target=self._start_board_reader, daemon=True)
        reader_thread.start()

    def start_cali(self):
        self._start_board_reader()



    # ### --- Linux Input + HID Output ---
    # if platform.system() == "Linux":
    #     import evdev
    #     import uinput
    #     from evdev import ecodes

    #     device = None

    #     def create_virtual_joystick(self):
    #         events = [
    #             self.uinput.ABS_X + (0, 255, 0, 0),
    #             self.uinput.ABS_Y + (0, 255, 0, 0),
    #             # uinput.ABS_RX + (0, 255, 0, 0),
    #             # uinput.ABS_RY + (0, 255, 0, 0),
    #             # uinput.ABS_Z + (0, 255, 0, 0),
    #             # uinput.ABS_RZ + (0, 255, 0, 0),
    #             self.uinput.BTN_A,
    #         ]
    #         return self.uinput.Device(events, name="Wii Balance Board HID")

    #     def send_hid_output(self,device):
    #         total_weight = sum(self.raw_data)
    #         if total_weight <= 5:
    #             total_weight = 0.0000000001  # Prevent divide-by-zero

    #         top = self.raw_data[0] + self.raw_data[1]
    #         bottom = self.raw_data[2] + self.raw_data[3]
    #         left = self.raw_data[0] + self.raw_data[2]
    #         right = self.raw_data[1] + self.raw_data[3]

    #         # Match red dot direction
    #         x = (right - left) / total_weight
    #         y = (top - bottom) / total_weight

    #         # Clamp to range [-1, 1]
    #         x = max(-1.0, min(1.0, x))
    #         y = max(-1.0, min(1.0, y))
    #         print(f"X: {x:.3f}, Y: {y:.3f}")

    #         # Convert to joystick range [0, 255] where 128 is center
    #         joy_x = int((x + 1) * 127.5)
    #         joy_y = int((y + 1) * 127.5)

    #         device.emit(self.uinput.ABS_X, joy_x)
    #         device.emit(self.uinput.ABS_Y, joy_y)

    #         # Send raw pressures as analogs
    #         # norm_data = [min(1.0, max(0.0, val / total_weight)) for val in raw_data]

    #         # device.emit(uinput.ABS_RX, int(norm_data[0] * 255))
    #         # device.emit(uinput.ABS_RY, int(norm_data[1] * 255))
    #         # device.emit(uinput.ABS_Z, int(norm_data[2] * 255))
    #         # device.emit(uinput.ABS_RZ, int(norm_data[3] * 255))

    #     def start_board_reader(self):
    #         global device
    #         device = self.create_virtual_joystick()
    #         self.send_hid_output(device)

    #         def get_board_device():
    #             devices = [
    #                 path
    #                 for path in self.evdev.list_devices()
    #                 if self.evdev.InputDevice(path).name == "Nintendo Wii Remote Balance Board"
    #             ]
    #             return self.evdev.InputDevice(devices[0]) if devices else None

    #         print("Waiting for balance board (Linux)...")
    #         board = None
    #         while not board:
    #             board = get_board_device()
    #             time.sleep(0.5)

    #         print("Balance board found, please step on.")

    #         while True:
    #             event = board.read_one()
    #             if event is None:
    #                 continue

    #             if event.code == self.ecodes.ABS_HAT1X:
    #                 self.raw_data[0] = (event.value / 100) * 2.2046
    #             elif event.code == self.ecodes.ABS_HAT0X:
    #                 self.raw_data[1] = (event.value / 100) * 2.2046
    #             elif event.code == self.ecodes.ABS_HAT1Y:
    #                 self.raw_data[2] = (event.value / 100) * 2.2046
    #             elif event.code == self.ecodes.ABS_HAT0Y:
    #                 self.raw_data[3] = (event.value / 100) * 2.2046
    #             elif event.code == self.ecodes.BTN_A:
    #                 aButton = event.value
    #                 if aButton:
    #                     device.emit(self.uinput.BTN_A, 1)
    #                 else:
    #                     device.emit(self.uinput.BTN_A, 0)

    #             self.send_hid_output(device)

    # elif platform.system() == "Windows":