output "website_app_default_hostname" {
  description = "Hostname for the Website App"
  value       = azurerm_linux_web_app.website_app.default_hostname
}

output "hmi_vm_public_ip" {
  description = "Public IP address of the HMI Virtual Machine"
  value       = azurerm_public_ip.hmi_public_ip.ip_address
}

output "hex_storage_account_name" {
  description = "Name of the HEX storage account"
  value       = azurerm_storage_account.hex_storage.name
}

output "hex_storage_container_name" {
  description = "Name of the HEX storage container"
  value       = azurerm_storage_container.hex_container.name
}

output "hex_storage_account_key" {
  description = "Primary access key for the HEX storage account"
  value       = azurerm_storage_account.hex_storage.primary_access_key
  sensitive   = true
}
