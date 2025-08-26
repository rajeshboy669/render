# Base image
FROM python:3.11-slim

# Install Chrome & dependencies
RUN apt-get update && apt-get install -y wget gnupg unzip curl \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update && apt-get install -y google-chrome-stable \
    && CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && wget -q https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip -d /usr/local/bin/ \
    && rm chromedriver_linux64.zip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set display for Chrome
ENV DISPLAY=:99

# Copy app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Run app
CMD ["python", "bot.py"]
