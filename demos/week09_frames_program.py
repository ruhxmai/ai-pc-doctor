"""Неделя 9. Программа работы с фреймами: поиск и изменение свойств.

Без аргументов — демонстрационный сценарий; с флагом -i — интерактивный режим.
"""
import sys

import _setup  # noqa: F401

from pcdoctor.frames import FrameSystem
from pcdoctor.frames_cli import repl, run_command
from pcdoctor.knowledge_base import KnowledgeBase

fs = FrameSystem.load(kb=KnowledgeBase.load(), current_year=2026)

if "-i" in sys.argv:
    repl(fs)
    sys.exit()

script = [
    "list storage",
    "find has_moving_parts=да",
    "find класс:heat_source max_temp>=95",
    "find lifetime_left<0",
    "find класс:fault needs_service=нет",
    "find symptoms~bsod",
    "get ssd_samsung_970 typical_lifetime_years",
    "set ssd_samsung_970 typical_lifetime_years 12",
    "del ssd_samsung_970 typical_lifetime_years",
    "set gpu_rtx_3060 current_temp 97",
    "find status=перегрев",
    "new ssd_kingston_a400 ssd Kingston A400 480 ГБ",
    "set ssd_kingston_a400 capacity_gb 480",
    "set ssd_kingston_a400 purchase_year 2025",
    "show ssd_kingston_a400",
    "find класс:storage capacity_gb>=480",
]
for line in script:
    print(f"фреймы> {line}")
    print(run_command(fs, line), end="\n\n")
