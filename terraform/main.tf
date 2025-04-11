terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  # Remote backend configuration for persistent state.
  backend "azurerm" {
    resource_group_name  = "ota-terraform-rg"         # Pre-created resource group for state
    storage_account_name = "otatfstateacc"            # Pre-created storage account for state (must be lowercase and globally unique)
    container_name       = "tfstate"                  # Pre-created container in that storage account
    key                  = "ota-update-azure.tfstate" # Name for the state file
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
# Relational Database (Azure SQL)
# -------------------------------
resource "azurerm_mssql_server" "sql_server" {
  name                         = var.sql_server_name
  resource_group_name          = azurerm_resource_group.rg.name
  location                     = azurerm_resource_group.rg.location
  version                      = "12.0"
  administrator_login          = var.sql_admin_username
  administrator_login_password = var.sql_admin_password
}

resource "azurerm_mssql_database" "sql_db" {
  name                 = var.sql_database_name
  server_id            = azurerm_mssql_server.sql_server.id
  max_size_gb          = 2
  sku_name             = "Basic"
  zone_redundant       = false
  storage_account_type = "Local"
}

resource "azurerm_mssql_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.sql_server.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
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
    "SQL_SERVER"                 = azurerm_mssql_server.sql_server.fully_qualified_domain_name
    "SQL_DATABASE"               = var.sql_database_name
    "SQL_USER"                   = var.sql_admin_username
    "SQL_PASSWORD"               = var.sql_admin_password
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
    sql_server_fqdn    = azurerm_mssql_server.sql_server.fully_qualified_domain_name
    sql_database_name  = var.sql_database_name
    sql_admin_username = var.sql_admin_username
    sql_admin_password = var.sql_admin_password
  }))
}
