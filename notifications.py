# -*- coding: utf-8 -*-
"""Фоновая проверка напоминаний и показ уведомлений."""

import queue
import threading

from database import ReminderDatabase

CHECK_INTERVAL = 10  # секунд между проверками базы


class NotificationChecker(threading.Thread):
    """Фоновый поток: каждые CHECK_INTERVAL секунд проверяет базу.

    Сработавшие напоминания кладёт в очередь, из которой их забирает
    главный поток и показывает окно-уведомление. Работает, даже если
    окно программы свернуто.
    """

    def __init__(self, db: ReminderDatabase):
        super().__init__(daemon=True)  # поток закроется вместе с программой
        self.db = db
        self.queue = queue.Queue()
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            try:
                for reminder in self.db.pop_due():
                    self.queue.put(reminder)
            except Exception as e:  # сеть/база не должны ронять программу
                print(f"Ошибка проверки напоминаний: {e}")
            self._stop_event.wait(CHECK_INTERVAL)

    def stop(self):
        self._stop_event.set()
