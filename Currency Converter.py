#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Currency Converter
==================
Автор: Литовкина Мария Александровна

Приложение для конвертации валют с использованием API exchangerate-api.com.
Сохраняет историю операций, поддерживает валидацию ввода и актуальные курсы.

Примеры использования:
    • Конвертация 100 USD в EUR → ~92–94 EUR
    • Конвертация 5000 RUB в USD → ~54–56 USD
    • Валидация: отрицательные числа и нечисловые значения → ошибка

Установка:
    1. pip install -r requirements.txt
    2. python currency_converter.py

API-ключ:
    Получите на https://www.exchangerate-api.com/ и укажите в API_KEY ниже.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import os
import logging
import threading
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

# ==================== КОНФИГУРАЦИЯ ====================
API_KEY = "ВАШ_API_КЛЮЧ"  # 🔑 Замените на ваш ключ от exchangerate-api.com
BASE_URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/USD"
HISTORY_FILE = Path.home() / ".currency_converter" / "conversion_history.json"
MAX_HISTORY_ENTRIES = 100

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(Path.home() / ".currency_converter" / "app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Дефолтные курсы (fallback при ошибке API)
DEFAULT_RATES = {
    "USD": 1.0, "EUR": 0.92, "RUB": 90.5, "GBP": 0.78,
    "JPY": 150.0, "CNY": 7.2, "CAD": 1.35
}


class CurrencyConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Currency Converter")
        self.root.geometry("800x550")
        self.root.minsize(700, 450)

        # Настройка адаптивности окна
        self.root.rowconfigure(2, weight=1)
        self.root.columnconfigure(0, weight=1)

        self.currencies = ["USD", "EUR", "RUB", "GBP", "JPY", "CNY", "CAD"]
        self.rates = DEFAULT_RATES.copy()

        self.create_widgets()
        self.load_history()
        
        # Загрузка курсов в фоне, чтобы не блокировать UI
        threading.Thread(target=self.fetch_exchange_rates, daemon=True).start()

    def create_widgets(self):
        """Создание элементов интерфейса"""
        # === Верхняя панель ===
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), columnspan=4)

        # Выбор валют
        ttk.Label(top_frame, text="Из:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.from_currency = ttk.Combobox(top_frame, values=self.currencies, state="readonly", width=10)
        self.from_currency.set("USD")
        self.from_currency.grid(row=0, column=1, padx=5)

        ttk.Label(top_frame, text="В:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.to_currency = ttk.Combobox(top_frame, values=self.currencies, state="readonly", width=10)
        self.to_currency.set("EUR")
        self.to_currency.grid(row=0, column=3, padx=5)

        # Ввод суммы
        ttk.Label(top_frame, text="Сумма:").grid(row=1, column=0, sticky=tk.W, pady=10, padx=5)
        self.amount_entry = ttk.Entry(top_frame, width=15)
        self.amount_entry.grid(row=1, column=1, pady=10, padx=5)
        self.amount_entry.bind('<Return>', lambda e: self.convert_currency())  # Горячая клавиша Enter

        # Кнопка конвертации
        self.convert_btn = ttk.Button(top_frame, text="Конвертировать", command=self.convert_currency)
        self.convert_btn.grid(row=1, column=2, pady=10, padx=10)

        # Статус-бар
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=3, column=0, columnspan=4, sticky=(tk.W, tk.E), padx=5, pady=2)

        # === Таблица истории ===
        tree_frame = ttk.Frame(self.root)
        tree_frame.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=5)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.history_tree = ttk.Treeview(
            tree_frame,
            columns=("date", "from_amount", "from_curr", "to_amount", "to_curr", "rate"),
            show="headings",
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.history_tree.yview)

        # Заголовки колонок
        headers = [
            ("date", "Дата", 130),
            ("from_amount", "Сумма", 80),
            ("from_curr", "Из", 60),
            ("to_amount", "Результат", 90),
            ("to_curr", "В", 60),
            ("rate", "Курс", 90)
        ]
        for col_id, text, width in headers:
            self.history_tree.heading(col_id, text=text)
            self.history_tree.column(col_id, width=width, minwidth=50)

        self.history_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Кнопка очистки истории
        clear_btn = ttk.Button(self.root, text="Очистить историю", command=self.clear_history)
        clear_btn.grid(row=1, column=3, sticky=tk.E, padx=10, pady=5)

    def fetch_exchange_rates(self):
        """Получение актуальных курсов с exchangerate-api.com"""
        self.status_var.set("Загрузка курсов валют...")
        self.convert_btn.state(['disabled'])
        
        try:
            if API_KEY == "ВАШ_API_КЛЮЧ":
                logging.warning("API-ключ не установлен! Используются дефолтные курсы.")
                self.status_var.set("⚠️ Укажите API-ключ для актуальных курсов")
                return

            response = requests.get(BASE_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("result") == "success" and "conversion_rates" in data:
                # Фильтруем только нужные валюты
                api_rates = data["conversion_rates"]
                self.rates = {
                    curr: api_rates.get(curr, DEFAULT_RATES.get(curr))
                    for curr in self.currencies
                }
                self.rates["USD"] = 1.0  # Гарантируем наличие базовой валюты
                logging.info("Курсы валют успешно обновлены")
                self.status_var.set(f"✅ Курсы обновлены: {datetime.now().strftime('%H:%M')}")
            else:
                raise ValueError(f"API вернул ошибку: {data.get('error-type', 'unknown')}")

        except requests.RequestException as e:
            logging.warning(f"Ошибка сети: {e}")
            self.status_var.set("⚠️ Ошибка сети, используются дефолтные курсы")
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка парсинга JSON: {e}")
            self.status_var.set("⚠️ Ошибка обработки ответа")
        except Exception as e:
            logging.error(f"Непредвиденная ошибка: {e}")
            self.status_var.set("⚠️ Ошибка загрузки курсов")
        finally:
            self.convert_btn.state(['!disabled'])

    def load_history(self):
        """Загрузка истории из файла"""
        if not HISTORY_FILE.exists():
            return
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                for item in history:
                    self._add_to_tree(item)
            logging.info(f"Загружено {len(history)} записей истории")
        except Exception as e:
            logging.error(f"Ошибка загрузки истории: {e}")
            messagebox.showwarning("Предупреждение", f"Не удалось загрузить историю: {e}")

    def save_history(self, conversion: dict):
        """Сохранение одной записи в историю"""
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            history = []
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            
            history.append(conversion)
            # Ограничиваем размер истории
            if len(history) > MAX_HISTORY_ENTRIES:
                history = history[-MAX_HISTORY_ENTRIES:]
            
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Ошибка сохранения истории: {e}")

    def clear_history(self):
        """Очистка истории с подтверждением"""
        if messagebox.askyesno("Подтверждение", "Удалить всю историю конвертаций?"):
            try:
                if HISTORY_FILE.exists():
                    HISTORY_FILE.unlink()
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                logging.info("История очищена")
                self.status_var.set("🗑️ История очищена")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось очистить историю: {e}")

    def _format_decimal(self, value: float, decimals: int = 2) -> str:
        """Форматирование числа с точной округлением через Decimal"""
        d = Decimal(str(value)).quantize(Decimal(10) ** -decimals, rounding=ROUND_HALF_UP)
        return str(d)

    def _add_to_tree(self, item: dict):
        """Добавление записи в таблицу"""
        self.history_tree.insert("", "end", values=(
            item["date"],
            self._format_decimal(item["from_amount"]),
            item["from_curr"],
            self._format_decimal(item["to_amount"]),
            item["to_curr"],
            self._format_decimal(item["rate"], 4)
        ))

    def convert_currency(self):
        """Основная логика конвертации"""
        try:
            # Валидация суммы
            amount_str = self.amount_entry.get().strip()
            if not amount_str:
                raise ValueError("Пустое значение")
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError("Отрицательное или нулевое значение")

            from_curr = self.from_currency.get()
            to_curr = self.to_currency.get()

            if not from_curr or not to_curr:
                raise ValueError("Валюты не выбраны")
            if from_curr not in self.rates or to_curr not in self.rates:
                raise ValueError("Валюта отсутствует в курсах")

            # Расчёт через Decimal для точности
            amount_dec = Decimal(str(amount))
            from_rate = Decimal(str(self.rates[from_curr]))
            to_rate = Decimal(str(self.rates[to_curr]))

            if from_curr == to_curr:
                converted = amount_dec
                rate = Decimal("1.0")
            else:
                # Конвертация: amount * (to_rate / from_rate)
                converted = (amount_dec * to_rate / from_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                rate = (to_rate / from_rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            # Отображение результата
            result = f"{self._format_decimal(amount)} {from_curr} = {converted} {to_curr}\nКурс: {rate}"
            messagebox.showinfo("✅ Результат", result)
            logging.info(f"Конвертация: {amount} {from_curr} → {converted} {to_curr} @ {rate}")

            # Сохранение в историю
            conversion = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "from_amount": float(amount),
                "from_curr": from_curr,
                "to_amount": float(converted),
                "to_curr": to_curr,
                "rate": float(rate)
            }
            self.save_history(conversion)
            self._add_to_tree(conversion)
            self.status_var.set(f"✅ Конвертация выполнена: {from_curr} → {to_curr}")

        except ValueError as e:
            messagebox.showerror("Ошибка ввода", f"Некорректная сумма: {e}\nВведите положительное число.")
            logging.warning(f"Ошибка валидации: {e}")
        except Exception as e:
            logging.error(f"Непредвиденная ошибка: {e}", exc_info=True)
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    # Создаём директорию для логов и истории при старте
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    root = tk.Tk()
    # Иконка (опционально, если есть файл)
    # root.iconbitmap("icon.ico") if os.path.exists("icon.ico") else None
    
    app = CurrencyConverter(root)
    logging.info("Приложение запущено")
    root.mainloop()