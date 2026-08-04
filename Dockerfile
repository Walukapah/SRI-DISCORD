FROM python:3.11-slim

WORKDIR /app

# Install packages directly (no requirements.txt needed)
RUN pip install --no-cache-dir discord.py>=2.3.0 PyGithub>=2.1.0 python-dotenv>=1.0.0 aiohttp>=3.8.0

# Copy bot files
COPY . .

# Create configs directory
RUN mkdir -p configs sessions

# Expose port
EXPOSE 7860

# Run the bot
CMD ["python", "app.py"]
