import pygame
import asyncio
import random


class point:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def in_bound(self, width, height):
        return (0 <= self.x and self.x < width) and (0 <= self.y and self.y < height)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __add__(self, other):
        return point(self.x + other.x, self.y + other.y)


cell = 50
width = 15
height = 9
turn = 0.2
dx = [1, 0, -1, 0]
dy = [0, 1, 0, -1]
ds = [point(dx[i], dy[i]) for i in range(4)]
key_to_dir = {pygame.K_RIGHT: 0, pygame.K_UP: 3, pygame.K_LEFT: 2, pygame.K_DOWN: 1}


class fake_server:
    def clear(self):
        snake_row = height // 2
        self.snake = [point(0, snake_row), point(1, snake_row), point(2, snake_row)]
        self.end_game = False
        self.apple = self._get_apple_pos()
        self.pause = False

    def __init__(self, width, height):
        assert width >= 8 and height >= 5
        self.width = width
        self.height = height

        self.clear()

    def _make_field(self):
        field = [[0] * height for _ in range(width)]
        if self.apple.in_bound(self.width, self.height):
            field[self.apple.x][self.apple.y] = 3
        for p in self.snake:
            self.end_game = self.end_game or not (p.in_bound(width, height))
            if not (p.in_bound(width, height)):
                continue
            if field[p.x][p.y] != 0:
                self.end_game = True
            field[p.x][p.y] = 1
            if p == self.snake[-1]:
                field[p.x][p.y] = 2
        return field

    def _get_apple_pos(self):
        self.apple = point(-1, -1)
        field = self._make_field()
        free = []
        for x in range(width):
            for y in range(height):
                if field[x][y] == 0:
                    free.append(point(x, y))
        if len(free) == 0:
            self.end_game = True
            return point(-1, -1)
        else:
            return random.choice(free)

    async def get_state(self):
        await asyncio.sleep(turn)
        if not (self.end_game):
            if self.pause:
                return "pause"
            else:
                return "ok"
        else:
            return "stop"

    async def get_field(self, dir):
        self.snake.append(self.snake[-1] + ds[dir])
        if self.snake[-1] == self.apple:
            self.apple = self._get_apple_pos()
        else:
            self.snake = self.snake[1:]
        return self._make_field()

    async def send_continue(self):
        if self.end_game:
            self.clear()

    async def send_pause(self):
        if not (self.end_game):
            if self.pause:
                self.pause = False
            else:
                self.pause = True


pygame.init()
screen = pygame.display.set_mode((cell * width, cell * height))
pygame.display.set_caption("snake.mini")

server = fake_server(width, height)
running = True
dir_basic = key_to_dir[pygame.K_RIGHT]
prev_dir = dir_basic
state = "ok"
code_to_color = {0: (128, 128, 128), 1: (0, 255, 0), 2: (20, 230, 20), 3: (255, 0, 0)}
que = []
while running:
    state = asyncio.run(server.get_state())
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in key_to_dir:
                if state == "ok":
                    new_dir = key_to_dir[event.key]
                    last_dir = prev_dir
                    if len(que) > 0:
                        last_dir = que[-1]
                    if (new_dir + last_dir) % 2 == 1 and len(que) < 3:
                        que.append(new_dir)
            elif event.key == pygame.K_SPACE:
                if state == "stop":
                    asyncio.run(server.send_continue())
                    prev_dir = dir_basic
                elif state == "ok" or state == "pause":
                    asyncio.run(server.send_pause())
    if state == "stop" or state == "pause":
        continue
    dir = prev_dir
    if len(que) > 0:
        dir = que[0]
        que = que[1:]
    field = asyncio.run(server.get_field(dir))
    prev_dir = dir
    for x in range(width):
        for y in range(height):
            pygame.draw.rect(
                screen, code_to_color[field[x][y]], (x * cell, y * cell, cell, cell)
            )
    pygame.display.flip()
