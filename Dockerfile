# Use an official Python image with a version you control
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (if any)
# None needed for your bot, but good practice to include
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Command to run the application
CMD ["python", "main.py"]
