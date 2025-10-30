"""Command-line interface for ytsum."""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from . import __version__
from .config import Config, get_config, set_config
from .database import Database
from .tui import run_tui

console = Console()


def setup_logging(verbose: bool = False):
    """Set up logging configuration.

    Args:
        verbose: Enable verbose (DEBUG) logging.
    """
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


def cmd_init(args):
    """Initialize ytsum configuration."""
    console.print("[bold cyan]Initializing ytsum...[/bold cyan]")

    # Create .env.example in current directory
    env_example = Path.cwd() / ".env.example"
    Config.create_example_env(env_example)
    console.print(f"[green]✓[/green] Created {env_example}")

    # Create config directory
    config_dir = Path.home() / ".config" / "ytsum"
    config_dir.mkdir(parents=True, exist_ok=True)

    env_file = config_dir / ".env"
    if not env_file.exists():
        Config.create_example_env(env_file)
        console.print(f"[green]✓[/green] Created {env_file}")
        console.print(
            "\n[yellow]Please edit the .env file and add your API keys:[/yellow]"
        )
        console.print(f"  {env_file}")
    else:
        console.print(f"[yellow]⚠[/yellow] Config file already exists: {env_file}")

    # Initialize database
    db = Database()
    console.print(f"[green]✓[/green] Initialized database at {db.db_path}")

    console.print("\n[bold green]Setup complete![/bold green]")
    console.print("\nNext steps:")
    console.print("1. Edit your .env file with API keys")
    console.print("2. Run 'ytsum ui' to start the interface")
    console.print("3. Add channels to follow")
    console.print("4. Run 'ytsum run' to process videos")


def cmd_ui(args):
    """Launch the TUI."""
    config = get_config()

    # Validate config
    is_valid, errors = config.validate()
    if not is_valid:
        console.print("[bold red]Configuration errors:[/bold red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        console.print("\nRun 'ytsum init' to set up configuration.")
        sys.exit(1)

    db = Database(config.database_path)
    run_tui(db)


def cmd_run(args):
    """Run the check and summarization process."""
    from .scheduler import check_and_process

    config = get_config()

    # Validate config
    is_valid, errors = config.validate()
    if not is_valid:
        console.print("[bold red]Configuration errors:[/bold red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        sys.exit(1)

    console.print("[bold cyan]Starting video check and processing...[/bold cyan]")

    db = Database(config.database_path)

    try:
        result = check_and_process(db, config)

        console.print("\n[bold green]Processing complete![/bold green]")
        console.print(f"Videos found: {result['videos_found']}")
        console.print(f"Videos processed: {result['videos_processed']}")
        console.print(f"Errors: {len(result['errors'])}")

        if result["errors"]:
            console.print("\n[yellow]Errors encountered:[/yellow]")
            for error in result["errors"]:
                console.print(f"  [red]✗[/red] {error}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


def cmd_status(args):
    """Show current status and statistics."""
    config = get_config()
    db = Database(config.database_path)

    stats = db.get_stats()

    # Create stats table
    table = Table(title="ytsum Status", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Channels", str(stats["total_channels"]))
    table.add_row("Total Videos", str(stats["total_videos"]))
    table.add_row("With Transcripts", str(stats["videos_with_transcripts"]))
    table.add_row("With Summaries", str(stats["videos_with_summaries"]))
    table.add_row("Total Runs", str(stats["total_runs"]))

    if stats["last_run"]:
        last_run_time = stats["last_run"].run_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        last_run_status = "Success" if stats["last_run"].success else "Failed"
        table.add_row("Last Run", last_run_time)
        table.add_row("Last Run Status", last_run_status)

    console.print(table)

    # Show pending work
    videos_without_transcripts = len(db.get_videos_without_transcripts())
    videos_without_summaries = len(db.get_videos_without_summaries())

    if videos_without_transcripts or videos_without_summaries:
        console.print("\n[yellow]Pending Work:[/yellow]")
        if videos_without_transcripts:
            console.print(f"  {videos_without_transcripts} videos need transcripts")
        if videos_without_summaries:
            console.print(f"  {videos_without_summaries} videos need summaries")


def cmd_config(args):
    """Show current configuration."""
    config = get_config()

    table = Table(title="Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")

    config_dict = config.to_dict()
    for key, value in config_dict.items():
        # Format keys nicely
        display_key = key.replace("_", " ").title()
        table.add_row(display_key, str(value))

    console.print(table)

    # Validate
    is_valid, errors = config.validate()
    if not is_valid:
        console.print("\n[bold red]Configuration Issues:[/bold red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
    else:
        console.print("\n[bold green]✓ Configuration is valid[/bold green]")


def cmd_schedule(args):
    """Run the scheduler daemon (for systemd service)."""
    from .scheduler import run_scheduler

    config = get_config()

    # Validate config
    is_valid, errors = config.validate()
    if not is_valid:
        console.print("[bold red]Configuration errors:[/bold red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        sys.exit(1)

    console.print(
        f"[bold cyan]Starting scheduler (daily at {config.check_schedule})...[/bold cyan]"
    )
    console.print("Press Ctrl+C to stop")

    db = Database(config.database_path)

    try:
        run_scheduler(db, config)
    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduler stopped[/yellow]")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="YouTube Transcript Summarizer - Automated video summarization with AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", action="version", version=f"ytsum {__version__}")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    parser_init = subparsers.add_parser("init", help="Initialize ytsum configuration")

    # ui command
    parser_ui = subparsers.add_parser("ui", help="Launch the TUI interface")

    # run command
    parser_run = subparsers.add_parser(
        "run", help="Run check and summarization process once"
    )

    # status command
    parser_status = subparsers.add_parser("status", help="Show current status")

    # config command
    parser_config = subparsers.add_parser("config", help="Show configuration")

    # schedule command
    parser_schedule = subparsers.add_parser(
        "schedule", help="Run scheduler daemon (for systemd service)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Load config (except for init command)
    if args.command != "init":
        config = Config()
        set_config(config)

    # Execute command
    if args.command == "init":
        cmd_init(args)
    elif args.command == "ui":
        cmd_ui(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
