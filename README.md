A general library of classes I find myself rewriting time and time again.

# Usage examples.
1. Hosting a simple socket server (inet or unix).
```py
from socket import AF_UNIX, SOCK_STREAM
import cmyui

if __name__ == '__main__':
    with Server(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        for conn in s.listen('/tmp/gulag.sock', 5):
            # Use your conn object here.

            print(conn.request.cmd, conn.request.httpver)
            #
            # Headers in {k: v} format, body in bytes.
            print(conn.request.headers, conn.request.body)

            # Args parsed from get/post request.
            # Format depends on request type
            # (see cmyui_pkg/connection.py)
            # for more information.
            print(conn.request.args)
```

More documentation coming soon..
