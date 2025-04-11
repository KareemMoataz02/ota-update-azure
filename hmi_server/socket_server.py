import socket
import threading
import pyodbc
import os
import requests

# Database connection settings from environment variables
SQL_SERVER = os.environ.get('SQL_SERVER')
SQL_DATABASE = os.environ.get('SQL_DATABASE')
SQL_USER = os.environ.get('SQL_USER')
SQL_PASSWORD = os.environ.get('SQL_PASSWORD')
connection_string = f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USER};PWD={SQL_PASSWORD}'

HOST = '0.0.0.0'
PORT = 9000


def handle_client(conn, addr):
    print(f"Connected by {addr}")
    try:
        # Expecting the client to send the filename of the requested HEX update.
        data = conn.recv(1024).decode().strip()
        if not data:
            return
        print(f"Received request for file: {data}")
        try:
            conn_db = pyodbc.connect(connection_string)
            cursor = conn_db.cursor()
            cursor.execute(
                "SELECT file_path FROM HexUpdates WHERE filename = ?", (data,))
            row = cursor.fetchone()
            cursor.close()
            conn_db.close()
            if row:
                file_url = row[0]
                # Fetch the file content from blob storage using its URL
                response = requests.get(file_url)
                if response.status_code == 200:
                    hex_data = response.text
                    conn.sendall(hex_data.encode())
                else:
                    conn.sendall(
                        f"Error retrieving file: HTTP {response.status_code}".encode())
            else:
                conn.sendall(f"File {data} not found.".encode())
        except Exception as e:
            conn.sendall(f"Database error: {e}".encode())
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"HMI Socket Server listening on {HOST}:{PORT}")
        while True:
            client_conn, client_addr = s.accept()
            threading.Thread(target=handle_client, args=(
                client_conn, client_addr)).start()


if __name__ == "__main__":
    start_server()
