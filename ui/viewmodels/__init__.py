"""ViewModels — pure-Python prezentační logika pro UI vrstvu.

Žádný PyQt6 import. ViewModel drží stav (data/error/loading) a deleguje
načtení na injectovanou query. Page widget čte properties a renderuje.
"""

from ui.viewmodels.dashboard_vm import DashboardViewModel

__all__ = ["DashboardViewModel"]
