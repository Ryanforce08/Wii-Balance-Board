# Wii Balance Board Visualizer + HID

A cross-platform Python tool to interface with the Wii Balance Board, visualize weight distribution in real time, and expose the board as a virtual HID joystick/gamepad on both Linux and Windows.

## Features

- **Live Visualization**: Real-time display of weight on each sensor and the center of pressure.
- **Virtual Joystick (Linux)**: Emulates a joystick device using `uinput`, making the balance board compatible with many games and applications.
- **Virtual Joystick (Windows)**: Creates a virtual joystick via [vJoy](https://github.com/njz3/vJoy), no extra software beyond the vJoy driver required.
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

- [hidapi](https://pypi.org/project/hidapi/) — communicates with the Balance Board over Bluetooth HID
- [pyvjoy](https://pypi.org/project/pyvjoy/) — creates a virtual joystick via vJoy
- [vJoy driver](https://github.com/njz3/vJoy/releases) — **must be installed** for `pyvjoy` to work

#### Install vJoy driver:

1. Download the latest release from [vJoy releases](https://github.com/njz3/vJoy/releases).
2. Run the installer (enable at least 1 virtual device with X and Y axes + 1 button).
3. Reboot if prompted.

#### Install Python dependencies:

```bash
pip install pygame hidapi pyvjoy
```

#### Pairing the Balance Board on Windows:

1. Open **Settings → Bluetooth & devices → Add device**.
2. Press the **sync button** (red button inside the battery compartment) on the Balance Board.
3. Select **"Nintendo RVL-WBC-01"** when it appears.
4. The board may show as "not connected" after pairing — this is normal; the script will find it when you press sync again.

## Usage

1. **Connect** your Wii Balance Board via Bluetooth and ensure it is powered on.
2. **Run the script**:

```bash
python wii_balance_board_visualizer.py
```

- The UI window will show the board and live sensor readings.
- A virtual joystick/gamepad will be created automatically (Linux: uinput joystick, Windows: vJoy virtual joystick).

## Controls

- **A Button**: The board's front button is mapped to joystick button A (both Linux and Windows).

## Troubleshooting

- If the board is not found, ensure it is paired via Bluetooth and powered on.
- On Linux, you may need to run as root or grant access to `/dev/uinput` and `/dev/input` devices.
- On Windows, ensure [vJoy](https://github.com/njz3/vJoy/releases) is installed for virtual joystick support.
- On Windows, if the board is not found, try pressing the sync button again after starting the script.
- The script automatically detects your OS and loads the appropriate backend.

## Acknowledgements

- [vJoy](https://github.com/njz3/vJoy) and [pyvjoy](https://github.com/tidzo/pyvjoy) for virtual joystick support on Windows.
- `hidapi`, `evdev`, and `uinput` for device IO.
- Inspired by community efforts to make the Wii Balance Board accessible on PC.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

**Note:** This project is not affiliated with Nintendo.
