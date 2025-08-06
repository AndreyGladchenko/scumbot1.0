# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy the bot source code into the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the bot
CMD ["python", "main.py"]
