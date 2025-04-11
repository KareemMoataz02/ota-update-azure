# OTA Update Azure Deployment

This repository provisions two Azure servers using Terraform IaC and provides code stubs:

1. **Website Server**: An Azure Web App (running a Flask app) that lets your company upload new HEX file updates for cars and saves update metadata in an Azure SQL Database.
2. **HMI Server**: A Linux Virtual Machine running a Python socket server. The HMI server listens for update requests over a socket, queries the database, and sends back the requested HEX file update.

## Directory Structure

ota-update-azure/ 
├── terraform/ 
│ ├── provider.tf 
│ ├── variables.tf 
│ ├── main.tf 
│ └── outputs.tf 
├── website_app/ 
│ ├── app.py 
│ └── requirements.txt 
├── hmi_server/ 
│ ├── socket_server.py 
│ └── requirements.txt 
└── README.md



Testing 

Below is a revised complete deliverable that uses Terraform IaC to not only provision the Azure Web App but also automatically deploy your website code (as a ZIP package) using the “WEBSITE_RUN_FROM_PACKAGE” mechanism. In this example, the website ZIP package (containing your Flask app code) is uploaded to an Azure Storage container, a SAS URL is generated for it, and that URL is set as an app setting on the Web App so that the code is automatically deployed.

The overall file structure is:

```
ota-update-azure/
├── terraform/
│   ├── provider.tf
│   ├── variables.tf
│   ├── main.tf
│   └── outputs.tf
├── website_app/
│   ├── app.py
│   ├── requirements.txt
│   └── website_app.zip    
├── hmi_server/
│   ├── socket_server.py
│   └── requirements.txt
└── README.md
```

