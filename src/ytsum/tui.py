"""Terminal User Interface for ytsum using Textual."""

from datetime import datetime
from typing import Optional

from rich.table import Table
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)

from sqlalchemy.orm import joinedload

from .config import get_config
from .database import Channel, Database, Video


class SummaryScreen(ModalScreen):
    """Modal screen to display video summary."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def __init__(self, title: str, channel: str, published: str, url: str,
                 summary: str, key_points: list):
        super().__init__()
        self.video_title = title
        self.channel = channel
        self.published = published
        self.url = url
        self.summary = summary
        self.key_points = key_points

    def compose(self) -> ComposeResult:
        """Create the summary display."""
        # Build markdown content
        key_points_md = "\n".join([f"{i}. {point}" for i, point in enumerate(self.key_points, 1)])

        content = f"""# {self.video_title}

**Channel:** {self.channel}
**Published:** {self.published}
**URL:** {self.url}

---

## Summary

{self.summary}

---

## Key Points

{key_points_md}

---

*Press ESC or Q to close*
"""
        with Container(id="summary_container"):
            with VerticalScroll():
                yield Markdown(content, id="summary_markdown")
            yield Button("Close", variant="primary", id="close_btn")

    @on(Button.Pressed, "#close_btn")
    def close_summary(self):
        """Close the summary screen."""
        self.dismiss()

    def action_dismiss(self):
        """Close the modal."""
        self.dismiss()


class StatsPanel(Static):
    """Display statistics panel."""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def on_mount(self) -> None:
        """Update stats when mounted."""
        self.update_stats()

    def update_stats(self) -> None:
        """Update the statistics display."""
        stats = self.db.get_stats()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Channels", str(stats["total_channels"]))
        table.add_row("Total Videos", str(stats["total_videos"]))
        table.add_row("With Transcripts", str(stats["videos_with_transcripts"]))
        table.add_row("With Summaries", str(stats["videos_with_summaries"]))
        table.add_row("Total Runs", str(stats["total_runs"]))

        if stats["last_run"]:
            last_run_time = stats["last_run"].run_timestamp.strftime("%Y-%m-%d %H:%M")
            table.add_row("Last Run", last_run_time)

        self.update(table)


class ChannelsTab(VerticalScroll):
    """Tab for managing channels."""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Label("Add New Channel", classes="section-title")
        with Horizontal(classes="input-group"):
            yield Input(placeholder="Channel URL or ID", id="channel_input")
            yield Button("Add Channel", id="add_channel_btn", variant="primary")

        yield Label("Followed Channels", classes="section-title")
        yield DataTable(id="channels_table")

    def on_mount(self) -> None:
        """Set up the channels table when mounted."""
        table = self.query_one("#channels_table", DataTable)
        table.add_columns("Name", "Channel ID", "Added", "Last Checked")
        self.refresh_channels()

    def refresh_channels(self) -> None:
        """Refresh the channels list."""
        table = self.query_one("#channels_table", DataTable)
        table.clear()

        channels = self.db.get_all_channels()
        for channel in channels:
            last_checked = (
                channel.last_checked.strftime("%Y-%m-%d %H:%M")
                if channel.last_checked
                else "Never"
            )
            table.add_row(
                channel.channel_name,
                channel.channel_id,
                channel.added_date.strftime("%Y-%m-%d"),
                last_checked,
                key=channel.channel_id,
            )

    @on(Button.Pressed, "#add_channel_btn")
    def add_channel(self) -> None:
        """Handle add channel button press."""
        input_widget = self.query_one("#channel_input", Input)
        channel_identifier = input_widget.value.strip()

        if not channel_identifier:
            self.notify("Please enter a channel URL or ID", severity="warning")
            return

        # Import here to avoid circular dependencies
        from .youtube import YouTubeClient

        config = get_config()
        yt_client = YouTubeClient(config.youtube_api_key)

        # Extract channel ID if it's a URL
        channel_id = yt_client.extract_channel_id(channel_identifier)
        if not channel_id:
            channel_id = channel_identifier

        # Get channel info
        self.notify("Fetching channel information...", timeout=2)
        channel_info = yt_client.get_channel_info(channel_id)

        if not channel_info:
            self.notify("Channel not found. Please check the URL or ID.", severity="error")
            return

        # Add to database
        result = self.db.add_channel(
            channel_info["id"], channel_info["name"], channel_info["url"]
        )

        if result:
            self.notify(f"Added channel: {channel_info['name']}", severity="information")
            input_widget.value = ""
            self.refresh_channels()
        else:
            self.notify("Channel already exists", severity="warning")

    @on(DataTable.RowSelected, "#channels_table")
    def on_channel_selected(self, event: DataTable.RowSelected) -> None:
        """Handle channel selection."""
        channel_id = event.row_key.value
        # Could show a context menu or details here
        self.notify(f"Selected channel: {channel_id}", timeout=1)


class VideosTab(VerticalScroll):
    """Tab for browsing videos and summaries."""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Label("Recent Videos & Summaries", classes="section-title")
        yield Label("Use ↑↓ arrows to navigate, press 's' to view summary", classes="hint")
        with Horizontal(classes="button-row"):
            yield Button("Refresh", id="refresh_videos_btn", variant="primary")
            yield Button("View Summary", id="view_summary_btn", variant="success")
        yield DataTable(id="videos_table")

    def on_mount(self) -> None:
        """Set up the videos table when mounted."""
        table = self.query_one("#videos_table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Title", "Channel", "Published", "Has Summary")
        self.refresh_videos()

    def refresh_videos(self) -> None:
        """Refresh the videos list."""
        table = self.query_one("#videos_table", DataTable)
        table.clear()

        videos = self.db.get_recent_videos(limit=50)
        for video in videos:
            has_summary = "✓" if video.summary else "✗"
            # Truncate long titles
            title = video.title[:60] + "..." if len(video.title) > 60 else video.title
            table.add_row(
                title,
                video.channel.channel_name,
                video.published_at.strftime("%Y-%m-%d"),
                has_summary,
                key=str(video.id),
            )

    @on(Button.Pressed, "#refresh_videos_btn")
    def on_refresh_pressed(self) -> None:
        """Handle refresh button press."""
        self.refresh_videos()
        self.notify("Videos refreshed", timeout=1)

    @on(Button.Pressed, "#view_summary_btn")
    def on_view_summary_pressed(self) -> None:
        """Handle view summary button press."""
        table = self.query_one("#videos_table", DataTable)
        if table.cursor_row is not None:
            try:
                rows = list(table.rows.keys())
                if table.cursor_row < len(rows):
                    row_key = rows[table.cursor_row]
                    video_id = int(row_key.value)
                    self.show_video_summary(video_id)
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")
        else:
            self.notify("Please select a video first", severity="warning")

    def show_video_summary(self, video_id: int) -> None:
        """Display summary for a video."""
        with self.db.get_session() as session:
            # Eagerly load relationships before closing session
            video = (
                session.query(Video)
                .options(joinedload(Video.channel), joinedload(Video.summary))
                .filter_by(id=video_id)
                .first()
            )

            if not video:
                self.notify("Video not found", severity="error")
                return

            # Check if summary exists before expunging
            has_summary = video.summary is not None

            if has_summary:
                # Access all data we need before expunging
                title = video.title
                channel_name = video.channel.channel_name
                published = video.published_at.strftime('%Y-%m-%d')
                url = video.url
                summary_text = video.summary.summary_text
                key_points = video.summary.get_key_points()

                # Now expunge
                session.expunge_all()

                # Push the summary screen
                self.app.push_screen(
                    SummaryScreen(
                        title=title,
                        channel=channel_name,
                        published=published,
                        url=url,
                        summary=summary_text,
                        key_points=key_points
                    )
                )
            else:
                self.notify("No summary available for this video", severity="warning", timeout=3)

    @on(DataTable.RowSelected, "#videos_table")
    def on_video_selected(self, event: DataTable.RowSelected) -> None:
        """Handle video selection - show summary if available."""
        video_id = int(event.row_key.value)
        self.show_video_summary(video_id)

    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "s":
            # Same as clicking View Summary button
            self.on_view_summary_pressed()


class HistoryTab(VerticalScroll):
    """Tab for viewing run history."""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Label("Run History", classes="section-title")
        yield Button("Refresh", id="refresh_history_btn", variant="primary")
        yield DataTable(id="history_table")

    def on_mount(self) -> None:
        """Set up the history table when mounted."""
        table = self.query_one("#history_table", DataTable)
        table.add_columns("Timestamp", "Found", "Processed", "Duration (s)", "Status")
        self.refresh_history()

    def refresh_history(self) -> None:
        """Refresh the run history."""
        table = self.query_one("#history_table", DataTable)
        table.clear()

        history = self.db.get_run_history(limit=30)
        for run in history:
            status = "✓ Success" if run.success else "✗ Failed"
            duration = str(run.duration_seconds) if run.duration_seconds else "N/A"
            table.add_row(
                run.run_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                str(run.videos_found),
                str(run.videos_processed),
                duration,
                status,
                key=str(run.id),
            )

    @on(Button.Pressed, "#refresh_history_btn")
    def on_refresh_pressed(self) -> None:
        """Handle refresh button press."""
        self.refresh_history()
        self.notify("History refreshed", timeout=1)


class SettingsTab(VerticalScroll):
    """Tab for viewing settings."""

    def __init__(self):
        super().__init__()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Label("Configuration", classes="section-title")

        config = get_config()
        config_dict = config.to_dict()

        table = Table(show_header=True, box=None)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="yellow")

        for key, value in config_dict.items():
            # Format keys nicely
            display_key = key.replace("_", " ").title()
            table.add_row(display_key, str(value))

        yield Static(table)


class MainScreen(Screen):
    """Main application screen."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "run_check", "Run Check"),
    ]

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()

        with Container():
            yield Label("YouTube Transcript Summarizer", classes="app-title")
            yield StatsPanel(self.db)

            with TabbedContent():
                with TabPane("Channels", id="channels_tab"):
                    yield ChannelsTab(self.db)

                with TabPane("Videos", id="videos_tab"):
                    yield VideosTab(self.db)

                with TabPane("History", id="history_tab"):
                    yield HistoryTab(self.db)

                with TabPane("Settings", id="settings_tab"):
                    yield SettingsTab()

        yield Footer()

    def action_run_check(self) -> None:
        """Run a manual check for new videos."""
        self.notify("Running check for new videos...", severity="information")
        # This would trigger the scheduler's check_and_process function
        # For now, just show a notification
        self.notify(
            "Manual run feature - use 'ytsum run' command from terminal",
            severity="information",
            timeout=5,
        )


