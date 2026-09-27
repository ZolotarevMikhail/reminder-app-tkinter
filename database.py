# -*- coding: utf-8 -*-
"""Работа с базой данных SQLite."""

import sqlite3
from datetime import datetime, timedelta

DB_FILE = "reminders.db"

# Возможные статусы напоминания
STATUS_WAITING = "Ожидает"
STATUS_DONE = "Готово"
STATUS_OVERDUE = "Просрочено"
STATUS_CANCELED = "Отменено"
ALL_STATUSES = [STATUS_WAITING, STATUS_DONE, STATUS_OVERDUE, STATUS_CANCELED]


class ReminderDatabase:
    """Класс для работы с базой данных напоминаний."""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self._create_tables()

    def _connect(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """Создаёт таблицы, если их ещё нет."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    remind_at   TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'Ожидает',
                    created_at  TEXT NOT NULL
                )
            """)
            # Добавляем колонку «Повтор» в старые базы (если её ещё нет)
            try:
                conn.execute(
                    "ALTER TABLE reminders ADD COLUMN repeat TEXT NOT NULL DEFAULT 'Нет'"
                )
            except sqlite3.OperationalError:
                pass  # колонка уже есть

    def add(self, title, description, remind_at, repeat="Нет"):
        """Добавляет новое напоминание. Возвращает его id."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO reminders (title, description, remind_at, status, created_at, repeat) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (title, description, remind_at, STATUS_WAITING, now, repeat),
            )
            return cur.lastrowid

    def delete(self, reminder_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))

    def set_status(self, reminder_id, status):
        with self._connect() as conn:
            conn.execute(
                "UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id)
            )

    def get_all(self, status_filter="Все"):
        """Возвращает список напоминаний, при желании отфильтрованный по статусу."""
        with self._connect() as conn:
            if status_filter == "Все":
                rows = conn.execute(
                    "SELECT * FROM reminders ORDER BY remind_at, id"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE status = ? ORDER BY remind_at, id",
                    (status_filter,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_counts(self):
        """Считает напоминания по статусам. Возвращает словарь."""
        counts = {"Всего": 0}
        for status in ALL_STATUSES:
            counts[status] = 0
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM reminders GROUP BY status"
            ):
                counts[row["status"]] = row["cnt"]
                counts["Всего"] += row["cnt"]
        return counts

    def mark_overdue(self):
        """Переводит все просроченные 'Ожидает' в статус 'Просрочено'."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as conn:
            conn.execute(
                "UPDATE reminders SET status = ? WHERE status = ? AND remind_at <= ?",
                (STATUS_OVERDUE, STATUS_WAITING, now),
            )

    def pop_due(self):
        """Возвращает напоминания, время которых наступило.

        Разовые переводит в 'Готово' (срабатывают один раз),
        повторяющиеся переносит на следующий день/месяц — и они
        снова становятся 'Ожидает'.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE status = ? AND remind_at <= ?",
                (STATUS_WAITING, now),
            ).fetchall()
            result = [dict(row) for row in rows]
            for row in result:
                repeat = row.get("repeat", "Нет")
                if repeat == "Нет":
                    conn.execute(
                        "UPDATE reminders SET status = ? WHERE id = ?",
                        (STATUS_DONE, row["id"]),
                    )
                else:
                    next_moment = next_occurrence(row["remind_at"], repeat)
                    conn.execute(
                        "UPDATE reminders SET remind_at = ? WHERE id = ?",
                        (next_moment.strftime("%Y-%m-%d %H:%M"), row["id"]),
                    )
        return result


def _add_month(moment):
    """Прибавляет один месяц с учётом разной длины месяцев."""
    month = moment.month % 12 + 1
    year = moment.year + (moment.month == 12)
    day = min(moment.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
                           else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return moment.replace(year=year, month=month, day=day)


def next_occurrence(remind_at, repeat):
    """Вычисляет следующее время срабатывания для повторяющегося напоминания.

    Если пропущено несколько повторов (программа была выключена),
    время перематывается вперёд до ближайшего будущего.
    """
    moment = datetime.strptime(remind_at, "%Y-%m-%d %H:%M")
    now = datetime.now()
    while moment <= now:
        if repeat == "Каждый день":
            moment += timedelta(days=1)
        elif repeat == "Каждый месяц":
            moment = _add_month(moment)
        else:
            break
    return moment