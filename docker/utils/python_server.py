import argparse
import re
import sys
import threading
import traceback
from io import StringIO

import rpyc

# from rpyc.utils.server import ThreadPoolServer
from rpyc import ThreadPoolServer

ORIGINAL_GLOBAL = dict(globals())
vars = dict()
lock = threading.Lock()


class MyService(rpyc.Service):
    def __init__(self):
        self.globals = dict(ORIGINAL_GLOBAL)

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        pass

    def extract_id_and_command(self, full_command):
        # Extract the ID using regex
        match = re.match(r"<id>(.+?)</id>(.*)", full_command, re.DOTALL)
        if match:
            full_id = match.group(1)
            command = match.group(2).strip()
            return full_id, command
        else:
            return "DEFAULT_GLOBAL", full_command

    def get_namespace(self, full_id):
        # Split the ID by "/" to handle hierarchy
        id_parts = full_id.split("/")

        # Use the lock to ensure thread safety when accessing `vars`
        parent = vars
        with lock:
            current_namespace = vars
            for part in id_parts:
                if part not in current_namespace:
                    current_namespace[part] = {}
                parent = current_namespace
                current_namespace = current_namespace[part]

        return current_namespace, parent, id_parts[-1]

    def exposed_execute(self, command):
        try:
            full_id, command = self.extract_id_and_command(command)

            # Get the specific namespace for this ID
            namespace, parent, id_part = self.get_namespace(full_id)

            if command == "RESET_CONTAINER_SPECIAL_KEYWORD":
                self.globals = dict(ORIGINAL_GLOBAL)
                del parent[id_part]

            # Capture standard output and standard error to string buffers
            output_buffer = StringIO()
            error_buffer = StringIO()
            sys.stdout = output_buffer
            sys.stderr = error_buffer

            # Execute the command in the specified namespace
            with lock:
                exec(command, self.globals, namespace)

            # Restore the standard output and standard error and get the captured output
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            output = output_buffer.getvalue().strip()
            error = error_buffer.getvalue().strip()

            return {"output": output, "error": error}
        except Exception as e:
            stack_trace = traceback.format_exc()
            # Return the stack trace in the error response
            return {"error": f"Error: {str(e)}\nStack trace:\n{stack_trace}"}


if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Run the RPyC server.")
    parser.add_argument("--port", type=int, default=3006, help="Port number to run the server on (default: 3006)")

    # Parse the arguments
    args = parser.parse_args()

    # Use the parsed port or the default port
    server = ThreadPoolServer(MyService(), port=args.port)
    server.start()
