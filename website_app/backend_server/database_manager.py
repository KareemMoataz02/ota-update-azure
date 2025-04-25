# database_manager.py

import os
import logging
import certifi
from typing import List, Dict, Optional
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger("DatabaseManager")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)


class DatabaseManager:
    def __init__(self, data_directory: str):
        # --- filesystem prep & logging
        logger.info(
            f"Initializing DatabaseManager with data directory: {data_directory}")
        self.data_directory = data_directory
        os.makedirs(data_directory, exist_ok=True)

        # --- MongoDB/Cosmos setup
        self._init_mongo()

        # --- Blob Storage setup
        self._init_blob()

        # --- index creation, duplicate cleanup
        self._initialize_db()

    def _init_mongo(self):
        uri = os.environ["COSMOSDB_URI"]
        db_nm = os.environ.get("COSMOSDB_DATABASE", "")
        # explicitly use the Server API version 1
        self.client = MongoClient(uri, server_api=ServerApi("1"),
                                  tlsCAFile=certifi.where(),
                                  serverSelectionTimeoutMS=30000)
        try:
            self.client.admin.command("ping")
            logger.info("Connected to CosmosDB via SRV + ServerApi('1')!")
        except Exception as e:
            logger.error(f"Mongo ping failed: {e}")
            raise
        self.db = self.client[db_nm]
        self.collection_name = os.environ.get(
            "COSMOSDB_COLLECTION", "HexUpdates")
        self.coll = self.db[self.collection_name]

    def _init_blob(self):
        acct = os.environ["HEX_STORAGE_ACCOUNT_NAME"]
        key = os.environ["HEX_STORAGE_ACCOUNT_KEY"]
        cont = os.environ["HEX_STORAGE_CONTAINER_NAME"]
        conn_str = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={acct};AccountKey={key};"
            f"EndpointSuffix=core.windows.net"
        )
        self.blob_svc = BlobServiceClient.from_connection_string(conn_str)
        self.container_client = self.blob_svc.get_container_client(cont)
        logger.info("BlobServiceClient initialized.")

    def _initialize_db(self):
        """(Your existing index setup + duplicate cleanup)"""
        logger.info("Initializing indexes and deduplication.")
        # ... copy over your entire _initialize_db() and _clean_duplicates_in_versions() here ...

    # ————————————————————————————————
    # New methods to match your Flask logic
    # ————————————————————————————————

    def list_hex_updates(self) -> List[Dict]:
        """Get all patch docs."""
        try:
            return list(self.coll.find())
        except Exception as e:
            logger.error(f"Error listing updates: {e}")
            return []

    def upload_hex_update(
        self,
        file_stream,
        filename: str,
        car_model: str,
        patch_name: str,
        patch_version: str
    ) -> Optional[str]:
        """
        1. Uploads the file to Blob Storage
        2. Inserts a Mongo document with the same fields + file_url
        Returns the URL or None on error.
        """
        try:
            # upload blob
            blob = self.container_client.get_blob_client(filename)
            blob.upload_blob(file_stream, overwrite=True)
            file_url = (
                f"https://{self.container_client.account_name}"
                f".blob.core.windows.net/{self.container_client.container_name}/{filename}"
            )

            # insert doc
            doc = {
                "filename": filename,
                "file_url": file_url,
                "car_model": car_model,
                "patch_name": patch_name,
                "patch_version": patch_version
            }
            self.coll.insert_one(doc)
            logger.info(f"Inserted document for {filename}")
            return file_url

        except Exception as e:
            logger.error(f"Error in upload_hex_update: {e}")
            return None

    def _clean_duplicates_in_versions(self):
        """Clean up duplicate entries in versions collection"""
        try:
            # Check for duplicates
            pipeline = [
                {"$group": {
                    "_id": {"version_number": "$version_number", "hex_file_path": "$hex_file_path"},
                    "count": {"$sum": 1},
                    "ids": {"$push": "$_id"}
                }},
                {"$match": {"count": {"$gt": 1}}}
            ]

            duplicates = list(self.versions_collection.aggregate(pipeline))

            if duplicates:
                logger.info(
                    f"Found {len(duplicates)} groups of duplicate versions. Cleaning up...")

                for dup in duplicates:
                    # Keep the first document, remove others
                    ids_to_remove = dup['ids'][1:]
                    self.versions_collection.delete_many(
                        {"_id": {"$in": ids_to_remove}})

                logger.info("Duplicate versions cleanup completed")
        except Exception as e:
            logger.error(f"Error cleaning up duplicate versions: {str(e)}")

    def get_hex_file_chunk(self, file_path: str, chunk_size: int, offset: int) -> Optional[bytes]:
        """
        Read a chunk of hex file - using file system for binary files
        In the future, this could be migrated to MongoDB GridFS for binary storage
        """
        try:
            # Verify that the path is in the data directory for security
            if not os.path.abspath(file_path).startswith(os.path.abspath(self.data_directory)):
                # Attempt to find it relative to the data directory
                relative_path = os.path.join(
                    self.data_directory, os.path.basename(file_path))
                if os.path.exists(relative_path):
                    file_path = relative_path
                else:
                    logger.error(
                        f"Security warning: Attempted to access file outside data directory: {file_path}")
                    return None

            # Ensure file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None

            with open(file_path, 'rb') as f:
                f.seek(offset)
                chunk = f.read(chunk_size)
                logger.debug(
                    f"Read {len(chunk)} bytes from {file_path} at offset {offset}")
                return chunk
        except Exception as e:
            logger.error(f"Error reading hex file {file_path}: {str(e)}")
            return None

    def get_file_size(self, file_path: str) -> int:
        """
        Get size of a hex file - using file system
        In the future, this could be migrated to MongoDB GridFS for binary storage
        """
        try:
            # Verify that the path is in the data directory for security
            if not os.path.abspath(file_path).startswith(os.path.abspath(self.data_directory)):
                # Attempt to find it relative to the data directory
                relative_path = os.path.join(
                    self.data_directory, os.path.basename(file_path))
                if os.path.exists(relative_path):
                    file_path = relative_path
                else:
                    logger.error(
                        f"Security warning: Attempted to access file outside data directory: {file_path}")
                    return 0

            # Ensure file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return 0

            size = os.path.getsize(file_path)
            logger.debug(f"File size for {file_path}: {size} bytes")
            return size
        except Exception as e:
            logger.error(f"Error getting file size for {file_path}: {str(e)}")
            return 0

    def save_file(self, file_data: bytes, file_name: str) -> Optional[str]:
        """
        Save a binary file to the data directory
        Returns the file path if successful, None otherwise
        """
        try:
            # Ensure only filenames are used, not paths (security)
            safe_filename = os.path.basename(file_name)
            file_path = os.path.join(self.data_directory, safe_filename)

            with open(file_path, 'wb') as f:
                f.write(file_data)

            logger.info(f"File saved successfully: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving file {file_name}: {str(e)}")
            return None

    def close(self):
        """Close the MongoDB connection"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
                logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {str(e)}")
