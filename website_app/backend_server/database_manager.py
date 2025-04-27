import os
import logging
import certifi
from pymongo import MongoClient, errors
from pymongo.server_api import ServerApi

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, data_directory: str):
        logger.info(
            f"Initializing DatabaseManager with data directory: {data_directory}")
        self.data_directory = data_directory
        os.makedirs(data_directory, exist_ok=True)

        # Read the full SRV URI and target database from environment
        srv_uri = os.environ.get("MONGO_URI")
        if not srv_uri:
            raise ValueError(
                "Environment variable MONGO_URI must be set to your Atlas connection string")

        dbname = os.environ.get("MONGO_DB", "otaMongoDb")

        try:
            # Connect to MongoDB Atlas
            self.client = MongoClient(
                srv_uri,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=10_000,
                retryWrites=False,
                server_api=ServerApi("1"),
            )
            # Verify the connection
            self.client.admin.command("ping")
            logger.info("Connected to MongoDB Atlas cluster")
        except errors.PyMongoError as e:
            logger.error(f"Failed to connect to MongoDB Atlas: {e}")
            raise

        # Select database
        self.db = self.client[dbname]

        # Collections
        self.car_types_collection = self.db['car_types']
        self.ecus_collection = self.db['ecus']
        self.versions_collection = self.db['versions']
        self.requests_collection = self.db['requests']
        self.download_requests_collection = self.db['download_requests']

        # Initialize collections with indexes
        self._initialize_db()

        # Factory methods for services (to be injected by DatabaseService)
        self.get_car_type_service = None
        self.get_ecu_service = None
        self.get_version_service = None
        self.get_request_service = None

    def _initialize_db(self):
        """Create indexes and ensure collections exist"""
        logger.info("Initializing database indexes")

        try:
            # Fix for duplicate key error: First, we'll clean up any duplicates in the versions collection
            self._clean_duplicates_in_versions()

            # Check and create indexes for car_types collection
            car_types_indexes = list(self.car_types_collection.list_indexes())
            car_types_index_names = [idx['name'] for idx in car_types_indexes]

            # Name index
            if 'name_1' not in car_types_index_names:
                logger.info("Creating index on car_types.name")
                self.car_types_collection.create_index(
                    "name")  # Removed unique constraint

            # Model number index
            if 'model_number_1' not in car_types_index_names:
                logger.info("Creating index on car_types.model_number")
                self.car_types_collection.create_index(
                    "model_number")  # Removed unique constraint

            # Check and create indexes for ecus collection
            ecus_indexes = list(self.ecus_collection.list_indexes())
            ecus_index_names = [idx['name'] for idx in ecus_indexes]

            if 'name_1_model_number_1' not in ecus_index_names:
                logger.info(
                    "Creating compound index on ecus.name and ecus.model_number")
                self.ecus_collection.create_index(
                    # Removed unique constraint
                    [("name", 1), ("model_number", 1)])

            # Check and create indexes for versions collection - with NO unique constraint
            versions_indexes = list(self.versions_collection.list_indexes())
            versions_index_names = [idx['name'] for idx in versions_indexes]

            if 'version_number_1_hex_file_path_1' not in versions_index_names:
                logger.info(
                    "Creating compound index on versions.version_number and versions.hex_file_path")
                self.versions_collection.create_index(
                    # No unique constraint
                    [("version_number", 1), ("hex_file_path", 1)])

            # Request indexes
            requests_indexes = list(self.requests_collection.list_indexes())
            requests_index_names = [idx['name'] for idx in requests_indexes]

            if 'car_id_1_timestamp_-1' not in requests_index_names:
                logger.info(
                    "Creating compound index on requests.car_id and requests.timestamp")
                self.requests_collection.create_index(
                    [("car_id", 1), ("timestamp", -1)])

            # Download request indexes
            download_requests_indexes = list(
                self.download_requests_collection.list_indexes())
            download_requests_index_names = [idx['name']
                                             for idx in download_requests_indexes]

            if 'car_id_1_timestamp_-1' not in download_requests_index_names:
                logger.info(
                    "Creating compound index on download_requests.car_id and download_requests.timestamp")
                self.download_requests_collection.create_index(
                    [("car_id", 1), ("timestamp", -1)])

            if 'status_1' not in download_requests_index_names:
                logger.info("Creating index on download_requests.status")
                self.download_requests_collection.create_index("status")

            logger.info("Database indexes initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database indexes: {str(e)}")
            # Continue even if indexes fail - they're for performance, not functionality

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
