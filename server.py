import configparser
import asyncio
import random
import socket
import ctypes
import uuid

SERVER_ID = f"snake_game_server-{uuid.uuid4().hex[:8]}"
TCP_PORT = 8888
UDP_PORT = 9999
DISCOVERY_REQUEST = b"DISCOVER_SNAKE_GAME"
DISCOVERY_RESPONSE_PREFIX = b"SNAKE_GAME_HERE"
CONFIG_PATH = "config.ini"
BYTE_CODE_SHIFT = 100


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


async def udp_responder():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", UDP_PORT))

    local_ip = get_local_ip()
    loop = asyncio.get_event_loop()
    print(f"Server {SERVER_ID} is waiting for UPD-requests on port {UDP_PORT}")

    while True:
        try:
            data, addr = await loop.sock_recvfrom(sock, 1024)
            print(f"UDP get {data} from {addr}")
            if data == DISCOVERY_REQUEST:
                response = f"{DISCOVERY_RESPONSE_PREFIX.decode()}|{SERVER_ID}|{local_ip}".encode()
                await loop.sock_sendto(sock, response, addr)
                # print(f"UDP server sent answer to {addr}")
        except Exception as e:
            print(f"Error in UDP: {e}")


def load_config(path="config.ini"):
    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    return {
        "game": {
            "width": config.getint("game", "width"),
            "height": config.getint("game", "height"),
            "players_number": config.getint("game", "players_number"),
            "turn_time": config.getfloat("game", "turn_time"),
            "apples_number": config.getint("game", "apples_number"),
        }
    }


