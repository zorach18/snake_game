import pygame
import numpy as np

x_min, x_max = -1.0, 1.0
y_min, y_max = -1.5, 1.5
max_iter = 100
width, height = 800, 600
c_real_d, c_imag_d = 0.05, 0.05
c_real = -0.8
c_imag = 0.156
c_par = c_real + c_imag * 1j


def make_normal_scale():
    global x_min, x_max, y_min, y_max, width, height
    dx, dy = x_max - x_min, y_max - y_min
    mx, my = (x_max + x_min) / 2, (y_max + y_min) / 2
    sc = max(dx / width, dy / height)
    dx, dy = width * sc, height * sc
    x_min, x_max = mx - dx / 2, mx + dx / 2
    y_min, y_max = my - dy / 2, my + dy / 2


pygame.init()
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("Mandelbrot set")


def np_get_color(divergence, max_iter):
    normalized = divergence / max_iter

    colors = np.zeros((*divergence.shape, 3), dtype=np.uint8)
    colors[..., 0] = (normalized * 255).astype(np.uint8)
    colors[..., 1] = ((1 - normalized) * 128).astype(np.uint8)
    colors[..., 2] = (np.sin(normalized * 10) * 127 + 128).astype(np.uint8)
    colors[divergence == max_iter] = [0, 0, 0]

    return colors


def np_get_surface():
    make_normal_scale()
    print(f"x:[{x_min}, {x_max}]")
    print(f"y:[{y_min}, {y_max}]")
    print(f"c = {c_real} + {c_imag}i")
    x = np.linspace(x_min, x_max, width)
    y = np.linspace(y_min, y_max, height)
    z = x[:, None] + y * 1j

    c = np.full(z.shape, c_par, dtype=np.complex128)
    divergence = np.zeros(c.shape, dtype=int)

    for i in range(max_iter):
        mask = np.abs(z) <= 2
        z[mask] = z[mask] ** 2 + c[mask]
        divergence[mask] = i
    divergence[np.abs(z) <= 2] = max_iter
    colors = np_get_color(divergence, max_iter)
    return pygame.surfarray.make_surface(colors)


surface = np_get_surface()
print(type(surface))
screen.blit(surface, (0, 0))
pygame.display.flip()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            zoom = 1
            if event.button == 1:
                zoom = 0.5
            elif event.button == 3:
                zoom = 2.0
            else:
                continue
            x, y = event.pos
            x = x_min + (x_max - x_min) * x / width
            y = y_min + (y_max - y_min) * y / height
            x_min = x + (x_min - x) * zoom
            x_max = x + (x_max - x) * zoom
            y_min = y + (y_min - y) * zoom
            y_max = y + (y_max - y) * zoom
            surface = np_get_surface()
            screen.blit(surface, (0, 0))
            pygame.display.flip()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                c_real -= c_real_d
            elif event.key == pygame.K_RIGHT:
                c_real += c_real_d
            elif event.key == pygame.K_DOWN:
                c_imag -= c_imag_d
            elif event.key == pygame.K_UP:
                c_imag += c_imag_d
            else:
                continue
            c_par = c_real + c_imag * 1j
            surface = np_get_surface()
            screen.blit(surface, (0, 0))
            pygame.display.flip()
    pygame.time.delay(100)

pygame.quit()
