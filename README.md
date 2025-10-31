# ytsum - YouTube Transcript Summarizer

Automated tool to fetch YouTube video transcripts from channels you follow and generate AI-powered summaries with key points. Perfect for running on a Raspberry Pi as a daily automation.

## Features

- **Channel Management**: Follow YouTube channels and automatically track new videos
- **Transcript Fetching**: Automatically fetch transcripts for new videos
- **AI Summarization**: Generate concise summaries with key takeaways using OpenRouter (Claude, GPT, Llama, etc.)
- **Web Interface**: Modern web UI accessible from any device on your network
- **Terminal UI**: Beautiful TUI for managing channels, viewing summaries, and checking run history
- **Daily Automation**: Systemd service for automatic daily checks
- **Run History**: Track all processing runs with detailed statistics
- **SQLite Database**: Lightweight, file-based storage perfect for Raspberry Pi

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
- Linux system (tested on Raspberry Pi OS)

## Installation

### Quick Install

```bash
# Clone or download to your Raspberry Pi
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

```bash
# Copy service file
sudo cp ytsum.service /etc/systemd/system/ytsum@.service

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable ytsum@$(whoami).service
sudo systemctl start ytsum@$(whoami).service

# Check status
sudo systemctl status ytsum@$(whoami).service

# View logs
sudo journalctl -u ytsum@$(whoami).service -f
```

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
| `CHECK_SCHEDULE` | Daily check time (HH:MM) | `08:00` |
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

- All data is stored locally in SQLite on your Raspberry Pi
- API keys are stored in `~/.config/ytsum/.env` (not synced/shared)
- Transcripts and summaries are never sent anywhere except to OpenRouter for summarization
- No telemetry or data collection

## License

MIT License - feel free to modify and use as needed.

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
