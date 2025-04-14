# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies from requirements
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port on which Gunicorn will listen
EXPOSE 8000

# Set the startup command for your app
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
