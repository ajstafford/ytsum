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
- **AI Summarization**: Generate concise summaries with key takeaways using OpenRouter (Claude, GPT, Llama, etc.)
- **Web Interface**: Modern web UI accessible from any device on your network
- **Terminal UI**: Beautiful TUI for managing channels, viewing summaries, and checking run history
- **Daily Automation**: Systemd service for automatic daily checks
- **Run History**: Track all processing runs with detailed statistics
- **SQLite Database**: Lightweight, file-based storage

## Architecture

```
YouTube API → New Videos → Transcript Fetching → OpenRouter AI → Summaries → TUI Display
                                ↓
                            SQLite Database
```

## Requirements

- Python 3.9 or higher
- YouTube Data API v3 key (free from Google Cloud Console)
- OpenRouter API key (from openrouter.ai)
- Linux system

**OR**

- Docker and Docker Compose (for containerized deployment)
- YouTube Data API v3 key (free from Google Cloud Console)
- OpenRouter API key (from openrouter.ai)

## Docker Installation (Recommended)

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
   - Choose your preferred model (Claude 3.5 Sonnet recommended)

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
| `SUMMARY_MAX_LENGTH` | Max summary length in words | `500` |
| `MAX_KEY_POINTS` | Number of key points to extract | `5` |
| `MAX_VIDEOS_PER_CHECK` | Max videos to check per channel | `50` |
| `DAYS_TO_LOOK_BACK` | How far back to check for new videos | `7` |

After changing `docker.env`, restart the container:
```bash
docker-compose restart
```

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

#### Option 2: Host Cron

Add a cron job on your host system to trigger processing:

```bash
# Edit your crontab
crontab -e

# Add this line to run daily at 8 AM
# Replace /path/to/ytsum/ with the actual path to your ytsum directory
0 8 * * * cd /path/to/ytsum && docker-compose run --rm ytsum ytsum run >> /var/log/ytsum-cron.log 2>&1
```

This uses `docker-compose run` which starts a new container, runs the command, and removes the container afterward.

#### Option 3: Manual Processing

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

## Installation

### Quick Install

```bash
# Clone or download
cd /home/your-user/ytsum

# Run installation script
./install.sh
```

The installation script will:
1. Create a Python virtual environment
2. Install all dependencies
3. Initialize configuration files
4. Optionally set up systemd service

### Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install package
pip install -e .

# Initialize configuration
ytsum init
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
   - Choose your preferred model (Claude 3.5 Sonnet recommended)

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

### Launch TUI Interface

```bash
ytsum ui
```

The TUI provides tabs for:
- **Channels**: Add/remove channels to follow
- **Videos**: Browse videos and view summaries
- **History**: View run history and statistics
- **Settings**: View current configuration

Navigation:
- `Tab` / `Shift+Tab`: Navigate between tabs
- `q`: Quit
- `d`: Toggle dark mode
- `r`: Run manual check (from home screen)

### Launch Web Interface

```bash
ytsum web
```

The web interface will start on `http://0.0.0.0:5000` (accessible from any device on your network).

**Custom Options:**
```bash
# Custom port
ytsum web --port 8080

# Localhost only (not accessible from network)
ytsum web --host 127.0.0.1

# Enable debug mode
ytsum web --debug
```

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

# Run scheduler daemon (for systemd)
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

## Automation

### Using Systemd (Recommended)

The installation script can set up systemd for you. If you skipped it, manually install:

#### Web Interface Service (Always Running)

To keep the web interface running 24/7:

```bash
# Copy web service file
sudo cp ytsum-web.service /etc/systemd/system/ytsum-web@.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the web service
sudo systemctl enable ytsum-web@$(whoami).service
sudo systemctl start ytsum-web@$(whoami).service

# Check web service status
sudo systemctl status ytsum-web@$(whoami).service

# View web service logs
sudo journalctl -u ytsum-web@$(whoami).service -f
```

The web interface will be available at `http://your-server-ip:5000` and will:
- Start automatically on boot
- Restart automatically if it crashes
- Be accessible from any device on your network

#### Scheduled Processing (Daily Timer)

For automatic daily video checking and summarization:

