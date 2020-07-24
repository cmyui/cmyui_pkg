A general library of classes I find myself rewriting time and time again.

# Some use cases
1. Hosting a simple socket server (INET & UNIX).
```py
from socket import AF_INET, SOCK_STREAM
from cmyui import Server, Connection

serv: Server
conn: Connection

# for inet sockets, addr is a tuple of (host: str, port: int).
# for unix sockets, addr is simply a string of the file location.
serv_addr = ('127.0.0.1', 5001) # or '/tmp/myserv.sock'

with Server(socket.AF_INET, socket.SOCK_STREAM) as serv:
    for conn in serv.listen(serv_addr, max_conns = 5):
        ''' Use your conn object here! '''

        print(
            # HTTP command as a string ('GET', 'POST', etc.).
            conn.request.cmd,

            # HTTP version as a float.
            conn.request.httpver,

            # HTTP headers as {k: v} pairs.
            conn.request.headers,

            # HTTP body as bytes.
            conn.request.body,

            # Args parsed from the request as {k: v} pairs.
            # GET: parse args from URI
            # POST (w/ form data): parse args from multipart
            conn.request.args
        )

        conn.response.add_header('Content-Type: image/png')
        conn.response.send(b'abc', 200) # Attaches headers &
                                        # Content-Length before sending.
```

More documentation coming soon..
