# -*- coding: utf-8 -*-
"""
Напоминалка для Windows 11
Главный файл приложения
"""

import sys

from gui import ReminderApp


def main():
    """Главная функция приложения"""
    try:
        # Создание и запуск приложения
        app = ReminderApp()
        print("Напоминалка запущена успешно!")
        print("Приложение работает в фоновом режиме для уведомлений.")
        app.run()
    except Exception as e:
        print(f"Ошибка при запуске приложения: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()