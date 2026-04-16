"""ViewModels — pure-Python prezentační logika pro UI vrstvu.

Žádný PyQt6 import. ViewModel drží stav (data/error/loading) a deleguje
načtení na injectovanou query. Page widget čte properties a renderuje.
"""

from ui.viewmodels.chart_of_accounts_vm import ChartOfAccountsViewModel
from ui.viewmodels.dashboard_vm import DashboardViewModel
from ui.viewmodels.doklady_list_vm import DokladyListViewModel

__all__ = [
    "ChartOfAccountsViewModel",
    "DashboardViewModel",
    "DokladyListViewModel",
]
