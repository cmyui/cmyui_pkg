A general library of classes I find myself rewriting time and time again.

# Some use cases
1. Hosting a simple socket server (INET & UNIX).
```py
from cmyui.web import *

serv: TCPServer
conn: Connection

# for inet sockets, addr is a tuple of (host: str, port: int).
# for unix sockets, addr is simply a string of the file location.
serv_addr = ('127.0.0.1', 5001) # or '/tmp/myserv.sock'

with TCPServer(serv_addr) as serv:
    for conn in serv.listen(max_conns = 5):
        ''' Use your conn object here! '''

        print(
            # HTTP command as a string ('GET', 'POST', etc.).
            conn.req.cmd,

            # HTTP version as a float.
            conn.req.httpver,

            # HTTP headers as {k: v} pairs.
            conn.req.headers,

            # HTTP body as bytes.
            conn.req.body,

            # Args parsed from the request as {k: v} pairs.
            # GET: parse args from URI
            # POST (w/ form data): parse args from multipart
            conn.req.args,

            # Files included in the request as {k: v} pairs
            conn.req.files
        )

        conn.resp.add_header('Content-Type: image/png')
        conn.resp.send(b'abc', 200) # Attaches headers &
                                    # Content-Length before sending.
```

More documentation coming soon..
