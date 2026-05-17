import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import os
from datetime import datetime

class CurrencyConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Currency Converter")
        self.root.geometry("750x500")

        # Список валют (можно расширить)
        self.currencies = ["USD", "EUR", "RUB", "GBP", "JPY", "CNY", "CAD"]
        
        # Дефолтные курсы на случай ошибки
        self.rates = {
            "USD": 1.0,
            "EUR": 0.92,
            "RUB": 90.5,
            "GBP": 0.78,
            "JPY": 150.0,
            "CNY": 7.2,
            "CAD": 1.35
        }

        # UI элементы
        self.create_widgets()

        # Загрузка истории
        self.load_history()

        # Получение актуальных курсов при запуске
        self.fetch_exchange_rates()

    def create_widgets(self):
        # Рамка для выбора валют и ввода суммы
        frame = ttk.Frame(self.root, padding="10")
        frame.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Выбор исходной валюты
        ttk.Label(frame, text="Из валюты:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.from_currency = ttk.Combobox(frame, values=self.currencies, state="readonly")
        self.from_currency.set("USD")
        self.from_currency.grid(row=0, column=1, pady=5, padx=5)

        # Выбор целевой валюты
        ttk.Label(frame, text="В валюту:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.to_currency = ttk.Combobox(frame, values=self.currencies, state="readonly")
        self.to_currency.set("EUR")
        self.to_currency.grid(row=0, column=3, pady=5, padx=5)

        # Поле ввода суммы
        ttk.Label(frame, text="Сумма:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.amount_entry = ttk.Entry(frame)
        self.amount_entry.grid(row=1, column=1, pady=5, padx=5)

        # Кнопка конвертации
        convert_btn = ttk.Button(frame, text="Конвертировать", command=self.convert_currency)
        convert_btn.grid(row=1, column=2, pady=5, padx=5)

        # Таблица истории с прокруткой
        tree_frame = ttk.Frame(self.root)
        tree_frame.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.history_tree = ttk.Treeview(tree_frame, 
            columns=("date", "from_amount", "from_curr", "to_amount", "to_curr", "rate"), 
            show="headings",
            yscrollcommand=scrollbar.set)
        
        scrollbar.config(command=self.history_tree.yview)
        
        # Настройка колонок
        self.history_tree.heading("date", text="Дата")
        self.history_tree.heading("from_amount", text="Сумма из")
        self.history_tree.heading("from_curr", text="Валюта из")
        self.history_tree.heading("to_amount", text="Сумма в")
        self.history_tree.heading("to_curr", text="Валюта в")
        self.history_tree.heading("rate", text="Курс")
        
        self.history_tree.column("date", width=120)
        self.history_tree.column("from_amount", width=80)
        self.history_tree.column("from_curr", width=60)
        self.history_tree.column("to_amount", width=80)
        self.history_tree.column("to_curr", width=60)
        self.history_tree.column("rate", width=80)
        
        self.history_tree.pack(fill=tk.BOTH, expand=True)

    def fetch_exchange_rates(self):
        """Получение актуальных курсов валют с exchangerate.host"""
        try:
            url = "https://api.exchangerate.host/latest?base=USD"
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Проверка на HTTP-ошибки
            data = response.json()

            # API возвращает 'rates' напрямую, без ключа 'success'
            if "rates" in data:
                self.rates = data["rates"]
                # Добавляем базовый USD, если его нет
                self.rates["USD"] = 1.0
                messagebox.showinfo("Курсы обновлены", "Актуальные курсы валют загружены!")
            else:
                raise ValueError("Некорректный формат ответа API")
                
        except Exception as e:
            messagebox.showwarning("Курсы не обновлены", 
                f"Не удалось получить актуальные курсы: {e}\nИспользуются значения по умолчанию.")
            # Дефолтные курсы уже установлены в __init__

    def load_history(self):
        if os.path.exists("conversion_history.json"):
            try:
                with open("conversion_history.json", "r", encoding="utf-8") as f:
                    history = json.load(f)
                    for item in history:
                        self.history_tree.insert("", "end", values=(
                            item["date"], 
                            f"{item['from_amount']:.2f}", 
                            item["from_curr"],
                            f"{item['to_amount']:.2f}", 
                            item["to_curr"], 
                            f"{item['rate']:.4f}"
                        ))
            except Exception as e:
                messagebox.showerror("Ошибка загрузки", f"Не удалось загрузить историю: {e}")

    def save_history(self, conversion):
        try:
            history = []
            if os.path.exists("conversion_history.json"):
                with open("conversion_history.json", "r", encoding="utf-8") as f:
                    history = json.load(f)
            
            history.append(conversion)
            
            # Ограничиваем историю последними 100 записями
            if len(history) > 100:
                history = history[-100:]
            
            with open("conversion_history.json", "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить историю: {e}")

    def convert_currency(self):
        try:
            amount = float(self.amount_entry.get())
            if amount <= 0:
                messagebox.showerror("Ошибка", "Сумма должна быть положительным числом!")
                return

            from_curr = self.from_currency.get()
            to_curr = self.to_currency.get()

            # Проверка выбора валют
            if not from_curr or not to_curr:
                messagebox.showerror("Ошибка", "Выберите валюты для конвертации!")
                return

            # Проверка наличия валют в курсах
            if from_curr not in self.rates or to_curr not in self.rates:
                messagebox.showerror("Ошибка", "Одна из выбранных валют отсутствует в списке курсов!")
                return

            # Расчёт курса
            if from_curr == to_curr:
                rate = 1.0
                converted_amount = amount
            else:
                # Конвертация через USD как базовую валюту
                amount_in_usd = amount / self.rates[from_curr]
                converted_amount = amount_in_usd * self.rates[to_curr]
                rate = converted_amount / amount

            # Отображение результата
            result_text = f"{amount} {from_curr} = {converted_amount:.2f} {to_curr} (курс: {rate:.4f})"
            messagebox.showinfo("Результат", result_text)

            # Сохранение в историю
            conversion = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "from_amount": amount,
                "from_curr": from_curr,
                "to_amount": converted_amount,
                "to_curr": to_curr,
                "rate": rate
            }
            self.save_history(conversion)
            self.history_tree.insert("", "end", values=(
                conversion["date"], 
                f"{conversion['from_amount']:.2f}",
                conversion["from_curr"], 
                f"{conversion['to_amount']:.2f}",
                conversion["to_curr"], 
                f"{conversion['rate']:.4f}"
            ))

        except ValueError:
            messagebox.showerror("Ошибка", "Пожалуйста, введите корректную сумму!")
        except Exception as e:
            messagebox.showerror("Непредвиденная ошибка", f"Произошла ошибка: {e}")

# Запуск приложения
if __name__ == "__main__":
    root = tk.Tk()
    app = CurrencyConverter(root)
    root.mainloop()python main.py