class YTSumApp(App):
    """Main TUI application for ytsum."""

    CSS = """
    .app-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding: 1;
    }

    .section-title {
        text-style: bold;
        color: $primary;
        padding: 1 0;
    }

    .hint {
        color: $text-muted;
        padding: 0 0 1 0;
        text-style: italic;
    }

    .input-group {
        height: auto;
        padding: 1 0;
    }

    .button-row {
        height: auto;
        padding: 1 0;
    }

    Input {
        width: 3fr;
    }

    Button {
        width: 1fr;
        margin-left: 1;
    }

    DataTable {
        height: 1fr;
    }

    StatsPanel {
        padding: 1;
        border: solid $primary;
        margin: 1;
    }

    SummaryScreen {
        align: center middle;
    }

    #summary_container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }

    #summary_container VerticalScroll {
        width: 100%;
        height: 1fr;
        margin-bottom: 1;
    }

    #summary_markdown {
        padding: 1;
    }

    #close_btn {
        width: 20;
        dock: bottom;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
    ]

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def on_mount(self) -> None:
        """Set up the app when mounted."""
        self.title = "ytsum - YouTube Transcript Summarizer"
        self.sub_title = "Manage channels and view summaries"
        self.push_screen(MainScreen(self.db))

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark


def run_tui(db: Optional[Database] = None):
    """Run the TUI application.

    Args:
        db: Database instance. If None, creates a new one.
    """
    if db is None:
        db = Database()

    app = YTSumApp(db)
    app.run()
