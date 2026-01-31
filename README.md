# ytsum - YouTube Transcript Summarizer

[![AI Assisted](https://img.shields.io/badge/AI-Assisted-blue?logo=openai)](https://github.com/ajstafford/ytsum)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Automated tool to fetch YouTube video transcripts from channels you follow and generate AI-powered summaries with key points.

> **Note**: This project was developed with assistance from AI tools. See [AI_ATTRIBUTION.md](AI_ATTRIBUTION.md) for details.

## Features

- **Multi-user Authentication**: Secure login and registration with private user data
- **Channel Management**: Follow YouTube channels and automatically track new videos
- **Transcript Fetching**: Automatically fetch transcripts for new videos
- **AI Summarization**: Generate concise summaries with key takeaways using OpenRouter AI
- **Web Interface**: Modern web UI accessible from any device on your network
- **Telegram Notifications**: Get instant notifications when new video summaries are available
- **Daily Automation**: Docker scheduler runs every 30 minutes to check for new videos
- **Run History**: Track all processing runs with detailed statistics
- **SQLite Database**: Lightweight, file-based storage

## Architecture

### 3-Container Docker Architecture
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  ytsum-web   │     │ytsum-scheduler│    │ytsum-telegram│
│  (Flask UI)  │     │ (automation)  │    │ (bot + queue)│
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┴────────────────────┘
                            │
                   ┌────────▼─────────┐
                   │   SQLite DB      │
                   │  + Queue Table   │
                   └──────────────────┘
```

**High Availability Design:**
- Web, scheduler, and Telegram bot run in separate containers
- Each service can be restarted independently
- Message queue ensures reliable notification delivery
- Telegram bot runs 24/7 for instant user verification

## Requirements

- Docker and Docker Compose
- YouTube Data API v3 key (free from Google Cloud Console)
- OpenRouter API key (from openrouter.ai)

## Installation

Running ytsum with Docker is the easiest way to get started. All dependencies are bundled in the container, and your data is automatically persisted.

### Prerequisites

1. Install Docker and Docker Compose:
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install docker.io docker-compose
   
   # Or use Docker's official installation script
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   ```

2. Add your user to the docker group (optional, to run without sudo):
   ```bash
   sudo usermod -aG docker $USER
   # Log out and back in for this to take effect
   ```

### Get API Keys

1. **YouTube Data API v3 Key**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or use existing)
   - Enable "YouTube Data API v3"
   - Create credentials → API Key
   - Copy the API key

2. **OpenRouter API Key**:
   - Go to [OpenRouter](https://openrouter.ai/)
   - Sign up and get an API key

### Quick Start with Docker

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ajstafford/ytsum.git
   cd ytsum
   ```

2. **Configure API keys**:
   ```bash
   # Copy the example environment file
   cp docker.env.example docker.env
   
   # Edit docker.env and add your API keys
   nano docker.env
   ```
   
   **Required:** Update these values in `docker.env`:
   - `YOUTUBE_API_KEY=your_youtube_api_key_here`
   - `OPENROUTER_API_KEY=your_openrouter_api_key_here`

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```
   
   This will:
   - Build the Docker image
   - Create a persistent volume for your database
   - Start the web interface on port 5000
   - Run in the background

4. **Access the web interface**:
   - From the same device: `http://localhost:5000`
   - From another device on your network: `http://YOUR_SERVER_IP:5000`
   - Find your server's IP: `hostname -I`

### Docker Management

**View logs**:
```bash
docker-compose logs -f
```

**Stop the application**:
```bash
docker-compose stop
```

**Restart the application**:
```bash
docker-compose restart
```

**Stop and remove containers** (data is preserved):
```bash
docker-compose down
```

**Update to latest version**:
```bash
git pull
docker-compose up -d --build
```

**Run manual check/processing**:
```bash
docker-compose exec ytsum ytsum run
```

**Access the TUI interface**:
```bash
docker-compose exec ytsum ytsum ui
```

**View application status**:
```bash
docker-compose exec ytsum ytsum status
```

### Data Persistence

Your database and logs are stored in a Docker volume named `ytsum-data`. This ensures:
- ✅ Data persists between container restarts
- ✅ Data survives container removal
- ✅ Data is preserved during updates

**View volume information**:
```bash
# List all volumes to find your ytsum volume
docker volume ls | grep ytsum

# Inspect the volume (replace ytsum_ytsum-data with your actual volume name from above)
docker volume inspect ytsum_ytsum-data
```

**Backup your data**:
```bash
# Create a backup of the database
# Note: Replace 'ytsum_ytsum-data' with your actual volume name from 'docker volume ls'
docker run --rm -v ytsum_ytsum-data:/data -v $(pwd):/backup alpine tar czf /backup/ytsum-backup.tar.gz -C /data .
```

**Restore from backup**:
```bash
# Restore database from backup
# Note: Replace 'ytsum_ytsum-data' with your actual volume name from 'docker volume ls'
docker run --rm -v ytsum_ytsum-data:/data -v $(pwd):/backup alpine tar xzf /backup/ytsum-backup.tar.gz -C /data
```

**Reset/delete all data** (⚠️ WARNING: This deletes everything):
```bash
docker-compose down -v
```

### Docker Configuration

All configuration is done via the `docker.env` file. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key | Required |
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `OPENROUTER_MODEL` | Model to use | `anthropic/claude-3.5-sonnet` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional) | - |
| `SUMMARY_MAX_LENGTH` | Max summary length in words | `500` |
| `MAX_KEY_POINTS` | Number of key points to extract | `5` |
| `MAX_VIDEOS_PER_CHECK` | Max videos to check per channel | `50` |
| `DAYS_TO_LOOK_BACK` | How far back to check for new videos | `7` |

After changing `docker.env`, restart the container:
```bash
docker-compose restart
```

### Telegram Notifications Setup (Optional)

Get instant Telegram notifications when new video summaries are available:

1. **Create a Telegram Bot**:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow instructions
   - Copy the bot token (looks like `123456789:ABCdefGHI...`)

2. **Configure ytsum**:
   ```bash
   # Add token to docker.env
   echo "TELEGRAM_BOT_TOKEN=your_bot_token_here" >> docker.env
   ```

3. **Use the Scheduler Compose File** (includes Telegram service):
   ```bash
   docker-compose -f docker-compose.with-scheduler.yml up -d
   ```

4. **Link Your Account**:
   - Open ytsum web interface → Settings → Telegram
   - Click "Generate Verification Code"
   - In Telegram, message your bot: `/verify YOUR_CODE`
   - Your account is now linked!

5. **Test Notifications**:
   - Click "Send Test Message" in Settings
   - You should receive a test message in Telegram

**Architecture**: The Telegram bot runs in a separate container (`ytsum-telegram`) that:
- Receives incoming messages (for account linking via `/verify`)
- Processes outgoing messages from a queue
- Runs 24/7 independently of web and scheduler

### Automated Scheduling with Docker

The Docker container runs the web interface by default. To enable automatic daily video processing, you have three options:

#### Option 1: Use the Scheduler Compose File (Easiest)

Use the provided `docker-compose.with-scheduler.yml` which includes both the web interface and a scheduler service:

```bash
# Stop the current setup if running
docker-compose down

# Start with scheduler
docker-compose -f docker-compose.with-scheduler.yml up -d
```

This runs both the web interface and a scheduler that processes videos daily at the time specified in `CHECK_SCHEDULE` (default: 08:00).

**Note:** SQLite handles concurrent reads well, but the web service and scheduler may occasionally encounter brief database locks during writes. This is normal SQLite behavior when multiple processes access the same database.

Trigger processing manually whenever you want:

```bash
docker-compose exec ytsum ytsum run
```

Or from the web interface, click the "Run Check Now" button.

### Troubleshooting Docker

**Container won't start**:
```bash
# Check logs for errors
docker-compose logs

# Verify docker.env has correct API keys
cat docker.env | grep API_KEY
```

**Permission issues**:
```bash
# Ensure your user is in the docker group
groups | grep docker

# If not, add yourself and re-login
sudo usermod -aG docker $USER
```

**Port 5000 already in use**:
Edit `docker-compose.yml` and change the port mapping:
```yaml
ports:
  - "8080:5000"  # Use port 8080 instead
```

**Check container health**:
```bash
docker-compose ps
```

## Configuration

### Get API Keys

1. **YouTube Data API v3 Key**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or use existing)
   - Enable "YouTube Data API v3"
   - Create credentials → API Key
   - Copy the API key

