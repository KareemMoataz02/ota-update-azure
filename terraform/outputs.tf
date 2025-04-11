output "website_app_default_hostname" {
  description = "Hostname for the Website App"
  value       = azurerm_linux_web_app.website_app.default_hostname
}

output "hmi_vm_public_ip" {
  description = "Public IP address of the HMI Virtual Machine"
  value       = azurerm_public_ip.hmi_public_ip.ip_address
}

output "sql_server_fqdn" {
  description = "The fully qualified domain name of the SQL Server."
  value       = azurerm_mssql_server.sql_server.fully_qualified_domain_name
}

output "sql_database_name" {
  description = "The name of the SQL Database."
  value       = var.sql_database_name
}

output "sql_admin_username" {
  description = "The SQL Server admin username."
  value       = var.sql_admin_username
}

output "sql_admin_password" {
  description = "The SQL Server admin password."
  value       = var.sql_admin_password
  sensitive   = true
}
