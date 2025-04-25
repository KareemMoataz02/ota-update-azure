output "website_app_default_hostname" {
  description = "Hostname for the Website App"
  value       = azurerm_linux_web_app.website_app.default_hostname
}

output "hmi_vm_public_ip" {
  description = "Public IP address of the HMI Virtual Machine"
  value       = azurerm_public_ip.hmi_public_ip.ip_address
}

output "env_cosmosdb_uri" {
  description = "Environment variable assignment for Cosmos DB URI"
  value       = "COSMOSDB_URI=${azurerm_cosmosdb_account.mongodb.primary_mongodb_connection_string}"
  sensitive   = true
}

output "env_cosmosdb_database" {
  description = "Environment variable assignment for Cosmos DB database name"
  value       = "COSMOSDB_DATABASE=${var.mongodb_database_name}"
  sensitive   = true
}

output "env_cosmosdb_collection" {
  description = "Environment variable assignment for Cosmos DB collection name"
  value       = "COSMOSDB_COLLECTION=${var.mongodb_collection_name}"
  sensitive   = true
}

output "env_hex_storage_account_name" {
  description = "Environment variable assignment for HEX storage account name"
  value       = "HEX_STORAGE_ACCOUNT_NAME=${var.hex_storage_account_name}"
}

output "env_hex_storage_container_name" {
  description = "Environment variable assignment for HEX storage container name"
  value       = "HEX_STORAGE_CONTAINER_NAME=${azurerm_storage_container.hex_container.name}"
}

output "env_hex_storage_account_key" {
  description = "Environment variable assignment for HEX storage account key"
  value       = "HEX_STORAGE_ACCOUNT_KEY=${azurerm_storage_account.hex_storage.primary_access_key}"
  sensitive   = true
}
