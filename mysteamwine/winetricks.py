from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .bottle import Bottle, ensure_bottle_dirs
from .runtime import check_executable, run_logged


def run_winetricks(
    *,
    bottle: Bottle,
    winetricks_path: Path,
    verbs: Sequence[str],
    log_name: str = "winetricks.log",
    unattended: bool = True,
) -> tuple[int, str]:
    ensure_bottle_dirs(bottle)
    check_executable(winetricks_path, "winetricks")

    command = [str(winetricks_path)]
    if unattended:
        command.append("-q")
    command.extend(verbs)

    return run_logged(
        cmd=command,
        env={"WINEPREFIX": str(bottle.prefix), "WINEDEBUG": "-all"},
        log_file=bottle.logs / log_name,
    )


# Chain of Responsibility Design Pattern

from abc import ABC, abstractmethod


# Handler
class LeaveHandler(ABC):
    def __init__(self):
        self.next_handler = None

    def set_next_handler(self, next_handler):
        self.next_handler = next_handler

    @abstractmethod
    def approve_leave(self, days):
        pass


# Concrete Handler 1
class TeamLead(LeaveHandler):
    def approve_leave(self, days):
        if days <= 2:
            print(f"TeamLead approved {days} days of leave")
        elif self.next_handler is not None:
            self.next_handler.approve_leave(days)
        else:
            print("Leave request cant be approved")


# Concrete Handler 2
class Manager(LeaveHandler):
    def approve_leave(self, days):
        if days <= 5:
            print(f"Manager approved {days} days of leave")
        elif self.next_handler is not None:
            self.next_handler.approve_leave(days)
        else:
            print("Leave request cant be approved")


# Client
class Client:
    def __init__(self):
        self.team_lead = TeamLead()
        self.manager = Manager()

        # Creating the chain
        self.team_lead.set_next_handler(self.manager)

    def send_request(self, days):
        self.team_lead.approve_leave(days)


# Main
if __name__ == "__main__":
    client = Client()

    client.send_request(1)
    client.send_request(4)
    client.send_request(7)