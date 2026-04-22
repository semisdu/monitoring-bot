import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.scheduler import MonitoringScheduler
from telegram.ext import Application
from config.settings import TELEGRAM_TOKEN

def test_scheduler_creation():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    scheduler = MonitoringScheduler(app)
    assert scheduler is not None
    assert scheduler.application == app
