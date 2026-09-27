FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency file first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser and its system dependencies
RUN playwright install --with-deps chromium

# Copy application code
COPY bot ./bot
COPY services ./services
COPY utils ./utils
COPY data ./data

# Create downloads directory
RUN mkdir -p /app/downloads

# Start the bot
EXPOSE 10000

CMD ["python", "-m", "bot.main"]