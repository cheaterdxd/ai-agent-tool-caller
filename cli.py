#!/usr/bin/env python3
"""CLI interface for AI Agent."""

import click
import os
import signal
import subprocess
import sys
from pathlib import Path

PID_FILE = "/tmp/ai-agent.pid"


@click.group()
def cli():
    """AI Agent CLI - Control your autonomous AI agent."""
    pass


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Path to config file')
def start(config):
    """Start the daemon in background."""
    if Path(PID_FILE).exists():
        click.echo("❌ Daemon already running!")
        sys.exit(1)
    
    click.echo("🚀 Starting AI Agent daemon...")
    
    # Start daemon in background
    process = subprocess.Popen(
        [sys.executable, 'daemon.py'],
        stdout=open('logs/daemon.log', 'a'),
        stderr=open('logs/daemon.log', 'a'),
        start_new_session=True
    )
    
    # Save PID
    with open(PID_FILE, 'w') as f:
        f.write(str(process.pid))
    
    click.echo(f"✅ Daemon started (PID: {process.pid})")
    click.echo("📊 Check logs: tail -f logs/daemon.log")


@cli.command()
def stop():
    """Stop the daemon."""
    if not Path(PID_FILE).exists():
        click.echo("❌ Daemon not running!")
        sys.exit(1)
    
    with open(PID_FILE, 'r') as f:
        pid = int(f.read().strip())
    
    click.echo(f"🛑 Stopping daemon (PID: {pid})...")
    
    try:
        os.kill(pid, signal.SIGTERM)
        os.remove(PID_FILE)
        click.echo("✅ Daemon stopped.")
    except ProcessLookupError:
        click.echo("⚠️  Process not found, cleaning up...")
        os.remove(PID_FILE)
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        sys.exit(1)


@cli.command()
def status():
    """Check daemon status."""
    if Path(PID_FILE).exists():
        with open(PID_FILE, 'r') as f:
            pid = f.read().strip()
        click.echo(f"🟢 Daemon is running (PID: {pid})")
        click.echo("📊 Check logs: tail -f logs/daemon.log")
    else:
        click.echo("🔴 Daemon is stopped")


@cli.command()
def restart():
    """Restart the daemon."""
    if Path(PID_FILE).exists():
        ctx = click.get_current_context()
        ctx.invoke(stop)
    
    ctx = click.get_current_context()
    ctx.invoke(start)


@cli.command()
@click.argument('query')
def search(query):
    """Search immediately (requires running daemon)."""
    click.echo(f"🔍 Use Discord to search: {query}")
    click.echo("💡 Or send via Discord bot with: 'search " + query + "'")


@cli.command()
@click.argument('note')
def add(note):
    """Add note to RAG (requires running daemon)."""
    click.echo(f"📝 Use Discord to add note: {note}")
    click.echo("💡 Or send via Discord bot with: 'add " + note + "'")


if __name__ == '__main__':
    cli()
