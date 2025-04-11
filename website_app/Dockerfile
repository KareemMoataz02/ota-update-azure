# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install prerequisites for adding Microsoft's repository
RUN apt-get update && apt-get install -y \
    curl \
    apt-transport-https \
    gnupg2

# Add Microsoft's GPG key and repository for msodbcsql18
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && echo "deb [arch=amd64] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list

# Update package lists and install msodbcsql18, unixodbc-dev, and build-essential
RUN apt-get update && \
    ACCEPT_EULA=Y apt-get install -y \
      msodbcsql18 \
      unixodbc-dev \
      build-essential && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install Python dependencies from requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose the port on which Gunicorn will listen
EXPOSE 8000

# Set the startup command for your app (adjust the module path if needed)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
