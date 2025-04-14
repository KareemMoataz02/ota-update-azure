#############################
# Variables
#############################
variable "resource_group_name" {
  description = "The name of the Resource Group"
  type        = string
  default     = "ota-update-rg"
}

variable "location" {
  description = "Azure region for deployment (allowed: uaenorth)"
  type        = string
  default     = "uaenorth"
}

variable "website_app_name" {
  description = "The name of the Web App for the upload website"
  type        = string
  default     = "ota-website-app"
}


variable "cosmosdb_account_name" {
  description = "The name of the Azure Cosmos DB account that uses the MongoDB API."
  type        = string
}

variable "mongodb_database_name" {
  description = "The MongoDB database name within the Cosmos DB account."
  type        = string
  default     = "otaMongoDb"
}

variable "mongodb_collection_name" {
  description = "The name of the MongoDB collection to store your data."
  type        = string
  default     = "otaCollection"
}


variable "hmi_vm_name" {
  description = "The name of the Virtual Machine hosting the HMI server"
  type        = string
  default     = "hmi-socket-vm"
}

variable "hmi_vm_admin_username" {
  description = "Admin username for HMI VM"
  type        = string
  default     = "azureuser"
}

variable "hmi_vm_admin_password" {
  description = "Admin password for HMI VM (use secure method in production)"
  type        = string
  default     = "P@ssword1234!"
}

variable "website_zip_path" {
  description = "Local path to the website app ZIP package"
  type        = string
  default     = "../website_app/website_app.zip"
}

variable "hex_storage_account_name" {
  description = "The name of the Storage Account for HEX files"
  type        = string
  default     = "otahexstorage"
}

variable "website_code_container_name" {
  description = "The container name for storing website code"
  type        = string
  default     = "website-code"
}

variable "tfstate_storage_account_name" {
  description = "The globally unique name for the storage account to store Terraform state."
  type        = string
  default     = "otatfstateacc"
}

variable "environment" {
  description = "The deployment environment (e.g., dev, staging, prod)."
  type        = string
  default     = "dev"
}
