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
  }
  backend "azurerm" {
    resource_group_name  = "ota-terraform-rg"
    storage_account_name = "otatfstateacc"
    container_name       = "tfstate"
    key                  = "ota-update-azure.tfstate"
  }
}

provider "azurerm" {
  subscription_id = "ec34342c-37de-48d7-a62d-6d8cbf370531"
  features {

  }
}

provider "azapi" {}

# ---------------------------------------------------------------
# Main Infrastructure Resources for OTA Update Azure Deployment
# ---------------------------------------------------------------

# -------------------------------
# Resource Group
# -------------------------------
resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

# ---------------------------------------------------------------
# Azure Cosmos DB for MongoDB (vCore) cluster
# ---------------------------------------------------------------
resource "azurerm_mongo_cluster" "mongodb_vcore" {
  name                = var.cosmosdb_account_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  # Admin credentials for the MongoDB cluster
  administrator_username = var.mongo_admin_username
  administrator_password = var.mongo_admin_password

  # How many shards (each shard is a replica set)
  shard_count            = "1"
  compute_tier           = "M10"
  high_availability_mode = "Disabled"
  storage_size_in_gb     = "32"
  version                = "6.0"
}


# -------------------------------
# Website Server (Linux Web App)
# -------------------------------
resource "azurerm_service_plan" "website_plan" {
  name                = "ota-website-plan"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "B1"
}

locals {
  compose_b64 = base64encode(file("${path.module}/ota-compose.yml"))
}

locals {
  mongo_srv = format(
    "mongodb+srv://%s:%s@%s.global.mongocluster.cosmos.azure.com:10260/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000",
    urlencode(var.mongo_admin_username),
    urlencode(var.mongo_admin_password),
    azurerm_mongo_cluster.mongodb_vcore.name,
  )
}


#############################################
# 1) Create the Web App (no compose here)   #
#############################################
resource "azurerm_linux_web_app" "website_app" {
  name                = var.website_app_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  service_plan_id     = azurerm_service_plan.website_plan.id
  https_only          = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = true
    # no linux_fx_version or container_settings here
  }

  app_settings = {
    "COSMOSDB_DATABASE"   = var.mongodb_database_name
    "COSMOSDB_COLLECTION" = var.mongodb_collection_name
    "COSMOSDB_URI"        = local.mongo_srv
    "COSMOSDB_USER"       = azurerm_mongo_cluster.mongodb_vcore.administrator_username
    "COSMOSDB_KEY"        = azurerm_mongo_cluster.mongodb_vcore.administrator_password

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

#############################################
# 2) Patch in your Docker-Compose string    #
#############################################

resource "azapi_update_resource" "compose_patch" {
  depends_on  = [azurerm_linux_web_app.website_app]
  resource_id = azurerm_linux_web_app.website_app.id
  type        = "Microsoft.Web/sites@2022-03-01"

  body = jsonencode({
    properties = {
      siteConfig = {
        linuxFxVersion = "COMPOSE|${local.compose_b64}"
      }
    }
  })
}




# -------------------------------
# HEX Files Storage (Dedicated Blob Storage)
# -------------------------------
resource "azurerm_storage_account" "hex_storage" {
  name                     = var.hex_storage_account_name
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "hex_container" {
  name                  = "hexfiles"
  storage_account_id    = azurerm_storage_account.hex_storage.id
  container_access_type = "blob"
}

# -------------------------------
# HMI Networking
# -------------------------------
resource "azurerm_virtual_network" "vnet" {
  name                = "ota-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.rg.location
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
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  security_rule {
    name                       = "AllowSSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    source_port_range          = "*"
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
    source_port_range          = "*"
    destination_port_range     = "9000"
  }
}

resource "azurerm_public_ip" "hmi_public_ip" {
  name                = "hmi-public-ip"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
}

resource "azurerm_network_interface" "hmi_nic" {
  name                = "hmi-nic"
  location            = azurerm_resource_group.rg.location
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

# -------------------------------
# HMI Server (Linux Virtual Machine)
# -------------------------------
resource "azurerm_linux_virtual_machine" "hmi_vm" {
  name                            = var.hmi_vm_name
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
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
    cosmosdb_database   = var.mongodb_database_name
    cosmosdb_collection = var.mongodb_collection_name
    cosmosdb_uri        = local.mongo_srv
    cosmosdb_user       = azurerm_mongo_cluster.mongodb_vcore.administrator_username
    cosmosdb_key        = azurerm_mongo_cluster.mongodb_vcore.administrator_password

    hex_storage_account_name   = var.hex_storage_account_name
    hex_storage_container_name = azurerm_storage_container.hex_container.name
    hex_storage_account_key    = azurerm_storage_account.hex_storage.primary_access_key
  }))
}