async def open_notepad(file):
    proc = await asyncio.create_subprocess_exec(
        "notepad.exe",
        "config.ini",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


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


dir_to_ds = {
    "L": point(-1, 0),
    "R": point(1, 0),
    "D": point(0, 1),
    "U": point(0, -1),
}


def collinear_dir(dir1, dir2):
    a = {"U", "D"}
    b = {"L", "R"}
    if dir1 in a and dir2 in a:
        return True
    if dir1 in b and dir2 in b:
        return True
    return False


snake_num_to_col = ["cC", "dD"]


class game:
    def build_start_pos(self):
        if self.players_number == 1:
            y = self.height // 2
            self.snakes = [[point(0, y), point(1, y), point(2, y)]]
            self.prev_dir = ["R"]
        elif self.players_number == 2:
            x = self.width - 1
            y = self.height - 2
            self.snakes = [
                [point(0, 1), point(1, 1), point(2, 1)],
                [point(x, y), point(x - 1, y), point(x - 2, y)],
            ]
            self.prev_dir = ["R", "L"]
        self.que = [[] for i in range(self.players_number)]
        self.end_game = False
        self.apples = []
        self.gen_apples()

    def gen_apples(self):
        while len(self.apples) < self.apples_number:
            p = self.get_free_cell()
            if p:
                self.apples.append(p)
            else:
                break
        if len(self.apples) == 0:
            self.end_game = True

    def get_free_cell(self):
        free = []
        for x in range(self.width):
            for y in range(self.height):
                p = point(x, y)
                if not self.is_under_snake(p) and p not in self.apples:
                    free.append(p)
        if len(free) == 0:
            return None
        else:
            return random.choice(free)

    def construc_grid(self):
        grid = [["."] * self.height for _ in range(self.width)]
        for apple in self.apples:
            grid[apple.x][apple.y] = "A"
        for num in range(len(self.snakes)):
            for segm in self.snakes[num]:
                is_head = 0
                if segm == self.snakes[num][-1]:
                    is_head = 1
                grid[segm.x][segm.y] = snake_num_to_col[num][is_head]
        return grid

    def is_under_snake(self, p):
        for snake in self.snakes:
            if p in snake:
                return True
        return False

    def make_turn(self):
        for num in range(len(self.snakes)):
            dir = self.prev_dir[num]
            if len(self.que[num]) > 0:
                dir = self.que[num][0]
                self.que[num] = self.que[num][1:]
            self.prev_dir[num] = dir
            new_head = self.snakes[num][-1] + dir_to_ds[dir]
            if not new_head.in_bound(self.width, self.height):
                self.end_game = True
                return
            if new_head not in self.apples:
                self.snakes[num] = self.snakes[num][1:]
            self.snakes[num].append(new_head)
        for num in range(len(self.snakes)):
            head = self.snakes[num][-1]
            if head in self.apples:
                self.apples.remove(head)
            self.snakes[num] = self.snakes[num][:-1]
            if self.is_under_snake(head):
                self.end_game = True
            else:
                self.snakes[num].append(head)
        self.gen_apples()

    def get_string(self):
        grid = self.construc_grid()
        self.prev_grid = grid
        grid_code = ""
        for l in grid:
            f = ""
            for m in l:
                f = f + m + ","
            grid_code += f[:-1] + ":"
        message = f"{self.width}|{self.height}|{grid_code[:-1]}"
        return message

    def get_delta(self):
        grid = self.construc_grid()
        res = b""
        for x in range(self.width):
            for y in range(self.height):
                if grid[x][y] != self.prev_grid[x][y]:
                    res += bytes([x + BYTE_CODE_SHIFT, y + BYTE_CODE_SHIFT])
                    res += grid[x][y].encode()
        self.prev_grid = grid
        return res.decode()

    def apply_direct(self, num, ndir):
        pdir = self.prev_dir[num]
        if len(self.que[num]) > 0:
            pdir = self.que[num][-1]
        if not collinear_dir(pdir, ndir) and len(self.que[num]) < 3:
            self.que[num].append(ndir)

    async def update_settings(self):
        while True:
            try:
                game_config = load_config()["game"]
                self.players_number = game_config["players_number"]
                if not (self.players_number in {1, 2}):
                    raise ValueError("number of players must be 1 or 2")
                self.width = game_config["width"]
                if not (self.width >= 4):
                    raise ValueError("width must be at least 4")
                self.height = game_config["height"]
                if not (self.height >= 4):
                    raise ValueError("height must be at least 4")
                self.turn_time = game_config["turn_time"]
                self.apples_number = game_config["apples_number"]
                self.build_start_pos()
                return
            except Exception as e:
                print(f"error: {e}")
                await open_notepad(CONFIG_PATH)


async def read(client):
    data = await client["reader"].readline()
    message = data.decode().strip()
    if message == "":
        raise Exception("client closed connection")
    if "num" in client:
        print(f"{message} is readed from {client["num"]}")
    else:
        print(f"{message} is readed")
    return message


async def write(client, message, timeout=1.0):
    if not isinstance(message, str):
        raise Exception(f"{message} isn't a string")
    if not message:
        raise Exception(f"message mustn't be clear")

    fmes = message
    if message.startswith("STATE"):
        fmes = message.split("|")[0]
    if "num" in client:
        print(f"{fmes} is writed to {client["num"]} (length = {len(message)})")
    else:
        print(f"{fmes} is writed (length = {len(message)})")
    client["writer"].write(message.strip().encode() + b"\n")
    await asyncio.wait_for(client["writer"].drain(), timeout=timeout)


async def check_ping(client):
    time_start = asyncio.get_event_loop().time()
    await write(client, "PING")
    mes = await read(client)
    return asyncio.get_event_loop().time() - time_start


class server:
    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        if self.state == "wait_clients" and not self.wait_clients_event.is_set():
            client = {
                "reader": reader,
                "writer": writer,
            }
            self.clients.append(client)
            await write(client, "ok")
            if len(self.clients) == self.game.players_number:
                self.wait_clients_event.set()
        else:
            writer.write(b"Game already started\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()

    async def check_clients(self):
        alive_clients = []
        for client in self.clients:
            try:
                await write(client, "TEST")
                answer = await asyncio.wait_for(read(client), timeout=1.0)
                if answer == "TEST_ANSWER":
                    alive_clients.append(client)
            except:
                pass
        self.clients = alive_clients

    async def write_all(self, message, timeout=1.0):
        for client in self.clients:
            await write(client, message, timeout=timeout)

    async def read_all(self):
        try:
            answer = [""] * len(self.clients)
            for client in self.clients:
                answer[client["num"]] = await read(client)
            return answer
        except Exception as e:
            print(f"error: {e}")
            self.state = "wait_clients"
            return [""] * len(self.clients)

    async def send_state(self, prefix):
        if prefix == "STATE_INIT":
            message = f"{prefix}|{self.game.get_string()}"
        else:
            message = f"{prefix}|{self.game.get_delta()}"
        await self.write_all(message)

    async def dir_reader(self, client):
        while not self.dirr_shutdown.is_set():
            read_task = asyncio.create_task(read(client))
            shutdown_task = asyncio.create_task(self.dirr_shutdown.wait())
            done, pending = await asyncio.wait(
                [read_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            if shutdown_task in done:
                break
            if read_task in done:
                input = await read_task
                self.game.apply_direct(client["num"], input)

    async def stop_readers(self):
        await asyncio.sleep(0.1)
        self.dirr_shutdown.set()
        await asyncio.sleep(0.1)

    async def wait_clients(self):
        try:
            await self.write_all("END_GAME")
        except:
            pass
        await self.stop_readers()
        await self.check_clients()
        if len(self.clients) > self.game.players_number:
            self.clients = self.clients[: self.game.players_number]
        self.wait_clients_event.clear()
        if len(self.clients) == self.game.players_number:
            self.wait_clients_event.set()
        await self.wait_clients_event.wait()
        for i in range(len(self.clients)):
            self.clients[i]["num"] = i
        self.state = "wait_restart"

    async def wait_restart(self):
        await self.stop_readers()
        await self.write_all("SPACE_AWAIT")
        ans = await self.read_all()
        for client in self.clients:
            print(f"PING from {client["num"]} = {(await check_ping(client)):.4f}")
            if ans[client["num"]] != "SPACE_PRESSED":
                self.state = "wait_clients"
        self.state = "game_start"

    async def game_start(self):
        await self.game.update_settings()
        self.game.build_start_pos()
        await self.send_state("STATE_INIT")
        self.state = "game_cycle"
        self.dirr_shutdown.clear()
        for client in self.clients:
            asyncio.create_task(self.dir_reader(client))

    async def game_cycle(self):
        self.turn = 0
        while self.state == "game_cycle":
            turn_start = asyncio.get_event_loop().time()

            self.game.make_turn()
            if self.game.end_game == True:
                await self.write_all("END_GAME")
                self.state = "wait_restart"
                return
            await self.send_state("STATE")

            elapsed = asyncio.get_event_loop().time() - turn_start
            sleep_time = self.game.turn_time - elapsed
            if sleep_time < 0:
                print(f"Turn {self.turn} lag: {-sleep_time:.3f}s")
            else:
                await asyncio.sleep(sleep_time)
            self.turn += 1

    async def run(self):
        while True:
            print(self.state)
            try:
                method = getattr(self, self.state)
                await method()
            except Exception as e:
                print(f"error: {e}")
                self.state = "wait_clients"
                await asyncio.sleep(1)

    async def start(self):
        self.clients = {}
        self.state = "wait_clients"
        self.turn_time = 0.3
        self.game = game()
        self.dir_task = []
        self.dirr_shutdown = asyncio.Event()
        await self.game.update_settings()
        self.game.build_start_pos()
        self.wait_clients_event = asyncio.Event()
        asyncio.create_task(udp_responder())
        self.server = await asyncio.start_server(
            self.handler, host="0.0.0.0", port=8888
        )
        async with self.server:
            for sock in self.server.sockets:
                print(f"tcp server started at {sock.getsockname()}")
            await self.run()


async def main():
    s = server()
    await s.start()


asyncio.run(main())
