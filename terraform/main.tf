terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
  # Remote backend configuration for persistent state.
  backend "azurerm" {
    resource_group_name  = "ota-terraform-rg"
    storage_account_name = "otatfstateacc"
    container_name       = "tfstate"
    key                  = "ota-update-azure.tfstate"
  }
}

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

# -------------------------------
# NoSQL Database (Azure Cosmos DB with MongoDB API, optimized for least cost)
# -------------------------------
resource "azurerm_cosmosdb_account" "mongodb" {
  name                = var.cosmosdb_account_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  offer_type          = "Standard"
  kind                = "MongoDB"
  free_tier_enabled   = true

  capabilities {
    name = "EnableMongo"
  }

  capabilities {
    name = "EnableServerless"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  # Use a single region to minimize cost
  geo_location {
    location          = var.location
    failover_priority = 0
    zone_redundant    = false
  }

  automatic_failover_enabled    = false
  public_network_access_enabled = true
}

resource "azurerm_cosmosdb_mongo_database" "mongodb_database" {
  name                = var.mongodb_database_name
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.mongodb.name
}

resource "azurerm_cosmosdb_mongo_collection" "mongodb_collection" {
  name                = var.mongodb_collection_name
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.mongodb.name
  database_name       = azurerm_cosmosdb_mongo_database.mongodb_database.name
  throughput          = 400
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

resource "azurerm_linux_web_app" "website_app" {
  name                = var.website_app_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  service_plan_id     = azurerm_service_plan.website_plan.id
  https_only          = true

  site_config {
    always_on = false

    application_stack {
      docker_image_name   = "kareemmoataz13/ota-website-app:latest"
      docker_registry_url = "https://index.docker.io"
    }
  }

  app_settings = {
    # Connection settings for the new Cosmos DB (MongoDB API) service
    "COSMOSDB_URI"        = azurerm_cosmosdb_account.mongodb.endpoint
    "COSMOSDB_KEY"        = azurerm_cosmosdb_account.mongodb.primary_key
    "COSMOSDB_DATABASE"   = var.mongodb_database_name
    "COSMOSDB_COLLECTION" = var.mongodb_collection_name

    # Retaining existing blob storage settings
    "HEX_STORAGE_ACCOUNT_NAME"   = azurerm_storage_account.hex_storage.name
    "HEX_STORAGE_CONTAINER_NAME" = azurerm_storage_container.hex_container.name
    "HEX_STORAGE_ACCOUNT_KEY"    = azurerm_storage_account.hex_storage.primary_access_key
  }
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
  storage_account_name  = azurerm_storage_account.hex_storage.name
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
    cosmosdb_endpoint   = azurerm_cosmosdb_account.mongodb.endpoint
    cosmosdb_key        = azurerm_cosmosdb_account.mongodb.primary_key
    cosmosdb_database   = var.mongodb_database_name
    cosmosdb_collection = var.mongodb_collection_name
  }))
}
