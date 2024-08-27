import sys
import traceback
from io import StringIO

import rpyc

ORIGINAL_GLOBAL = dict(globals())


class MyService(rpyc.Service):
    def __init__(self):
        self.globals = dict(ORIGINAL_GLOBAL)

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        pass

    def exposed_execute(self, command):
        try:
            if command == "RESET_CONTAINER_SPECIAL_KEYWORD":
                self.globals = dict(ORIGINAL_GLOBAL)

            # Capture standard output and standard error to string buffers
            output_buffer = StringIO()
            error_buffer = StringIO()
            sys.stdout = output_buffer
            sys.stderr = error_buffer

            # Execute the command in a shared dictionary to maintain state
            exec(command, self.globals)

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
    from rpyc.utils.server import ThreadPoolServer

    server = ThreadPoolServer(MyService(), port=3006)
    server.start()
