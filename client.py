import asyncio
import socket
import pygame

TCP_PORT = 8888
UDP_PORT = 9999
DISCOVERY_REQUEST = b"DISCOVER_SNAKE_GAME"
DISCOVERY_RESPONSE_PREFIX = b"SNAKE_GAME_HERE"
BYTE_CODE_SHIFT = 100

key_to_dir = {
    pygame.K_RIGHT: "R",
    pygame.K_UP: "U",
    pygame.K_LEFT: "L",
    pygame.K_DOWN: "D",
}

code_to_color = {
    ".": (128, 128, 128),
    "A": (255, 0, 0),
    "c": (0, 255, 0),
    "C": (20, 230, 20),
    "d": (0, 0, 255),
    "D": (20, 20, 230),
}


class network_client:
    def __init__(self):
        self.state = "disconnected"
        self.reader = None
        self.writer = None

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()

    async def get_server_list(self, broadcast_addr, timeout=2.0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)

        loop = asyncio.get_event_loop()
        print(f"browsing servers on {broadcast_addr} ...")
        await loop.run_in_executor(
            None,
            sock.sendto,
            DISCOVERY_REQUEST,
            (broadcast_addr, UDP_PORT),
        )
        servers = []
        start_time = loop.time()
        while loop.time() - start_time < timeout:
            try:
                local_timout = timeout - (loop.time() - start_time)
                data = await asyncio.wait_for(
                    loop.sock_recv(sock, 1024), timeout=local_timout
                )
                if data.startswith(DISCOVERY_RESPONSE_PREFIX):
                    try:
                        parts = data.decode().split("|")
                        if len(parts) >= 3:
                            server_id, ip = parts[1], parts[2]
                            servers.append((ip, server_id))
                    except Exception:
                        pass
            except asyncio.TimeoutError:
                break
            except OSError as e:
                if hasattr(e, "winerror") and e.winerror == 10054:
                    print("aboba")
                    pass
                else:
                    raise
        sock.close()
        return servers

    async def choose_server(self):
        my_ip = self.get_local_ip()
        parts = my_ip.split(".")
        broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
        local_task = asyncio.create_task(self.get_server_list("127.0.0.1"))
        network_task = asyncio.create_task(self.get_server_list(broadcast))
        local_servers, network_servers = await asyncio.gather(
            local_task,
            network_task,
        )
        if len(local_servers) == 1:
            return local_servers[0][0]
        if len(network_servers) == 1:
            return network_servers[0][0]
        gen_count = len(local_servers) + len(network_servers)
        if gen_count == 0:
            raise Exception("There is no servers")
        else:
            raise Exception("More than 1 server")

    async def read(self):
        message = (await self.reader.readline()).decode().strip()
        if message == "":
            raise Exception("server closed connection")
        return message

    async def write(self, message):
        if not isinstance(message, str):
            raise Exception(f"{message} isn't a string")
        if not message:
            raise Exception(f"message mustn't be clear")
        self.writer.write(message.strip().encode() + b"\n")
        await self.writer.drain()

    async def create(self):
        print(self.get_local_ip())
        ip = await self.choose_server()
        reader, writer = await asyncio.open_connection(ip, TCP_PORT)
        self.reader = reader
        self.writer = writer
        init_message = await self.read()
        if init_message != "ok":
            raise Exception(init_message)
        self.state = "connected"
        print(f"connected to server {ip}:{TCP_PORT}")


class game_client:
    def __init__(self):
        pygame.init()
        self.cell = 50
        self.clock = pygame.time.Clock()

    def resize(self, grid_size):
        self.width, self.height = grid_size
        new_size = (self.width * self.cell, self.height * self.cell)
        self.screen = pygame.display.set_mode(new_size)
        self.screen.fill((255, 255, 255))
        pygame.display.flip()

    def draw_grid(self, grid):
        for x in range(self.width):
            for y in range(self.height):
                rect = pygame.Rect(x * self.cell, y * self.cell, self.cell, self.cell)
                pygame.draw.rect(self.screen, code_to_color[grid[x][y]], rect)
        pygame.display.flip()

    def draw_delta(self, data):
        print(bytes(data))
        for i in range(0, len(data), 3):
            x, y, c = data[i : i + 3]
            x -= BYTE_CODE_SHIFT
            y -= BYTE_CODE_SHIFT
            rect = pygame.Rect(x * self.cell, y * self.cell, self.cell, self.cell)
            pygame.draw.rect(self.screen, code_to_color[chr(c)], rect)
        pygame.display.flip()

    def get_dir(self):
        if len(self.que) == 0:
            return self.prev_dir
        self.prev_dir = self.que[0]
        self.que = self.que[1:]
        return self.prev_dir

    async def create(self):
        self.resize((10, 10))


class client:
    def __init__(self):
        self.network = network_client()
        self.display = game_client()

    def parse_grid(self, message):
        blocks = message.split("|")
        if blocks[0] == "STATE_INIT":
            width = int(blocks[1])
            height = int(blocks[2])
            grid = [p.split(",") for p in blocks[3].split(":")]
            self.display.resize((width, height))
            self.read_arrows = True
            self.display.draw_grid(grid)
        else:
            data = list(blocks[1].encode())
            self.display.draw_delta(data)

    async def space_await(self):
        self.space_pressed.clear()
        await self.space_pressed.wait()

    async def event_handler(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    exit(0)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.space_pressed.set()
                    if event.key in key_to_dir and self.read_arrows:
                        await self.network.write(key_to_dir[event.key])
            await asyncio.sleep(0.01)

    async def handler(self):
        while True:
            message = await self.network.read()
            if message == "TEST":
                await self.network.write("TEST_ANSWER")
            elif message == "SPACE_AWAIT":
                await self.space_await()
                await self.network.write("SPACE_PRESSED")
            elif message.startswith("STATE"):
                self.parse_grid(message)
            elif message == "END_GAME":
                self.read_arrows = False
            elif message == "PING":
                await self.network.write("PONG")
            if not message.startswith("STATE"):
                print(message)
            else:
                print(message.split("|")[0])

    async def create(self):
        await self.network.create()
        await self.display.create()
        self.read_arrows = False
        self.space_pressed = asyncio.Event()
        asyncio.create_task(self.event_handler())
        await self.handler()


async def main():
    a = client()
    await a.create()
    event = asyncio.Event()
    await event.wait()


asyncio.run(main())