```bash
# Copy service and timer files
sudo cp ytsum.service /etc/systemd/system/ytsum@.service
sudo cp ytsum.timer /etc/systemd/system/ytsum.timer

# Reload systemd
sudo systemctl daemon-reload

# Enable service on boot (optional)
sudo systemctl enable ytsum@$(whoami).service

# Enable and start timer for automatic daily checks (runs daily at midnight)
sudo systemctl enable ytsum.timer
sudo systemctl start ytsum.timer

# Check timer status
sudo systemctl status ytsum.timer

# View service logs
sudo journalctl -u ytsum@$(whoami).service -f

# View timer logs
sudo journalctl -u ytsum.timer -f
```

**Note**: The systemd timer runs daily at **00:00 (midnight)** by default. The `CHECK_SCHEDULE` config variable only applies when running `ytsum schedule` manually or with cron.

### Using Cron (Alternative)

Add to crontab:

```bash
crontab -e
```

Add line:

```
0 8 * * * /home/your-user/ytsum/venv/bin/ytsum run
```

## Project Structure

```
ytsum/
├── src/ytsum/
│   ├── __init__.py       # Package initialization
│   ├── cli.py            # CLI entry point and commands
│   ├── config.py         # Configuration management
│   ├── database.py       # SQLAlchemy models and DB operations
│   ├── youtube.py        # YouTube API integration
│   ├── summarizer.py     # OpenRouter/LLM integration
│   ├── tui.py            # Textual TUI interface
│   └── scheduler.py      # Daily automation logic
├── data/                 # SQLite database (created at runtime)
├── .env.example          # Example configuration
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Package configuration
├── install.sh            # Installation script
├── ytsum.service         # Systemd service file
└── README.md             # This file
```

## Database Schema

- **channels**: Followed YouTube channels
- **videos**: Discovered videos from channels
- **transcripts**: Fetched video transcripts
- **summaries**: AI-generated summaries with key points
- **run_history**: Automated run history and statistics

Database location: `~/.local/share/ytsum/ytsum.db`

## Configuration Options

All configuration is done via environment variables in `~/.config/ytsum/.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key | Required |
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `OPENROUTER_MODEL` | Model to use | `anthropic/claude-3.5-sonnet` |
| `CHECK_SCHEDULE` | Daily check time (HH:MM) - only used with `ytsum schedule` daemon or cron, not systemd timer | `08:00` |
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

### OpenRouter Costs

OpenRouter charges per token. Claude 3.5 Sonnet is recommended for quality but costs around $3/$15 per million tokens (input/output). Consider:
- Using cheaper models like `meta-llama/llama-3.1-70b-instruct`
- Limiting `MAX_VIDEOS_PER_CHECK` and `MAX_KEY_POINTS`
- Reducing `SUMMARY_MAX_LENGTH`

Check your usage at [OpenRouter Dashboard](https://openrouter.ai/dashboard)

### Database Issues

```bash
# View database location
ytsum config | grep "Database Path"

# Reset database (WARNING: deletes all data)
rm ~/.local/share/ytsum/ytsum.db
ytsum init
```

### Systemd Service Not Running

```bash
# Check service status
sudo systemctl status ytsum@$(whoami).service

# View logs
sudo journalctl -u ytsum@$(whoami).service -f

# Restart service
sudo systemctl restart ytsum@$(whoami).service
```

### Systemd Timer Not Running

If automated daily checks aren't happening:

```bash
# Check timer status
sudo systemctl status ytsum.timer

# Should show: "Active: active (waiting)"
# If "Active: inactive (dead)", enable and start it:
sudo systemctl enable ytsum.timer
sudo systemctl start ytsum.timer

# View next scheduled run
sudo systemctl list-timers ytsum.timer

# View timer logs
sudo journalctl -u ytsum.timer -f

# View service logs (when timer triggers)
sudo journalctl -u ytsum@$(whoami).service -f
```

**Note**: The timer runs daily at **00:00 (midnight)**. To change the schedule, edit `/etc/systemd/system/ytsum.timer` and modify the `OnCalendar` line, then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ytsum.timer
```

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

## Available Models on OpenRouter

Popular options:
- `anthropic/claude-3.5-sonnet` - Best quality, higher cost
- `openai/gpt-4-turbo` - Great quality, moderate cost
- `meta-llama/llama-3.1-70b-instruct` - Good quality, lower cost
- `google/gemini-pro` - Free tier available

See full list at [OpenRouter Models](https://openrouter.ai/models)

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
- [ ] **Email/notification system**: Get notified when new summaries are available
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
