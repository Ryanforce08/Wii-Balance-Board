# Wii Balance Board Visualizer + HID

A cross-platform Python tool to interface with the Wii Balance Board, visualize weight distribution in real time, and expose the board as a virtual HID joystick/gamepad (on Linux) or pass data for use with [WiiBalanceWalker](https://github.com/lshachar/WiiBalanceWalker) (on Windows).

## Features

- **Live Visualization**: Real-time display of weight on each sensor and the center of pressure.
- **Virtual Joystick (Linux)**: Emulates a joystick device using `uinput`, making the balance board compatible with many games and applications.
- **Windows Support**: Reads Wii Balance Board sensor data and can work with WiiBalanceWalker for virtual joystick output.
- **Threaded Input**: Board input is read in a separate thread to keep the UI responsive.

## Requirements

### Common
- Python 3.7+
- [pygame](https://pypi.org/project/pygame/)

### Linux
- [evdev](https://pypi.org/project/evdev/)
- [python-uinput](https://pypi.org/project/python-uinput/)

#### Install dependencies:
```bash
pip install pygame evdev python-uinput
```

### Windows

- [pywinusb](https://pypi.org/project/pywinusb/)
- [WiiBalanceWalker](https://github.com/lshachar/WiiBalanceWalker) (required for virtual joystick/HID functionality)

#### Install dependencies:
```bash
pip install pygame pywinusb
```

#### Note:
- On Windows, this script only reads the board data. You **must** run [WiiBalanceWalker](https://github.com/lshachar/WiiBalanceWalker) to create a virtual joystick for use in games.
- Make sure your Wii Balance Board is paired and recognized by your PC.

## Usage

1. **Connect** your Wii Balance Board via Bluetooth and ensure it is powered on.
2. **Run the script**:

```bash
python wii_balance_board_visualizer.py
```

- The UI window will show the board and live sensor readings.
- For Linux, a virtual joystick device will be created; you can map this in games or other software.
- For Windows, see [WiiBalanceWalker](https://github.com/lshachar/WiiBalanceWalker) for creating a virtual joystick.

## Controls

- **A Button**: If your Balance Board has an 'A' button, its state is also sent as joystick button 0 (Linux only).

## Troubleshooting

- If the board is not found, ensure it is paired via Bluetooth and powered on.
- On Linux, you may need to run as root or grant access to `/dev/uinput` and `/dev/input` devices.
- On Windows, ensure [WiiBalanceWalker](https://github.com/lshachar/WiiBalanceWalker) is running if you need virtual joystick output.
- The script automatically detects your OS and loads the appropriate backend.

## Acknowledgements

- **WiiBalanceWalker** by [lshachar](https://github.com/lshachar/WiiBalanceWalker) for HID support on Windows.
- `pywinusb`, `evdev`, and `uinput` for device IO.
- Inspired by community efforts to make the Wii Balance Board accessible on PC.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

**Note:** This project is not affiliated with Nintendo.