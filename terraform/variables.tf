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

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
  default     = "ec34342c-37de-48d7-a62d-6d8cbf370531"
}

variable "environment" {
  description = "The deployment environment (e.g., dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "website_app_name" {
  description = "The name of the Web App for the upload website"
  type        = string
  default     = "ota-website-app"
}

variable "hex_storage_account_name" {
  description = "The name of the Storage Account for HEX files"
  type        = string
  default     = "otahexstorage"
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

variable "mongodb_database_name" {
  description = "The MongoDB database name within Atlas"
  type        = string
  default     = "otaMongoDb"
}

variable "mongodb_collection_name" {
  description = "The name of the MongoDB collection to store your data."
  type        = string
  default     = "otaCollection"
}

#############################
# MongoDB Atlas Variables
#############################
variable "atlas_org_id" {
  description = "The MongoDB Atlas organization ID"
  type        = string
  default     = "680deb38edf9f57a1dcff86f"
}

variable "atlas_project_name" {
  description = "The MongoDB Atlas project name"
  type        = string
  default     = "ota-terraform"
}

variable "atlas_cluster_name" {
  description = "The MongoDB Atlas cluster name"
  type        = string
  default     = "ota-azure-cluster"
}

variable "atlas_public_key" {
  description = "MongoDB Atlas API public key"
  type        = string
  default     = "vktecnqd"
}

variable "atlas_private_key" {
  description = "MongoDB Atlas API private key"
  type        = string
  default     = "cee9772e-938a-4a1e-ab50-8dc938cbae91"
}

variable "mongo_user" {
  description = "MongoDB Atlas database user name"
  type        = string
  default     = "20p4361"
}

variable "mongo_password" {
  description = "MongoDB Atlas database user password"
  type        = string
  default     = "2q0E66zKfJ659Wys"
}

variable "app_vnet_cidr" {
  description = "CIDR block of the Azure VNet/subnet to allow access to Atlas"
  type        = string
  default     = "10.0.1.0/24"
}

