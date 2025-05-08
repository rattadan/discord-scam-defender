# Discord Scam Defender with Ollama Integration

The most powerful way to keep scammers away from your Discord community

A powerful Discord moderation bot that uses local LLMs via Ollama to detect and remove inappropriate content, scams, and spam from your Discord servers. The bot features hybrid moderation with different character personalities and can analyze both text and images.

## Features

- **Hybrid Content Moderation**: Uses different models for optimal performance
  - Llama 3.2 for text analysis and chat responses
  - Vision models for image processing and scam detection
- **Comprehensive Scam Detection**: Identifies and removes:
  - Phishing attempts and social engineering
  - Gift card scams and fake giveaways
  - Crypto investment schemes
  - Tech support and virus alert scams
  - Job offer scams and get-rich-quick schemes
- **Image Analysis**: Detects inappropriate images and visual scams

- **Progressive Discipline**: Three-strike system for violators
- **Customizable Personalities**: Choose from multiple character personas
  - Sheriff Terence Hill: Laid-back, witty lawman
  - Batman: Dark, brooding vigilante
  - RoboCop: Precise, mechanical enforcer
  - Rambo: Terse, intense survivor
- **LLM-Generated Responses**: Dynamic, character-driven moderation messages

## Requirements

- Python 3.8+
- [Ollama](https://ollama.ai/) installed locally with the following models:
  - `llama3.2-vision:latest` (for text and image analysis)
  - `moondream:latest` (alternative vision model)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

## Installation

1. **Clone this repository**

   ```bash
   git clone https://github.com/rattadan/discord-scam-defender
   cd discord-scam-defender
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv newenv
   source newenv/bin/activate  # On Windows: newenv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Prepare Ollama**

   Ensure Ollama is installed and running. Pull the required models:

   ```bash
   ollama pull llama3.2:1b
   ollama pull llama3.2-vision:latest
 
   ```

   Check available models with:

   ```bash
   ollama list
   ```

5. **Create a .env file**

   Copy the example config file and customize it:

   ```bash
   cp .env.example .env
   # Edit .env with your favorite editor
   ```

6. **Start the bot**

   ```bash
   python discord-scam-defender.py
   ```

## Telegram Bot Setup

1. **Create a new bot**
   - Contact [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow the instructions
   - Copy the API token and add it to your `.env` file

2. **Configure Group Permissions**
   - Add your bot to your Telegram group
   - Make the bot an admin with these permissions:
     - Delete messages
     - Ban users
     - Pin messages (optional but recommended)
   - The bot does NOT need to see all messages by default

3. **Privacy Settings**
   - Send `/setprivacy` to @BotFather
   - Select your bot
   - Set it to `Disable` if you want the bot to see all messages in the group
   - Set it to `Enable` if you only want the bot to see messages that start with a command (in this case, the bot will only moderate messages when it's @mentioned)

## Customization

All customization options are available in the `.env` file:

### Basic Configuration

```env
TELEGRAM_TOKEN=your_telegram_token_here
OLLAMA_BASE_URL=http://localhost:11434
TEXT_MODEL=llama3.2:1b
VISION_MODEL=llama3.2-vision:latest
```


## Running as a Service

### Systemd (Linux)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/telegram-ban-bot.service
```

Add the following content (adjust paths as needed):

```ini
[Unit]
Description=Telegram Moderation Bot
After=network.target

[Service]
User=yourusername
WorkingDirectory=/path/to/telegram-ban-bot_ollama
Environment="PATH=/path/to/telegram-ban-bot_ollama/newenv/bin"
ExecStart=/path/to/telegram-ban-bot_ollama/newenv/bin/python telegram-ban-bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable telegram-ban-bot
sudo systemctl start telegram-ban-bot
```

### Docker

To run with Docker, create a `Dockerfile`:

```Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "telegram-ban-bot.py"]
```
