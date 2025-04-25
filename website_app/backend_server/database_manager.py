import getpass
import os
import logging
import certifi
from pymongo import MongoClient, errors

# ----------------------------------------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------------------------------------
DB_NAME = os.getenv("env_cosmosdb_database", "ota_update_db")
SHARED_RU = 400

# Collection names and their index specifications
# Index spec: either a field name string or a list of (field, direction) tuples
COLLECTION_CONFIGS = {
    "car_types": [
        "name",
        "model_number"
    ],
    "ecus": [
        [("name", 1), ("model_number", 1)]
    ],
    "versions": [
        [("version_number", 1), ("hex_file_path", 1)]
    ],
    "requests": [
        [("car_id", 1), ("timestamp", -1)]
    ],
    "download_requests": [
        [("car_id", 1), ("timestamp", -1)],
        "status"
    ]
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DatabaseManager")


class DatabaseManager:
    """
    Manages Azure Cosmos DB (MongoDB API) connection, database/collection
    setup (unsharded), index initialization, and clean shutdown.
    """

    def __init__(self, data_directory: str):
        logger.info(
            f"Initializing DatabaseManager, data directory: {data_directory}")
        self.data_directory = data_directory
        os.makedirs(data_directory, exist_ok=True)

        # Prompt for the Cosmos DB connection string
        conn_str = getpass.getpass(
            prompt='Enter your Cosmos DB (MongoDB API) connection string: ').strip()

        try:
            # Connect with TLS and certifi
            self.client = MongoClient(
                conn_str,
                tls=True,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=10000
                # If on server version >= 4.0, you can enforce Server API v1:
                # server_api=ServerApi("1")
            )
            # Verify connectivity
            self.client.admin.command("ping")
            logger.info("Connected to Cosmos DB!")
        except errors.ServerSelectionTimeoutError as exc:
            logger.error(f"Connection failed: {exc}")
            raise

        self.db = self.client[DB_NAME]
        self._setup_database_and_collections()

    def _setup_database_and_collections(self):
        """
        Create database (with shared RU) if missing, then create each collection
        and its indexes per COLLECTION_CONFIGS.
        """
        # Create database with shared throughput if it does not exist
        if DB_NAME not in self.client.list_database_names():
            self.db.command({
                "customAction": "CreateDatabase",
                "offerThroughput": SHARED_RU
            })
            logger.info(f"Created database '{DB_NAME}' with {SHARED_RU} RU/s")

        # Iterate collections
        for coll_name, indexes in COLLECTION_CONFIGS.items():
            # Create collection if missing (unsharded, using DB-level RU)
            if coll_name not in self.db.list_collection_names():
                self.db.command({
                    "customAction": "CreateCollection",
                    "collection": coll_name
                })
                logger.info(f"Created collection '{coll_name}'")

            coll = self.db[coll_name]

            # Build a set of existing index names
            existing_indexes = {idx['name'] for idx in coll.list_indexes()}

            # Create missing indexes
            for spec in indexes:
                if isinstance(spec, str):
                    keys = [(spec, 1)]
                    index_name = f"{spec}_1"
                else:
                    keys = spec
                    index_name = "_".join(
                        f"{field}_{direction}" for field, direction in spec)

                if index_name not in existing_indexes:
                    coll.create_index(keys)
                    logger.info(
                        f"Created index '{index_name}' on '{coll_name}'")

    def close(self):
        """Close the MongoDB client connection."""
        if hasattr(self, 'client') and self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