2. **OpenRouter API Key**:
   - Go to [OpenRouter](https://openrouter.ai/)
   - Sign up and get an API key

### Edit Configuration

Edit `~/.config/ytsum/.env`:

```bash
nano ~/.config/ytsum/.env
```

Add your API keys:

```env
YOUTUBE_API_KEY=your_youtube_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

See `.env.example` for all available configuration options.

## Usage

### Launch Web Interface

The web interface runs inside the Docker container and is accessible on port 5000.

**Access the Web UI:**
- From the same device: `http://localhost:5000`
- From another device on your network: `http://YOUR_PI_IP:5000`
  - Find your Pi's IP: `hostname -I`
  - Example: `http://192.168.1.100:5000`

**Web Interface Features:**
- **Dashboard**: View stats, recent summaries at a glance
- **Channels**: Add/remove channels with a simple form
- **Videos**: Browse, search, and filter videos with pagination
- **Summary View**: Read full summaries with proper formatting and scrolling
- **History**: View all automation runs with error details
- **Manual Run**: Trigger processing with a button click
- **Responsive**: Works on desktop, tablet, and mobile

### Command Line Usage

```bash
# View current status
ytsum status

# Run check and process once
ytsum run

# View configuration
ytsum config

# Run scheduler daemon
ytsum schedule
```

### Adding Channels

You can add channels using various formats:
- Channel URL: `https://www.youtube.com/channel/UC...`
- Custom URL: `https://www.youtube.com/@channelname`
- Channel ID: `UC...`

Example channels to try:
- `https://www.youtube.com/@fireship`
- `https://www.youtube.com/@ThePrimeTimeagen`

## Project Structure

```
ytsum/
├── src/ytsum/
│   ├── __init__.py                # Package initialization
│   ├── cli.py                     # CLI entry point and commands
│   ├── config.py                  # Configuration management
│   ├── database.py                # SQLAlchemy models and DB operations
│   ├── youtube.py                 # YouTube API integration
│   ├── summarizer.py              # OpenRouter/LLM integration
│   ├── tui.py                     # Textual TUI interface
│   ├── scheduler.py               # Daily automation logic
│   ├── telegram.py                # Telegram bot class
│   └── telegram_bot_service.py    # Telegram broker service
├── src/ytsum/templates/
│   ├── base.html                  # Base template
│   ├── settings.html              # User settings (NEW)
│   └── ...                        # Other templates
├── data/                          # SQLite database (created at runtime)
├── .env.example                   # Example configuration
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Package configuration
├── install.sh                     # Installation script
├── ytsum.service                  # Service file (for non-Docker installs)
├── ytsum-web.service              # Web service file (for non-Docker installs)
├── ytsum.timer                    # Timer file (for non-Docker installs)
├── docker-compose.yml             # Docker: web only
├── docker-compose.with-scheduler.yml  # Docker: web + scheduler + telegram
└── README.md                      # This file
```

## Database Schema

### Core Tables
- **youtube_channels**: Followed YouTube channels
- **videos**: Discovered videos from channels
- **transcripts**: Fetched video transcripts
- **summaries**: AI-generated summaries with key points
- **run_history**: Automated run history and statistics

### User & Authentication
- **users**: User accounts with authentication
  - `telegram_chat_id`: Linked Telegram account
  - `telegram_enabled`: Notification enabled flag
  - `telegram_verification_code`: Temporary code for linking

### Telegram Notifications
- **telegram_queue**: Message queue for reliable delivery
  - `chat_id`: Target Telegram chat
  - `message`: Message content (Markdown/HTML)
  - `status`: pending, sent, or failed
  - `retry_count`: Failed delivery attempts

Database location: `~/.local/share/ytsum/ytsum.db`

## Configuration Options

All configuration is done via environment variables in `~/.config/ytsum/.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key | Required |
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `OPENROUTER_MODEL` | Model to use | `anthropic/claude-3.5-sonnet` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications | Optional |
| `CHECK_SCHEDULE` | Daily check time (HH:MM) - only used with manual scheduling | `08:00` |
| `SUMMARY_MAX_LENGTH` | Max summary length in words | `500` |
| `MAX_KEY_POINTS` | Number of key points to extract | `5` |
| `MAX_VIDEOS_PER_CHECK` | Max videos to check per channel | `50` |
| `DAYS_TO_LOOK_BACK` | How far back to check for new videos | `7` |

## Troubleshooting

### API Key Issues

```bash
# Verify configuration
ytsum config

# The output should show your API keys as "***" (set)
```

### No Transcripts Available

Some videos don't have transcripts enabled. This is normal and will be logged as a warning.

Check your usage at [OpenRouter Dashboard](https://openrouter.ai/dashboard)

### Database Issues

```bash
# View database location
ytsum config | grep "Database Path"

# Reset database (WARNING: deletes all data)
rm ~/.local/share/ytsum/ytsum.db
ytsum init
```

### Docker Scheduler Not Running

If using Docker Compose with scheduler and automated checks aren't happening:

```bash
# Check scheduler container logs
docker-compose -f docker-compose.with-scheduler.yml logs -f scheduler

# Restart scheduler
docker-compose -f docker-compose.with-scheduler.yml restart scheduler
```

### Manual Scheduler Issues

If running `ytsum schedule` manually:

```bash
# Run scheduler in foreground to see logs
ytsum schedule

# Check if another instance is running
ps aux | grep "ytsum schedule"

## Development

### Install in Development Mode

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
flake8 src/
```



## Privacy & Data

- All data is stored locally in SQLite
- API keys are stored in `~/.config/ytsum/.env` (not synced/shared)
- Transcripts and summaries are never sent anywhere except to OpenRouter for summarization
- No telemetry or data collection

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

Built with:
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Textual](https://textual.textualize.io/) - TUI framework
- [Bootstrap](https://getbootstrap.com/) - Web UI styling
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) - Transcript fetching
- [Google YouTube API](https://developers.google.com/youtube/v3) - Channel/video data
- [OpenRouter](https://openrouter.ai/) - LLM API gateway
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

## Enhancement Backlog

Potential future enhancements (prioritized):

### High Priority
- [ ] **Mark as Read/Favorite**: Flag videos you've watched or want to save
- [ ] **Full-text search**: Search across all summaries and transcripts
- [ ] **Video notes**: Add personal notes to summaries
- [ ] **Background processing**: Run check/process in background without blocking web UI
- [ ] **Export summaries**: Export to Markdown, PDF, or plain text files

### Medium Priority
- [x] **Telegram notifications**: Get instant notifications when new summaries are available ✅
- [ ] **Email notification system**: Alternative email-based notifications
- [ ] **Custom prompt templates**: Define your own summarization prompts
- [ ] **Multiple summary styles**: Choose between brief, detailed, or bullet-point formats
- [ ] **Tags/categories**: Organize videos with custom tags
- [ ] **Video playlists support**: Follow entire YouTube playlists
- [ ] **Channel groups**: Organize channels into groups (Tech, News, Education, etc.)

### Low Priority / Nice-to-Have
- [ ] **RSS feed generation**: Generate RSS feeds from summaries
- [ ] **API endpoint**: REST API for integration with other tools
- [ ] **Dark mode toggle**: UI theme switcher in web interface
- [ ] **Statistics dashboard**: Charts showing viewing patterns, most summarized channels
- [ ] **Transcript viewer**: View full transcripts inline with timestamps
- [ ] **Multi-language support**: Transcripts in multiple languages
- [ ] **Share summaries**: Generate shareable links to summaries
- [ ] **Batch operations**: Process/delete multiple videos at once

### Completed
- [x] **Web UI option**: Modern web interface with Bootstrap
- [x] **TUI interface**: Terminal-based interface with Textual
- [x] **Daily automation**: Systemd service for scheduled runs
- [x] **Search and filter videos**: By channel, summary status, etc.
