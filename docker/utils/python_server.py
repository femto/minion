import argparse
import re
import sys
import threading
import traceback
from io import StringIO
import json

import rpyc
from rpyc import ThreadPoolServer

ORIGINAL_GLOBAL = dict(globals())
vars = dict()
lock = threading.Lock()


class InheritedGlobals(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            return globals()[key]


class MyService(rpyc.Service):
    def __init__(self):
        self.globals = InheritedGlobals(ORIGINAL_GLOBAL)

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        pass

    def extract_id_and_command(self, full_command):
        match = re.match(r"<id>(.+?)</id>(.*)", full_command, re.DOTALL)
        if match:
            full_id = match.group(1)
            command = match.group(2).strip()
            return full_id, command
        else:
            return "DEFAULT_GLOBAL", full_command

    def get_namespace(self, full_id):
        id_parts = full_id.split("/")
        with lock:
            current_namespace = vars
            for part in id_parts:
                if part not in current_namespace:
                    current_namespace[part] = InheritedGlobals()
                current_namespace = current_namespace[part]
        return current_namespace

    def exposed_execute(self, command):
        try:
            full_id, command = self.extract_id_and_command(command)
            namespace = self.get_namespace(full_id)

            command_info = json.loads(command)  # Assuming the command is a JSON string

            if command_info.get('operation') == "RESET_CONTAINER_SPECIAL_KEYWORD":
                namespace.clear()
                namespace.update(ORIGINAL_GLOBAL)

            # Process the command based on its nature provided in JSON
            # Here additional functionality based on parsed JSON structure should be implemented
            # This is a place-holder for actual safe logic processing
            output = f"Executed safe operation: {command_info}"
            error = ""

            return {"output": output, "error": error}

        except json.JSONDecodeError:
            return {"error": "Invalid command format, expecting JSON."}
        except Exception as e:
            stack_trace = traceback.format_exc()
            return {"error": f"Error: {str(e)}\nStack trace:\n{stack_trace}"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the RPyC server.")
    parser.add_argument("--port", type=int, default=3006, help="Port number to run the server on (default: 3006)")
    args = parser.parse_args()
    server = ThreadPoolServer(MyService(), port=args.port)
    server.start()
