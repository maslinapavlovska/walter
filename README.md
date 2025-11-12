# Walter - Victorian History Discord Bot

A Discord bot that posts daily "On This Day in History" messages at 10 AM with Victorian British humor in the style of Jerome K. Jerome and George Grossmith, plus water supply interruption notifications for Sofia, Bulgaria.

## Quick Start

### 1. Prerequisites

- Python 3.11 or higher
- A Discord account
- An OpenAI API key (costs ~$34/month for daily messages)
- Playwright (for web scraping water stops data)

### 2. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and name it "Walter"
3. Go to the "Bot" tab → Click "Add Bot"
4. Click "Reset Token" and **immediately copy the token** (you won't see it again!)
5. Under "Privileged Gateway Intents", enable:
   - Message Content Intent
   - Server Members Intent (optional but recommended)
6. Go to "OAuth2" → "URL Generator"
   - Select Scopes: `bot`
   - Select Permissions:
     - View Channels
     - Send Messages
     - Mention @everyone, @here, and All Roles
     - Embed Links
     - Read Message History
7. Copy the generated URL and invite the bot to your server

### 3. Get Your Channel ID

1. In Discord, go to User Settings → Advanced → Enable "Developer Mode"
2. Right-click on the channel where you want daily messages → "Copy ID"

### 4. OpenAI API Setup

1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign up/Log in (separate from ChatGPT account)
3. Go to API Keys → Create new secret key
4. Add at least $5 in credits (Settings → Billing)

### 5. Bot Installation

```bash
# Clone or download this bot
cd walter-bot

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your actual tokens and IDs
```

### 6. Configure .env File

```
DISCORD_TOKEN=your_bot_token_here
CHANNEL_ID=your_channel_id_here
OPENAI_API_KEY=your_openai_api_key_here
TIMEZONE=America/New_York  # Change to your timezone
```

### 7. Run the Bot

#### Option A: Run Directly with Python

```bash
python bot.py
```

#### Option B: Run with Docker (Recommended for Production)

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

**Note:** Make sure your `.env` file is configured before running with Docker.

The bot will:
- Connect to Discord
- Schedule daily messages at 10 AM in your timezone
- Post Victorian-styled historical commentary

## Features

### 📜 Daily History Posts
- Fetches historical events from Wikipedia API
- Generates Victorian-style commentary using OpenAI
- Posts automatically at 10:00 AM (configurable timezone)

### 💧 Water Supply Notifications (Sofia, Bulgaria)
- Scrapes water stop data from sofiyskavoda.bg
- Shows both current (Текущи спирания) and planned (Планирани спирания) stops
- Included automatically in daily morning posts
- 30-minute caching to reduce server load
- Manual checks available anytime

## Commands

- `!test_daily` - (Admin only) Manually trigger the daily post (history + water stops)
- `!check_water` - Check current and planned water stops in Sofia
- `!walter_status` - Check bot status and next scheduled post
- `!next_post` - See when the next post is scheduled

## Hosting Options

### Docker Deployment (Recommended)

The bot includes Docker support for easy deployment. Simply:

```bash
# On your server
git clone <your-repo>
cd walter-bot
cp .env.example .env
# Edit .env with your credentials
docker-compose up -d
```

Logs persist in `./logs` and `./walter.log` on the host machine.

### Free: Oracle Cloud
- Sign up for [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
- Create an Always-Free VM (ARM-based, 24GB RAM)
- Install Docker and use docker-compose (recommended), or install Python and run with PM2/systemd

### Budget: DigitalOcean ($5/month)
- Create a basic Droplet
- Install Docker and use docker-compose (recommended), or use the setup script: `bash setup_vps.sh`

### Keep Bot Running 24/7

**With Docker (recommended):**
```bash
# Docker Compose automatically restarts the container
docker-compose up -d
```

**Without Docker - Using PM2:**
```bash
npm install -g pm2
pm2 start bot.py --name walter --interpreter python3
pm2 save
pm2 startup
```

**Without Docker - Using systemd:**
(see walter.service file for configuration)

## Cost Breakdown

- **OpenAI API**: ~$34/month for 100 daily messages
- **Hosting**: Free (Oracle) or $5/month (DigitalOcean)
- **Total**: $34-39/month

## Victorian Humor Styles

The bot rotates between three styles:

1. **Standard**: Balanced Victorian wit with modern observations
2. **Pooter-style**: From "Diary of a Nobody" - earnest and oblivious
3. **Jerome-style**: From "Three Men in a Boat" - meandering and self-deprecating

## Troubleshooting

### Bot is online but not posting
- Check timezone setting in .env
- Run `!test_daily` to test manually
- Check walter.log for errors

### "Rate limit exceeded" errors
- Normal at start (retries automatically)
- If persistent, check OpenAI billing/credits

### Bot crashes on startup
- Verify all tokens in .env are correct
- Check Python version: `python --version` (needs 3.8+)
- Install missing dependencies: `pip install -r requirements.txt`

## Expanding Walter

The modular architecture makes it easy to add:
- Weekly digests (add to scheduler)
- Different AI personalities (modify prompts in ai_service.py)
- Multiple channels (add more channel IDs)
- Interactive commands (add @bot.command decorators)

## Support

Check the logs first: `tail -f walter.log`

For OpenAI API issues: [platform.openai.com/docs](https://platform.openai.com/docs)
For Discord.py help: [discordpy.readthedocs.io](https://discordpy.readthedocs.io)

## License

MIT - Use freely and modify as needed!
