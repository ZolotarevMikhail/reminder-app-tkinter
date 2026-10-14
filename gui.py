# -*- coding: utf-8 -*-
"""Графический интерфейс напоминалки (tkinter).

Главное окно: форма добавления, таблица с цветами по статусу и
уведомления, приходящие из фонового потока notifications.
"""

import queue
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox

from database import ReminderDatabase, ALL_STATUSES
from notifications import NotificationChecker

DATE_FORMAT = "%Y-%m-%d %H:%M"

# Заголовок окна приложения (используется и в диалогах)
APP_TITLE = "Напоминалка"

# Подсказка внизу окна, когда строка ещё не выбрана
HINT_NO_SELECTION = ("Кликните по строке в списке, "
                     "затем нажмите кнопку действия")

# Цвет выделенной строки и «тихой» подсказки
HINT_COLOR = "#888888"
HINT_SELECTED_COLOR = "#333333"
HINT_ERROR_COLOR = "#c0392b"

# Быстрая установка времени: подпись кнопки -> сколько минут добавить
QUICK_BUTTONS = [("Через 1 мин", 1), ("Через 5 мин", 5), ("Через 15 мин", 15),
                 ("Через 30 мин", 30), ("Через 1 час", 60)]

# Варианты повтора напоминания
REPEAT_OPTIONS = ["Нет", "Каждый день", "Каждый месяц"]

# Цвет строк таблицы по статусу
ROW_COLORS = {
    "Готово": "#dff2df",
    "Просрочено": "#fadbd8",
    "Отменено": "#e6e6e6",
}

# Колонки таблицы: (ключ, заголовок, ширина)
COLUMNS = (
    ("id", "ID", 40),
    ("title", "Заголовок", 150),
    ("description", "Описание", 190),
    ("remind_at", "Дата/Время", 115),
    ("status", "Статус", 90),
    ("repeat", "Повтор", 85),
    ("created_at", "Создано", 115),
)


