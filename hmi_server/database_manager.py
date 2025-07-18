import os
from typing import Dict, List, Optional
from models import CarType, ECU, Version, FlashingFeedback, FlashingSession, FlashingMetrics, CarFlashingHistory
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson.binary import Binary
from azure.storage.blob import BlobServiceClient, BlobClient
from urllib.parse import urlparse
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

# Load environment variables from .env file
load_dotenv()

class DatabaseManager:
    def __init__(self, data_directory: str):
        """
        Initialize the DatabaseManager with MongoDB connection
        The data_directory parameter is kept for compatibility with existing code
        """
        self.data_directory = data_directory  # Keep for hex files storage
        
        # MongoDB connection from env variables
        uri = os.getenv("MONGO_URI")
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        self.db = self.client[os.getenv("MONGO_DB", 'automotive_firmware_db')]
        
        # Existing collections
        self.car_types_collection = self.db['car_types']
        self.ecus_collection = self.db['ecus']
        self.versions_collection = self.db['versions']
        self.requests_collection = self.db['requests']
        self.download_requests_collection = self.db['download_requests']
        
        # NEW: Flashing feedback collections
        self.flashing_feedback_collection = self.db['flashing_feedback']
        self.flashing_sessions_collection = self.db['flashing_sessions']
        self.flashing_metrics_collection = self.db['flashing_metrics']
        self.car_flashing_history_collection = self.db['car_flashing_history']
        
        # Azure Blob Storage configuration from env variables
        self.blob_account_name = os.getenv("HEX_STORAGE_ACCOUNT_NAME")
        self.blob_container_name = os.getenv("HEX_STORAGE_CONTAINER_NAME")
        self.blob_account_key = os.getenv("HEX_STORAGE_ACCOUNT_KEY")
        self.blob_connection_string = (f"DefaultEndpointsProtocol=https;AccountName={self.blob_account_name};"
                                     f"AccountKey={self.blob_account_key};EndpointSuffix=core.windows.net")
        self.blob_service_client = BlobServiceClient.from_connection_string(self.blob_connection_string)
        self.container_client = self.blob_service_client.get_container_client(self.blob_container_name)
        
        # Initialize collections if needed
        self._initialize_db()
    
    def _initialize_db(self):
        """Create indexes and ensure collections exist"""
        # Existing indexes
        self.car_types_collection.create_index("name")
        self.car_types_collection.create_index("model_number")
        self.ecus_collection.create_index("name")
        self.versions_collection.create_index([("version_number", 1), ("ecu_id", 1)])
        self.requests_collection.create_index("car_id")
        self.download_requests_collection.create_index("car_id")
        
        # NEW: Flashing feedback indexes
        self.flashing_feedback_collection.create_index("car_id")
        self.flashing_feedback_collection.create_index("session_id")
        self.flashing_feedback_collection.create_index("flashing_timestamp")
        self.flashing_feedback_collection.create_index([("car_type", 1), ("overall_status", 1)])
        
        self.flashing_sessions_collection.create_index("session_id")
        self.flashing_sessions_collection.create_index("car_id")
        self.flashing_sessions_collection.create_index("start_time")
        
        self.flashing_metrics_collection.create_index([("car_type", 1), ("ecu_name", 1), ("version", 1)])
        self.flashing_metrics_collection.create_index("last_updated")
        
        self.car_flashing_history_collection.create_index("car_id")
        self.car_flashing_history_collection.create_index("car_type")

    # ... (keep all existing methods unchanged) ...
    
    def _get_blob_name_from_url(self, blob_url: str) -> str:
        """Extract blob name from blob URL"""
        # Parse the URL to get the path
        parsed_url = urlparse(blob_url)
        # The path will be in format: /containername/blobname
        path_parts = parsed_url.path.split('/')
        # The blob name is after the container name (index 2 and beyond)
        # Join all parts after the container name to handle blobs with '/' in the name
        blob_name = '/'.join(path_parts[2:])
        return blob_name

    def get_hex_file_chunk(self, file_path: str, chunk_size: int, offset: int) -> Optional[bytes]:
        """
        Read a chunk of hex file from Azure Blob Storage or local file system
        """
        try:
            # Check if it's a blob URL or local file path
            if file_path.startswith("https://") and "blob.core.windows.net" in file_path:
                # It's a blob URL, extract blob name
                blob_name = self._get_blob_name_from_url(file_path)
                
                # Get blob client
                blob_client = self.container_client.get_blob_client(blob_name)
                
                # Download the range of bytes from the blob
                download_stream = blob_client.download_blob(offset=offset, length=chunk_size)
                
                # Read the bytes
                chunk_data = download_stream.readall()
                return chunk_data
            else:
                # Fallback to local file system for backward compatibility
                with open(file_path, 'rb') as f:
                    f.seek(offset)
                    return f.read(chunk_size)
        except Exception as e:
            print(f"Error reading hex file: {str(e)}")
            return None

    def get_file_size(self, file_path: str) -> int:
        """
        Get size of a hex file from Azure Blob Storage or local file system
        """
        try:
            # Check if it's a blob URL or local file path
            if file_path.startswith("https://") and "blob.core.windows.net" in file_path:
                # It's a blob URL, extract blob name
                blob_name = self._get_blob_name_from_url(file_path)
                
                # Get blob client
                blob_client = self.container_client.get_blob_client(blob_name)
                
                # Get blob properties to get size
                blob_properties = blob_client.get_blob_properties()
                return blob_properties.size
            else:
                # Fallback to local file system for backward compatibility
                return os.path.getsize(file_path)
        except Exception as e:
            print(f"Error getting file size: {str(e)}")
            return 0
    
    def load_all_data(self) -> List[CarType]:
        """Load all data from MongoDB and create CarType objects"""
        try:
            # Get all car types from MongoDB
            car_types_data = list(self.car_types_collection.find({}))
            
            car_types = []
            for car_type_info in car_types_data:
                # Get ECUs for this car type
                ecu_ids = car_type_info.get('ecu_ids', [])
                ecus = []
                
                for ecu_id in ecu_ids:
                    ecu_info = self.ecus_collection.find_one({"_id": ecu_id})
                    
                    if ecu_info:
                        # Get versions for this ECU
                        version_ids = ecu_info.get('version_ids', [])
                        versions = []
                        
                        for version_id in version_ids:
                            version_info = self.versions_collection.find_one({"_id": version_id})
                            
                            if version_info:
                                versions.append(Version(
                                    version_number=version_info['version_number'],
                                    compatible_car_types=version_info['compatible_car_types'],
                                    hex_file_path=version_info['hex_file_path']
                                ))
                        
                        ecus.append(ECU(
                            name=ecu_info['name'],
                            model_number=ecu_info['model_number'],
                            versions=versions
                        ))
                
                car_types.append(CarType(
                    name=car_type_info['name'],
                    model_number=car_type_info['model_number'],
                    ecus=ecus,
                    manufactured_count=car_type_info.get('manufactured_count', 0),
                    car_ids=car_type_info.get('car_ids', [])
                ))

            print(f"car_types: {car_types}")
            return car_types
        
        except Exception as e:
            print(f"Error loading database from MongoDB: {str(e)}")
            return []

    # ... (keep all existing save/load methods) ...

    # NEW: Flashing feedback methods
    def save_flashing_feedback(self, feedback: FlashingFeedback) -> bool:
        """Save flashing feedback from a car"""
        try:
            # Validate car exists
            if not self.validate_car_exists(feedback.car_id, feedback.car_type):
                logging.error(f"Car {feedback.car_id} of type {feedback.car_type} not found in database")
                return False
            
            feedback_data = {
                "session_id": feedback.session_id,
                "car_id": feedback.car_id,
                "car_type": feedback.car_type,
                "flashing_timestamp": feedback.flashing_timestamp,
                "overall_status": feedback.overall_status,
                "total_ecus": feedback.total_ecus,
                "successful_ecus": feedback.successful_ecus,
                "rolled_back_ecus": feedback.rolled_back_ecus,
                "final_ecu_versions": feedback.final_ecu_versions,
                "android_app_version": feedback.android_app_version,
                "beaglebone_version": feedback.beaglebone_version,
                "request_id": feedback.request_id,
                "received_timestamp": feedback.received_timestamp
            }
            
            # Insert feedback
            result = self.flashing_feedback_collection.insert_one(feedback_data)
            
            if result.inserted_id:
                logging.info(f"✅ Flashing feedback saved for car {feedback.car_id} (session: {feedback.session_id})")
                
                # Update car's current ECU versions
                self.update_car_current_versions(feedback.car_id, feedback.final_ecu_versions)
                
                # Update metrics
                self.update_flashing_metrics(feedback)
                
                # Update car flashing history
                self.update_car_flashing_history(feedback)
                
                return True
            else:
                logging.error(f"Failed to save flashing feedback for car {feedback.car_id}")
                return False
                
        except Exception as e:
            logging.error(f"Error saving flashing feedback: {str(e)}")
            return False
    
    def validate_car_exists(self, car_id: str, car_type: str) -> bool:
        """Validate that a car exists in the database"""
        try:
            car_type_doc = self.car_types_collection.find_one({"name": car_type})
            if not car_type_doc:
                return False
            
            car_ids = [cid.lower() for cid in car_type_doc.get('car_ids', [])]
            return car_id.lower() in car_ids
            
        except Exception as e:
            logging.error(f"Error validating car existence: {str(e)}")
            return False
    
    def update_car_current_versions(self, car_id: str, ecu_versions: Dict[str, str]):
        """Update the current ECU versions for a car"""
        try:
            # This could be stored in a separate collection or as part of car data
            # For now, we'll update the car_flashing_history collection
            self.car_flashing_history_collection.update_one(
                {"car_id": car_id},
                {
                    "$set": {
                        "current_ecu_versions": ecu_versions,
                        "last_updated": datetime.now()
                    }
                },
                upsert=True
            )
            logging.info(f"Updated current ECU versions for car {car_id}")
            
        except Exception as e:
            logging.error(f"Error updating car current versions: {str(e)}")
    
    def update_flashing_metrics(self, feedback: FlashingFeedback):
        """Update overall flashing metrics based on feedback"""
        try:
            for ecu_name in feedback.successful_ecus:
                final_version = feedback.final_ecu_versions.get(ecu_name, "unknown")
                self._update_ecu_metrics(feedback.car_type, ecu_name, final_version, "success")
            
            for ecu_name in feedback.rolled_back_ecus:
                final_version = feedback.final_ecu_versions.get(ecu_name, "unknown")
                self._update_ecu_metrics(feedback.car_type, ecu_name, final_version, "rollback")
            
            # Update failed ECUs (total - successful - rolled back)
            all_processed_ecus = set(feedback.successful_ecus + feedback.rolled_back_ecus)
            failed_count = feedback.total_ecus - len(all_processed_ecus)
            if failed_count > 0:
                # We don't have individual failed ECU names, so we'll track this at car type level
                self._update_general_metrics(feedback.car_type, failed_count, "failed")
                
        except Exception as e:
            logging.error(f"Error updating flashing metrics: {str(e)}")
    
    def _update_ecu_metrics(self, car_type: str, ecu_name: str, version: str, result_type: str):
        """Update metrics for a specific ECU"""
        try:
            # Find existing metrics document
            existing_metrics = self.flashing_metrics_collection.find_one({
                "car_type": car_type,
                "ecu_name": ecu_name,
                "version": version
            })
            
            if existing_metrics:
                # Update existing metrics
                total_attempts = existing_metrics.get("total_attempts", 0) + 1
                successful_attempts = existing_metrics.get("successful_attempts", 0)
                failed_attempts = existing_metrics.get("failed_attempts", 0)
                rollback_attempts = existing_metrics.get("rollback_attempts", 0)
                
                if result_type == "success":
                    successful_attempts += 1
                elif result_type == "rollback":
                    rollback_attempts += 1
                else:  # failed
                    failed_attempts += 1
                
                success_rate = (successful_attempts / total_attempts) * 100 if total_attempts > 0 else 0
                
                self.flashing_metrics_collection.update_one(
                    {"_id": existing_metrics["_id"]},
                    {
                        "$set": {
                            "total_attempts": total_attempts,
                            "successful_attempts": successful_attempts,
                            "failed_attempts": failed_attempts,
                            "rollback_attempts": rollback_attempts,
                            "success_rate": success_rate,
                            "last_updated": datetime.now()
                        }
                    }
                )
            else:
                # Create new metrics document
                total_attempts = 1
                successful_attempts = 1 if result_type == "success" else 0
                failed_attempts = 1 if result_type == "failed" else 0
                rollback_attempts = 1 if result_type == "rollback" else 0
                success_rate = (successful_attempts / total_attempts) * 100
                
                metrics_data = {
                    "car_type": car_type,
                    "ecu_name": ecu_name,
                    "version": version,
                    "total_attempts": total_attempts,
                    "successful_attempts": successful_attempts,
                    "failed_attempts": failed_attempts,
                    "rollback_attempts": rollback_attempts,
                    "success_rate": success_rate,
                    "last_updated": datetime.now()
                }
                
                self.flashing_metrics_collection.insert_one(metrics_data)
                
        except Exception as e:
            logging.error(f"Error updating ECU metrics: {str(e)}")
    
    def _update_general_metrics(self, car_type: str, count: int, result_type: str):
        """Update general metrics for car type"""
        # This is a simplified approach - you might want more detailed tracking
        pass
    
    def update_car_flashing_history(self, feedback: FlashingFeedback):
        """Update the flashing history for a car"""
        try:
            existing_history = self.car_flashing_history_collection.find_one({"car_id": feedback.car_id})
            
            if existing_history:
                # Update existing history
                total_sessions = existing_history.get("total_flashing_sessions", 0) + 1
                successful_sessions = existing_history.get("successful_sessions", 0)
                partial_success_sessions = existing_history.get("partial_success_sessions", 0)
                failed_sessions = existing_history.get("failed_sessions", 0)
                
                if feedback.overall_status == "completed":
                    successful_sessions += 1
                elif feedback.overall_status == "partial_failure":
                    partial_success_sessions += 1
                else:
                    failed_sessions += 1
                
                flashing_sessions = existing_history.get("flashing_sessions", [])
                flashing_sessions.append(feedback.session_id)
                
                self.car_flashing_history_collection.update_one(
                    {"car_id": feedback.car_id},
                    {
                        "$set": {
                            "total_flashing_sessions": total_sessions,
                            "successful_sessions": successful_sessions,
                            "partial_success_sessions": partial_success_sessions,
                            "failed_sessions": failed_sessions,
                            "last_flashing_date": feedback.flashing_timestamp,
                            "current_ecu_versions": feedback.final_ecu_versions,
                            "flashing_sessions": flashing_sessions
                        }
                    }
                )
            else:
                # Create new history
                successful_sessions = 1 if feedback.overall_status == "completed" else 0
                partial_success_sessions = 1 if feedback.overall_status == "partial_failure" else 0
                failed_sessions = 1 if feedback.overall_status not in ["completed", "partial_failure"] else 0
                
                history_data = {
                    "car_id": feedback.car_id,
                    "car_type": feedback.car_type,
                    "total_flashing_sessions": 1,
                    "successful_sessions": successful_sessions,
                    "partial_success_sessions": partial_success_sessions,
                    "failed_sessions": failed_sessions,
                    "last_flashing_date": feedback.flashing_timestamp,
                    "current_ecu_versions": feedback.final_ecu_versions,
                    "flashing_sessions": [feedback.session_id]
                }
                
                self.car_flashing_history_collection.insert_one(history_data)
                
        except Exception as e:
            logging.error(f"Error updating car flashing history: {str(e)}")
    
    def get_flashing_metrics_summary(self, car_type: str = None, days: int = 30) -> Dict:
        """Get flashing metrics summary"""
        try:
            # Build query
            query = {}
            if car_type:
                query["car_type"] = car_type
            
            # Time filter
            since_date = datetime.now() - timedelta(days=days)
            query["received_timestamp"] = {"$gte": since_date}
            
            # Aggregate metrics
            pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": "$overall_status",
                        "count": {"$sum": 1},
                        "car_types": {"$addToSet": "$car_type"}
                    }
                }
            ]
            
            results = list(self.flashing_feedback_collection.aggregate(pipeline))
            
            summary = {
                "period_days": days,
                "car_type_filter": car_type,
                "total_sessions": sum(r["count"] for r in results),
                "status_breakdown": {r["_id"]: r["count"] for r in results},
                "car_types_involved": list(set().union(*[r["car_types"] for r in results]) if results else [])
            }
            
            return summary
            
        except Exception as e:
            logging.error(f"Error getting flashing metrics summary: {str(e)}")
            return {}
    
    def get_car_flashing_history(self, car_id: str) -> Optional[Dict]:
        """Get flashing history for a specific car"""
        try:
            history = self.car_flashing_history_collection.find_one({"car_id": car_id})
            if history:
                # Remove MongoDB ObjectId for JSON serialization
                history.pop('_id', None)
            return history
            
        except Exception as e:
            logging.error(f"Error getting car flashing history: {str(e)}")
            return None
    
    def get_recent_flashing_activities(self, limit: int = 50) -> List[Dict]:
        """Get recent flashing activities across all cars"""
        try:
            activities = list(self.flashing_feedback_collection.find(
                {},
                {
                    "_id": 0,
                    "session_id": 1,
                    "car_id": 1,
                    "car_type": 1,
                    "flashing_timestamp": 1,
                    "overall_status": 1,
                    "total_ecus": 1,
                    "successful_ecus": 1,
                    "rolled_back_ecus": 1,
                    "received_timestamp": 1
                }
            ).sort("received_timestamp", -1).limit(limit))
            
            return activities
            
        except Exception as e:
            logging.error(f"Error getting recent flashing activities: {str(e)}")
            return []
    
    def get_ecu_success_rates(self, car_type: str = None) -> List[Dict]:
        """Get success rates for different ECUs and versions"""
        try:
            query = {}
            if car_type:
                query["car_type"] = car_type
            
            pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": {
                            "car_type": "$car_type",
                            "ecu_name": "$ecu_name",
                            "version": "$version"
                        },
                        "total_attempts": {"$sum": "$total_attempts"},
                        "successful_attempts": {"$sum": "$successful_attempts"},
                        "failed_attempts": {"$sum": "$failed_attempts"},
                        "rollback_attempts": {"$sum": "$rollback_attempts"},
                        "avg_success_rate": {"$avg": "$success_rate"},
                        "last_updated": {"$max": "$last_updated"}
                    }
                },
                {
                    "$project": {
                        "car_type": "$_id.car_type",
                        "ecu_name": "$_id.ecu_name",
                        "version": "$_id.version",
                        "total_attempts": 1,
                        "successful_attempts": 1,
                        "failed_attempts": 1,
                        "rollback_attempts": 1,
                        "success_rate": "$avg_success_rate",
                        "last_updated": 1,
                        "_id": 0
                    }
                },
                {"$sort": {"success_rate": -1}}
            ]
            
            results = list(self.flashing_metrics_collection.aggregate(pipeline))
            return results
            
        except Exception as e:
            logging.error(f"Error getting ECU success rates: {str(e)}")
            return []

    # Keep all existing methods unchanged
    def save_car_type(self, car_type: CarType):
        """Save a car type to the database"""
        try:
            # First save/update ECUs and get their IDs
            ecu_ids = []
            for ecu in car_type.ecus:
                # Save versions first and get their IDs
                version_ids = []
                for version in ecu.versions:
                    version_data = {
                        "version_number": version.version_number,
                        "compatible_car_types": version.compatible_car_types,
                        "hex_file_path": version.hex_file_path
                    }
                    
                    # Check if version exists, update or insert
                    result = self.versions_collection.update_one(
                        {"version_number": version.version_number, "hex_file_path": version.hex_file_path},
                        {"$set": version_data},
                        upsert=True
                    )
                    
                    # Get the ID of the inserted/updated version
                    if result.upserted_id:
                        version_id = result.upserted_id
                    else:
                        version_doc = self.versions_collection.find_one(
                            {"version_number": version.version_number, "hex_file_path": version.hex_file_path}
                        )
                        version_id = version_doc["_id"]
                    
                    version_ids.append(version_id)
                
                # Now save the ECU with version IDs
                ecu_data = {
                    "name": ecu.name,
                    "model_number": ecu.model_number,
                    "version_ids": version_ids
                }
                
                # Check if ECU exists, update or insert
                result = self.ecus_collection.update_one(
                    {"name": ecu.name, "model_number": ecu.model_number},
                    {"$set": ecu_data},
                    upsert=True
                )
                
                # Get the ID of the inserted/updated ECU
                if result.upserted_id:
                    ecu_id = result.upserted_id
                else:
                    ecu_doc = self.ecus_collection.find_one(
                        {"name": ecu.name, "model_number": ecu.model_number}
                    )
                    ecu_id = ecu_doc["_id"]
                
                ecu_ids.append(ecu_id)
            
            # Finally save the car type with ECU IDs
            car_type_data = {
                "name": car_type.name,
                "model_number": car_type.model_number,
                "ecu_ids": ecu_ids,
                "manufactured_count": car_type.manufactured_count,
                "car_ids": car_type.car_ids
            }
            
            # Update or insert car type
            self.car_types_collection.update_one(
                {"name": car_type.name, "model_number": car_type.model_number},
                {"$set": car_type_data},
                upsert=True
            )
            
        except Exception as e:
            print(f"Error saving car type to MongoDB: {str(e)}")
    
    def save_request(self, request):
        """Save a service request to the database"""
        try:
            request_data = {
                "timestamp": request.timestamp,
                "car_type": request.car_type,
                "car_id": request.car_id,
                "ip_address": request.ip_address,
                "port": request.port,
                "service_type": request.service_type.value,
                "metadata": request.metadata,
                "status": request.status.value
            }
            
            self.requests_collection.insert_one(request_data)
        except Exception as e:
            print(f"Error saving request to MongoDB: {str(e)}")
    
    def save_download_request(self, download_request):
        """Save a download request to the database"""
        try:
            request_data = {
                "timestamp": download_request.timestamp,
                "car_type": download_request.car_type,
                "car_id": download_request.car_id,
                "ip_address": download_request.ip_address,
                "port": download_request.port,
                "required_versions": download_request.required_versions,
                "old_versions": download_request.old_versions,
                "status": download_request.status.value,
                "total_size": download_request.total_size,
                "transferred_size": download_request.transferred_size,
                "active_transfers": download_request.active_transfers
            }
            
            self.download_requests_collection.insert_one(request_data)
        except Exception as e:
            print(f"Error saving download request to MongoDB: {str(e)}")
    
    def update_download_request_status(self, car_id: str, status, transferred_size=None):
        """Update the status of a download request"""
        try:
            update_data = {"status": status.value}
            if transferred_size is not None:
                update_data["transferred_size"] = transferred_size
                
            self.download_requests_collection.update_one(
                {"car_id": car_id, "status": {"$ne": "COMPLETED"}},
                {"$set": update_data}
            )
        except Exception as e:
            print(f"Error updating download request status in MongoDB: {str(e)}")

    def get_car_type_by_name(self, name: str) -> Optional[CarType]:
        """Get a car type by name"""
        try:
            car_type_info = self.car_types_collection.find_one({"name": name})
            if not car_type_info:
                return None
                
            # Load full car type using the same logic as load_all_data
            ecus = []
            for ecu_id in car_type_info.get('ecu_ids', []):
                ecu_info = self.ecus_collection.find_one({"_id": ecu_id})
                if ecu_info:
                    versions = []
                    for version_id in ecu_info.get('version_ids', []):
                        version_info = self.versions_collection.find_one({"_id": version_id})
                        if version_info:
                            versions.append(Version(
                                version_number=version_info['version_number'],
                                compatible_car_types=version_info['compatible_car_types'],
                                hex_file_path=version_info['hex_file_path']
                            ))
                    
                    ecus.append(ECU(
                        name=ecu_info['name'],
                        model_number=ecu_info['model_number'],
                        versions=versions
                    ))
            
            return CarType(
                name=car_type_info['name'],
                model_number=car_type_info['model_number'],
                ecus=ecus,
                manufactured_count=car_type_info.get('manufactured_count', 0),
                car_ids=car_type_info.get('car_ids', [])
            )
        except Exception as e:
            print(f"Error getting car type by name from MongoDB: {str(e)}")
            return None