"""Widgets package — reusable PyQt6 widgety (sidebar, icon loader, atd.)."""

from ui.widgets.icon import load_icon
from ui.widgets.kpi_card import KpiCard
from ui.widgets.sidebar import Sidebar

__all__ = ["KpiCard", "Sidebar", "load_icon"]
