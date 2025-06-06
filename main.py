import platform
import threading
import pygame
import sys
import time
import math

import wiibalance

wii = wiibalance.WiiBalanceBoard()

raw_data = wii.get_raw_data()

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
    wii.start()

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