class ReminderApp:
    """Главное окно приложения."""

    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.root.title("Напоминалка Windows 11")
        self.root.geometry("940x660")
        self.root.minsize(780, 540)

        self.db = ReminderDatabase()
        # Пропущенные за время выключения напоминания помечаем просроченными
        self.db.mark_overdue()

        self.checker = NotificationChecker(self.db)
        self.checker.start()

        self._build_ui()
        self.refresh()

        self.root.after(500, self._poll_notifications)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- построение интерфейса ----------

    def _build_ui(self):
        """Собирает все блоки главного окна."""
        tk.Label(self.root, text=APP_TITLE,
                 font=("Arial", 16, "bold")).pack(pady=(10, 4))
        self._build_form()
        self._build_filter_row()
        self._build_table()
        self._build_actions()

    def _build_form(self):
        """Форма добавления нового напоминания."""
        form = tk.LabelFrame(self.root, text=" Добавить новое напоминание ")
        form.pack(fill="x", padx=12, pady=6)

        tk.Label(form, text="Заголовок:").grid(row=0, column=0, sticky="e",
                                               padx=8, pady=4)
        self.entry_title = tk.Entry(form, width=60)
        self.entry_title.grid(row=0, column=1, sticky="we", padx=8, pady=4)

        tk.Label(form, text="Описание:").grid(row=1, column=0, sticky="e",
                                              padx=8, pady=4)
        self.entry_desc = tk.Entry(form, width=60)
        self.entry_desc.grid(row=1, column=1, sticky="we", padx=8, pady=4)

        tk.Label(form, text="Дата и время:").grid(row=2, column=0, sticky="e",
                                                  padx=8, pady=4)
        date_row = tk.Frame(form)
        date_row.grid(row=2, column=1, sticky="we", padx=8, pady=4)
        self.entry_date = tk.Entry(date_row, width=20)
        self.entry_date.pack(side="left")
        self.entry_date.insert(0, datetime.now().strftime(DATE_FORMAT))
        for label, minutes in QUICK_BUTTONS:
            tk.Button(date_row, text=label,
                      command=lambda m=minutes: self._set_quick_time(m)
                      ).pack(side="left", padx=4)

        tk.Label(form, text="Повторять:").grid(row=3, column=0, sticky="e",
                                               padx=8, pady=4)
        # Нативное меню (надёжнее выпадающего списка на Mac)
        self.repeat_var = tk.StringVar(value="Нет")
        tk.OptionMenu(form, self.repeat_var, *REPEAT_OPTIONS).grid(
            row=3, column=1, sticky="w", padx=8, pady=4)

        btn_row = tk.Frame(form)
        btn_row.grid(row=4, column=0, columnspan=2, pady=6)
        tk.Button(btn_row, text="Добавить напоминание",
                  command=self.add_reminder).pack(side="left", padx=6)
        tk.Button(btn_row, text="Тест уведомления",
                  command=self.test_notification).pack(side="left", padx=6)

        form.columnconfigure(1, weight=1)

    def _build_filter_row(self):
        """Строка фильтра по статусу и кнопки обновления."""
        filter_row = tk.Frame(self.root)
        filter_row.pack(fill="x", padx=12, pady=4)
        tk.Label(filter_row, text="Фильтр по статусу:").pack(side="left")
        self.filter_var = tk.StringVar(value="Все")
        tk.OptionMenu(filter_row, self.filter_var, "Все", *ALL_STATUSES,
                      command=lambda v: self.refresh()).pack(side="left",
                                                             padx=6)
        tk.Button(filter_row, text="Обновить",
                  command=self.refresh).pack(side="left", padx=6)
        self.label_counts = tk.Label(filter_row, text="")
        self.label_counts.pack(side="right")

    def _build_table(self):
        """Таблица напоминаний (с прокруткой и цветами статусов)."""
        table = tk.LabelFrame(self.root, text=" Список напоминаний ")
        table.pack(fill="both", expand=True, padx=12, pady=6)

        column_names = [col for col, _, _ in COLUMNS]
        self.tree = ttk.Treeview(table, columns=column_names,
                                 show="headings")
        for col, header, width in COLUMNS:
            self.tree.heading(col, text=header)
            anchor = "w" if col in ("title", "description") else "center"
            self.tree.column(col, width=width, anchor=anchor)
        scroll = ttk.Scrollbar(table, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, pady=(4, 0))
        scroll.pack(side="right", fill="y")

        for status, color in ROW_COLORS.items():
            self.tree.tag_configure(status, background=color)

        # Подсказка и строка «что выбрано» — видимый отклик на клики
        self.label_selected = tk.Label(self.root, text=HINT_NO_SELECTION,
                                       fg=HINT_COLOR)
        self.label_selected.pack(pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_actions(self):
        """Ряд кнопок действий над выбранной строкой."""
        actions = tk.Frame(self.root)
        actions.pack(pady=6)
        tk.Button(actions, text="Отметить «Готово»", width=20,
                  command=lambda: self._change_status(
                      "Готово")).pack(side="left", padx=6)
        tk.Button(actions, text="Отметить «Отменено»", width=20,
                  command=lambda: self._change_status(
                      "Отменено")).pack(side="left", padx=6)
        tk.Button(actions, text="Удалить напоминание", width=20,
                  command=self.delete_reminder).pack(side="left", padx=6)

    # ---------- действия ----------

    def _set_quick_time(self, minutes):
        """Кнопки «Через 5 мин» и т.п. подставляют время в поле."""
        moment = datetime.now() + timedelta(minutes=minutes)
        self.entry_date.delete(0, tk.END)
        self.entry_date.insert(0, moment.strftime(DATE_FORMAT))

    def add_reminder(self):
        title = self.entry_title.get().strip()
        description = self.entry_desc.get().strip()
        date_text = self.entry_date.get().strip()
        if not title:
            messagebox.showwarning(APP_TITLE, "Введите заголовок.")
            return
        try:
            moment = datetime.strptime(date_text, DATE_FORMAT)
        except ValueError:
            messagebox.showwarning(
                APP_TITLE,
                "Неверный формат даты. Нужен: ГГГГ-ММ-ДД ЧЧ:ММ\n"
                "Пример: 2026-09-27 15:30")
            return
        self.db.add(title, description, moment.strftime(DATE_FORMAT),
                    self.repeat_var.get())
        self.entry_title.delete(0, tk.END)
        self.entry_desc.delete(0, tk.END)
        self.refresh()

    def _selected_id(self):
        selected = self.tree.selection()
        if not selected:
            # Не диалог, а надпись в окне — чтобы сообщение точно было видно
            self.label_selected.config(
                text="Сначала выберите строку в списке — кликните по ней",
                fg=HINT_ERROR_COLOR)
            return None
        return int(self.tree.item(selected[0])["values"][0])

    def _on_select(self, event=None):
        """Делает выделение видимым: у выбранной строки цвет меняется."""
        selected = set(self.tree.selection())
        for iid in self.tree.get_children():
            status = self.tree.set(iid, "status")
            self.tree.item(
                iid, tags=() if iid in selected else (status,))
        if selected:
            values = self.tree.item(list(selected)[0])["values"]
            self.label_selected.config(
                text=f"Выбрано: №{values[0]} «{values[1]}»",
                fg=HINT_SELECTED_COLOR)
        else:
            self.label_selected.config(text=HINT_NO_SELECTION,
                                       fg=HINT_COLOR)

    def _change_status(self, status):
        reminder_id = self._selected_id()
        if reminder_id is not None:
            self.db.set_status(reminder_id, status)
            self.refresh()

    def delete_reminder(self):
        reminder_id = self._selected_id()
        if reminder_id is None:
            return
        if messagebox.askyesno(APP_TITLE,
                               "Удалить выбранное напоминание?"):
            self.db.delete(reminder_id)
            self.refresh()

    def test_notification(self):
        self.show_popup({"title": "Тест уведомления",
                         "description": "Если вы видите это окно — "
                                        "уведомления работают.",
                         "remind_at":
                             datetime.now().strftime(DATE_FORMAT)})

    # ---------- таблица и уведомления ----------

    def refresh(self):
        """Перечитывает базу и перерисовывает таблицу и счётчики."""
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self.db.get_all(self.filter_var.get()):
            self.tree.insert("", "end", values=(
                item["id"], item["title"], item["description"],
                item["remind_at"], item["status"],
                item.get("repeat", "Нет"), item["created_at"]),
                tags=(item["status"],))
        counts = self.db.get_counts()
        self.label_counts.config(text=(
            f"Всего: {counts['Всего']} | "
            f"Ожидает: {counts['Ожидает']} | "
            f"Готово: {counts['Готово']} | "
            f"Просрочено: {counts['Просрочено']}"))

    def _poll_notifications(self):
        """Забирает сработавшие напоминания из очереди и показывает окна."""
        try:
            while True:
                self.show_popup(self.checker.queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(500, self._poll_notifications)

    def show_popup(self, reminder):
        """Окно уведомления поверх всех окон."""
        popup = tk.Toplevel(self.root)
        popup.title("Напоминание")
        popup.attributes("-topmost", True)
        popup.geometry(
            f"+{self.root.winfo_x() + 250}+{self.root.winfo_y() + 150}")
        tk.Label(popup, text="⏰ " + reminder["title"],
                 font=("Arial", 13, "bold")).pack(padx=20, pady=(14, 6))
        if reminder.get("description"):
            tk.Label(popup, text=reminder["description"],
                     wraplength=320).pack(padx=20, pady=4)
        tk.Label(popup, text="Время: " + reminder["remind_at"],
                 fg="#666666").pack(padx=20, pady=4)
        tk.Button(popup, text="Отметить выполненным", width=22,
                  command=popup.destroy).pack(pady=12)

    def _on_close(self):
        self.checker.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
