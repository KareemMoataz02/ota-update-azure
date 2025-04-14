output "website_app_default_hostname" {
  description = "Hostname for the Website App"
  value       = azurerm_linux_web_app.website_app.default_hostname
}

output "hmi_vm_public_ip" {
  description = "Public IP address of the HMI Virtual Machine"
  value       = azurerm_public_ip.hmi_public_ip.ip_address
}


