import tools

log = tools.logger(__name__)

import asyncio

from enum import Enum, auto

class Type(Enum):
    SetActivity = auto()
    KeyPress = auto()
    KeyRelease = auto()

class Message(object):
    def __init__(self, type, val):
        self.type = type
        self.val = val

# A trivial object for connecting the Hub and UI indirectly with duck typing.
class Pipe(object):
    def __init__(self):
        self.server_q = asyncio.Queue()
        self.client_q = asyncio.Queue()
        self.server_t = None
        self.client_t = None
        self.background_tasks = set()

    def taskit(self, coro):
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    # Server calls
    def notify_set_activity(self, index):
        self.taskit(self.client_q.put(Message(Type.SetActivity, index)))

    def check_task(self, task):
        e = task.exception()
        if e is not None:
            log.info(f'Task exception {e}')
            raise e

    def start_server_task(self, handler):
        self.server_t = asyncio.create_task(self.server_task(handler))
        self.server_t.add_done_callback(self.check_task)

    # Server handler
    async def server_task(self, handler):
        while True:
            try:
                msg = await self.server_q.get()
                match msg.type:
                    case Type.SetActivity:
                        handler.client_set_activity(msg.val)
                    case Type.KeyPress:
                        handler.client_press_key(msg.val)
                    case Type.KeyRelease:
                        handler.client_release_key(msg.val)
            except Exception as e:
                log.info(f'server_task exception {e}')

    # Client calls
    def set_activity(self, index):
        self.taskit(self.server_q.put(Message(Type.SetActivity, index)))

    def key_press(self, key):
        self.taskit(self.server_q.put(Message(Type.KeyPress, key)))

    def key_release(self, key):
        self.taskit(self.server_q.put(Message(Type.KeyRelease, key)))

    # Client handler
    def start_client_task(self, handler):
        self.client_t = asyncio.create_task(self.client_task(handler))
        self.client_t.add_done_callback(self.check_task)

    async def client_task(self, handler):
        while True:
            msg = await self.client_q.get()
            match msg.type:
                case Type.SetActivity:
                    handler.server_notify_set_activity(msg.val)

