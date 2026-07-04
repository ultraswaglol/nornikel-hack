# config/logger.py
import datetime

def log_action(user_role: str, action_type: str, details: str):
    """
    Записывает действия пользователя в лог-файл аудита ИБ
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [ROLE: {user_role}] [ACTION: {action_type}] - {details}\n"
    
    with open("audit_security.log", "a", encoding="utf-8") as f:
        f.write(log_entry)