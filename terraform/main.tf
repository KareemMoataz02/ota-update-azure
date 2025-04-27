terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.75.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 1.4"
    }
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "ota-terraform-rg"
    storage_account_name = "otatfstateacc"
    container_name       = "tfstate"
    key                  = "ota-update-azure.tfstate"
  }
}

provider "azurerm" {
  subscription_id = var.subscription_id
  features {}
}

provider "azapi" {}

provider "mongodbatlas" {
  public_key  = var.atlas_public_key
  private_key = var.atlas_private_key
}

# -------------------------------
# Resource Group
# -------------------------------
resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

# -------------------------------
# MongoDB Atlas: Project & Cluster
# -------------------------------
resource "mongodbatlas_project" "app" {
  name   = var.atlas_project_name
  org_id = var.atlas_org_id
}

resource "mongodbatlas_cluster" "app_cluster" {
  project_id                  = mongodbatlas_project.app.id
  name                        = var.atlas_cluster_name
  cluster_type                = "REPLICASET"
  provider_name               = "AZURE"
  provider_region_name        = var.location
  provider_instance_size_name = "M0"
}

resource "mongodbatlas_project_ip_access_list" "app_access" {
  project_id = mongodbatlas_project.app.id
  ip_address = var.app_vnet_cidr
  comment    = "Allow App Service / VNet"
}

resource "mongodbatlas_database_user" "app_user" {
  project_id         = mongodbatlas_project.app.id
  username           = var.mongo_user
  password           = var.mongo_password
  auth_database_name = "admin"

  roles {
    role_name     = "readWrite"
    database_name = var.mongodb_database_name
  }
}

data "mongodbatlas_cluster" "app_cluster" {
  project_id = mongodbatlas_project.app.id
  name       = mongodbatlas_cluster.app_cluster.name
}

# -------------------------------
# Locals
# -------------------------------
locals {
  mongo_srv = data.mongodbatlas_cluster.app_cluster.connection_strings[0].standard_srv
}

# -------------------------------
# Website Service Plan & Web App
# -------------------------------
resource "azurerm_service_plan" "website_plan" {
  name                = "ota-website-plan"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "B1"
}

resource "azurerm_linux_web_app" "website_app" {
  name                = var.website_app_name
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  service_plan_id     = azurerm_service_plan.website_plan.id
  https_only          = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = true
  }

  app_settings = {
    "MONGO_URI"      = local.mongo_srv
    "MONGO_USER"     = mongodbatlas_database_user.app_user.username
    "MONGO_PASSWORD" = mongodbatlas_database_user.app_user.password
    "MONGO_DB"       = var.mongodb_database_name

    "HEX_STORAGE_ACCOUNT_NAME"   = azurerm_storage_account.hex_storage.name
    "HEX_STORAGE_CONTAINER_NAME" = azurerm_storage_container.hex_container.name
    "HEX_STORAGE_ACCOUNT_KEY"    = azurerm_storage_account.hex_storage.primary_access_key

    "WEBSITES_PORT" = "80"
  }

  tags = {
    Environment = var.environment
    Project     = "OTA-Update"
  }
}

resource "azapi_update_resource" "compose_patch" {
  depends_on  = [azurerm_linux_web_app.website_app]
  resource_id = azurerm_linux_web_app.website_app.id
  type        = "Microsoft.Web/sites@2022-03-01"

  body = jsonencode({
    properties = {
      siteConfig = {
        linuxFxVersion = "COMPOSE|${base64encode(file("${path.module}/ota-compose.yml"))}"
      }
    }
  })
}

# -------------------------------
# HEX Files Storage
# -------------------------------
resource "azurerm_storage_account" "hex_storage" {
  name                     = var.hex_storage_account_name
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "hex_container" {
  name                  = "hexfiles"
  storage_account_id    = azurerm_storage_account.hex_storage.id
  container_access_type = "blob"
}

# -------------------------------
# HMI Networking & VM
# -------------------------------
resource "azurerm_virtual_network" "vnet" {
  name                = "ota-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_subnet" "subnet" {
  name                 = "ota-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_network_security_group" "hmi_nsg" {
  name                = "hmi-nsg"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name

  security_rule {
    name                       = "AllowSSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    destination_port_range     = "22"
  }

  security_rule {
    name                       = "AllowCustomPort9000"
    priority                   = 1002
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    destination_port_range     = "9000"
  }
}

resource "azurerm_public_ip" "hmi_public_ip" {
  name                = "hmi-public-ip"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
}

resource "azurerm_network_interface" "hmi_nic" {
  name                = "hmi-nic"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.hmi_public_ip.id
  }
}

resource "azurerm_network_interface_security_group_association" "hmi_nic_association" {
  network_interface_id      = azurerm_network_interface.hmi_nic.id
  network_security_group_id = azurerm_network_security_group.hmi_nsg.id
}

resource "azurerm_linux_virtual_machine" "hmi_vm" {
  name                            = var.hmi_vm_name
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = var.location
  size                            = "Standard_B1s"
  admin_username                  = var.hmi_vm_admin_username
  admin_password                  = var.hmi_vm_admin_password
  disable_password_authentication = false
  network_interface_ids           = [azurerm_network_interface.hmi_nic.id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "UbuntuServer"
    sku       = "18.04-LTS"
    version   = "latest"
  }

  custom_data = base64encode(templatefile("cloud-init-hmi.yaml", {
    mongodb_uri        = local.mongo_srv
    mongodb_user       = mongodbatlas_database_user.app_user.username
    mongodb_password   = mongodbatlas_database_user.app_user.password
    mongodb_database   = var.mongodb_database_name
    mongodb_collection = var.mongodb_collection_name

    hex_storage_account_name   = var.hex_storage_account_name
    hex_storage_container_name = azurerm_storage_container.hex_container.name
    hex_storage_account_key    = azurerm_storage_account.hex_storage.primary_access_key
  }))
}
