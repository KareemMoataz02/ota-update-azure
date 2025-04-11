Below is a completely rewritten README.md for your repository:

---

# OTA Update Azure Deployment

This repository provides a complete solution for deploying an OTA update system on Azure using Terraform Infrastructure as Code (IaC). It provisions two types of Azure resources and includes code stubs for both:

1. **Website Server:**  
   An Azure Web App running a Flask application. This web server allows your company to upload new HEX file updates for vehicles. It also saves update metadata to an Azure SQL Database. The web app is automatically deployed using the "WEBSITE_RUN_FROM_PACKAGE" mechanism. In this process, your website’s code is packaged as a ZIP file, uploaded to an Azure Storage container, and deployed via a generated SAS URL.

2. **HMI Server:**  
   A Linux Virtual Machine that runs a Python socket server. The HMI server listens for update requests on a specified socket port, queries the Azure SQL Database for the corresponding HEX file update, and sends the update file back to the requester.

---

## Directory Structure

The repository is organized as follows:

```
ota-update-azure/
├── terraform/
│   ├── cloud-init-hmi.yaml     # Cloud-init script to configure and launch the HMI server VM
│   ├── provider.tf             # Azure provider configuration for Terraform
│   ├── variables.tf            # Terraform variables definition
│   ├── main.tf                 # Main Terraform configuration that provisions resources
│   └── outputs.tf              # Terraform outputs for deployed resources
├── website_app/
│   ├── app.py                  # Flask application for HEX file uploads and database interaction
│   ├── requirements.txt        # Python dependencies for the website app
├── hmi_server/
│   ├── socket_server.py        # Python socket server for delivering HEX updates
│   └── requirements.txt        # Python dependencies for the HMI socket server
└── README.md                   # This documentation file
```

---

## Overview

This solution is designed to streamline the deployment of an OTA update system:

- **Infrastructure Provisioning:**  
  Terraform scripts in the `terraform/` directory automate the provisioning of both the Azure Web App and the Linux VM for the HMI server. Additionally, the Terraform scripts handle the deployment of the website code by generating a SAS URL for the ZIP package stored in an Azure Storage container.

- **Website Server Deployment:**  
  The website app, built with Flask, lets administrators upload HEX files that represent car updates. The app then stores the update metadata in an Azure SQL Database, which serves as the central repository for update details.

- **HMI Server Operation:**  
  The HMI server running on a Linux VM listens over a network socket. When a client requests a particular HEX file update, the server queries the database, retrieves the corresponding file (often stored as a blob in Azure Storage), and transmits it back over the socket connection.

---

## Deployment Workflow

1. **Provisioning via Terraform:**  
   - The Terraform configuration (`main.tf`, `provider.tf`, etc.) sets up the necessary Azure resources, including the Web App, SQL Database, Storage Account, and Virtual Machine.
   - The `cloud-init-hmi.yaml` script is used to configure the HMI VM. It installs necessary software, clones the repository (with proper SSH key authentication for private repos), and starts the HMI socket server as a systemd service.

2. **Automatic Website Deployment:**  
   - The website code is packaged as a docker file.
   - The docker file is built and pushed to a docker registry.
   
3. **HMI Server Configuration:**  
   - The VM for the HMI server is configured using the cloud-init script, which handles installation of dependencies, setup of SSH keys, repository cloning, and configuration of the HMI system service.

---

