# Wii Balance Board Visualizer + HID for Linux

This project turns a **Wii Balance Board** into a virtual **HID joystick** on **Linux**, while providing a real-time visualizer using **Pygame**. It reads pressure data from the board's four sensors, calculates the user's center of pressure, and sends that as joystick input via `uinput`.

> **Note:** This only works on Linux systems due to reliance on `evdev` and `uinput`.

---

## Features

- Reads weight data from Wii Balance Board using `evdev`
- Sends joystick-like HID input via `uinput`
- Visualizes individual sensor data and user weight distribution with Pygame
- Computes and displays the center of pressure

---

## Requirements

- **Linux OS**
- Wii Balance Board connected via Bluetooth
- Python 3.7+
- System packages:
  - `libudev-dev`
  - `libevdev-dev`
- Python packages:
  ```bash
  pip install pygame evdev python-uinput
⚠️ You may need to run the script with sudo due to permissions required for evdev and uinput.

How It Works
Uses evdev to detect and read input from the Wii Balance Board.

Normalizes sensor data into X/Y axes representing the user's balance.

Sends these values to a virtual joystick using python-uinput.

Visualizes pressure and weight distribution in a 2D interface via pygame.

Usage
Connect your Wii Balance Board via Bluetooth.

Run the script:

bash
Copy
Edit
sudo python3 balance_board.py
Step onto the board and observe both:

Joystick movements (in compatible games or joystick testing tools)

Real-time visualization in the Pygame window

File Overview
File	Description
balance_board.py	Main script to run the visualizer and HID system
README.md	You're reading it

Notes
Joystick output is centered at (128,128) and scaled within the [0,255] range.

Total weight is shown in pounds (lbs), converted from the raw input.

Sensor layout:

less
Copy
Edit
TL —— TR
 |      |
BL —— BR
Center-of-pressure is indicated by a red dot.

Troubleshooting
Board not detected? Make sure it's connected and shows up via evdev-list-devices.

Permission errors? Run with sudo, or adjust udev rules to allow access without root.

No output? Confirm your system recognizes the Wii Balance Board and the correct input codes are being emitted.

Acknowledgments
Inspired by various open-source Wii Balance Board integrations

Thanks to the maintainers of evdev, python-uinput, and pygame