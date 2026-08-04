FROM python:3.11-slim

WORKDIR /app

# Install packages directly (no requirements.txt needed)
RUN pip install --no-cache-dir discord.py PyGithub python-dotenv aiohttp

# Copy bot files
COPY . .

# Create configs directory
RUN mkdir -p configs sessions

# Expose port
EXPOSE 7860

# Run the bot
CMD ["python", "app.py"]
