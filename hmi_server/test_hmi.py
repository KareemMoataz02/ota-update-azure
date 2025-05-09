import socket

HOST = "74.243.248.164"
PORT = 9000

with socket.create_connection((HOST, PORT), timeout=5) as s:
    s.sendall(b"demo1.hex\n")
    data = s.recv(65536)
    print("Got %d bytes:" % len(data))
    print(data.decode(errors="ignore"))
