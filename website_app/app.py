from flask import Flask, request
import os
import pyodbc
from azure.storage.blob import BlobServiceClient

app = Flask(__name__)

# Retrieve SQL connection settings from environment variables
SQL_SERVER = os.environ.get('SQL_SERVER')
SQL_DATABASE = os.environ.get('SQL_DATABASE')
SQL_USER = os.environ.get('SQL_USER')
SQL_PASSWORD = os.environ.get('SQL_PASSWORD')
connection_string = f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USER};PWD={SQL_PASSWORD}'

# Retrieve Blob Storage settings from environment variables
BLOB_ACCOUNT_NAME = os.environ.get('HEX_STORAGE_ACCOUNT_NAME')
BLOB_CONTAINER_NAME = os.environ.get('HEX_STORAGE_CONTAINER_NAME')
BLOB_ACCOUNT_KEY = os.environ.get('HEX_STORAGE_ACCOUNT_KEY')
blob_connection_string = (
    f"DefaultEndpointsProtocol=https;AccountName={BLOB_ACCOUNT_NAME};"
    f"AccountKey={BLOB_ACCOUNT_KEY};EndpointSuffix=core.windows.net"
)

blob_service_client = BlobServiceClient.from_connection_string(
    blob_connection_string)
container_client = blob_service_client.get_container_client(
    BLOB_CONTAINER_NAME)


def get_uploads():
    """Query the HexUpdates table and return all records."""
    rows = []
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        # Now file_path stores the blob URL
        cursor.execute(
            "IF OBJECT_ID('HexUpdates', 'U') IS NOT NULL SELECT id, filename, file_path, car_model FROM HexUpdates"
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error querying uploads:", e)
    return rows


@app.route("/")
def index():
    rows = get_uploads()

    table_html = "<h2>Uploaded Files</h2>"
    if rows:
        table_html += """
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Filename</th>
              <th>File URL</th>
              <th>Car Model</th>
            </tr>
          </thead>
          <tbody>
        """
        for row in rows:
            table_html += (
                f"<tr><td>{row[0]}</td><td>{row[1]}</td>"
                f"<td><a href='{row[2]}' target='_blank'>View File</a></td>"
                f"<td>{row[3] or ''}</td></tr>"
            )
        table_html += """
          </tbody>
        </table>
        """
    else:
        table_html += "<p>No uploads found.</p>"

    html = f"""<!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Upload Car HEX Update</title>
      <style>
        body {{
          font-family: Arial, sans-serif;
          background-color: #f2f2f2;
          margin: 0;
          padding: 20px;
        }}
        h1, h2 {{
          color: #333;
        }}
        form {{
          background-color: #fff;
          padding: 20px;
          border-radius: 5px;
          box-shadow: 0 0 10px rgba(0,0,0,0.1);
          max-width: 500px;
          margin-bottom: 30px;
        }}
        input[type="file"],
        input[type="text"] {{
          width: 100%;
          padding: 10px;
          margin: 5px 0 10px 0;
          border: 1px solid #ccc;
          border-radius: 4px;
        }}
        input[type="submit"] {{
          background-color: green;
          color: white;
          padding: 10px 15px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }}
        input[type="submit"]:hover {{
          background-color: #45a049;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin-top: 20px;
          background-color: #fff;
        }}
        table, th, td {{
          border: 1px solid #ddd;
        }}
        th, td {{
          padding: 8px;
          text-align: left;
        }}
        th {{
          background-color: #f2f2f2;
        }}
      </style>
    </head>
    <body>
      <h1>Upload Car HEX Update</h1>
      <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="hex_file" /><br/><br/>
        <input type="text" name="car_model" placeholder="Car Model" /><br/><br/>
        <input type="submit" value="Upload" />
      </form>
      {table_html}
    </body>
    </html>
    """
    return html


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("hex_file")
    car_model = request.form.get("car_model")
    if not file:
        return "No file uploaded", 400

    filename = file.filename

    try:
        # Upload file to Azure Blob Storage
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(file, overwrite=True)
        # Construct the blob file URL
        file_url = f"https://{BLOB_ACCOUNT_NAME}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{filename}"

        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        # Create the HexUpdates table if it does not exist, including the car_model column
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='HexUpdates' and xtype='U')
            CREATE TABLE HexUpdates (
                id INT IDENTITY(1,1) PRIMARY KEY,
                filename NVARCHAR(255),
                file_path NVARCHAR(500),
                car_model NVARCHAR(255)
            )
        """)
        conn.commit()

        cursor.execute(
            "INSERT INTO HexUpdates (filename, file_path, car_model) VALUES (?, ?, ?)",
            (filename, file_url, car_model)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return f"Error saving file: {e}", 500

    return f"File {filename} uploaded successfully! File URL: {file_url}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
