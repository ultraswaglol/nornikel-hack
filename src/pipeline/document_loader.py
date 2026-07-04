# src/pipeline/document_loader.py
import fitz  # PyMuPDF
from typing import Dict, Any, Tuple
from src.models.ontology import SecurityLevel, TrustLevel

# Пытаемся импортировать pdfplumber для высокоточного извлечения таблиц
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

class DocumentLoader:
    @staticmethod
    def _extract_tables_as_markdown(file_path: str) -> str:
        """
        Сканирует PDF, находит геометрические таблицы и преобразует их 
        в структурированный Markdown-формат, понятный языковым моделям.
        """
        if not HAS_PDFPLUMBER:
            return ""
            
        tables_text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        if not table:
                            continue
                            
                        # Очищаем ячейки от None и лишних переносов строк внутри ячеек
                        clean_table = []
                        for row in table:
                            clean_row = [str(cell or "").strip().replace("\n", " ") for cell in row]
                            # Добавляем строку только если она не полностью пустая
                            if any(clean_row):
                                clean_table.append(clean_row)
                                
                        if not clean_table or not clean_table[0]:
                            continue
                            
                        # Формируем Markdown-таблицу
                        markdown_table = "\n"
                        headers = clean_table[0]
                        
                        # Заголовок таблицы
                        markdown_table += "| " + " | ".join(headers) + " |\n"
                        # Разделитель заголовка и данных
                        markdown_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                        
                        # Строки данных
                        for row in clean_table[1:]:
                            # Выравниваем длину строки по заголовку, если ИИ ошибся с ячейками
                            if len(row) < len(headers):
                                row.extend([""] * (len(headers) - len(row)))
                            elif len(row) > len(headers):
                                row = row[:len(headers)]
                            markdown_table += "| " + " | ".join(row) + " |\n"
                            
                        tables_text += f"\n\n[Автоматически извлеченная Таблица {table_idx+1} на странице {page_num+1}]:\n{markdown_table}\n"
        except Exception as e:
            print(f"⚠️ [loader]: Ошибка при извлечении таблиц через pdfplumber: {e}")
            
        return tables_text

    @classmethod
    def load_pdf(cls, file_path: str, security_level: SecurityLevel = SecurityLevel.PUBLIC, trust_level: TrustLevel = TrustLevel.LEVEL_B) -> Tuple[str, Dict[str, Any]]:
        """
        Читает PDF, извлекает текст, находит и оцифровывает таблицы в Markdown
        и формирует метаданные документа.
        """
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
            
        # Запускаем интеллектуальный экстрактор таблиц
        if HAS_PDFPLUMBER:
            tables_markdown = cls._extract_tables_as_markdown(file_path)
            if tables_markdown:
                text += "\n\n=== ОЦИФРОВАННЫЕ ТАБЛИЦЫ ДОКУМЕНТА ===\n" + tables_markdown
            
        doc_metadata = doc.metadata if doc.metadata else {}
        
        # Получаем заголовок
        title = doc_metadata.get("title", "").strip()
        
        # Защита от заглушек типа untitled
        placeholders = ["untitled", "none", "untitled document", "без названия", "document", ""]
        if not title or title.lower() in placeholders:
            import os
            title = os.path.basename(file_path).replace(".pdf", "")

        year = 2024  
        creation_date = doc_metadata.get("creationDate", "")
        if creation_date and len(creation_date) >= 6:
            try:
                year = int(creation_date[2:6])
            except ValueError:
                pass

        metadata = {
            "title": title,
            "authors": [doc_metadata.get("author", "Неизвестный автор")] if doc_metadata.get("author") else ["НИИ Норникель"],
            "year": year,
            "geography": "RU" if "ru" in title.lower() or "росс" in title.lower() else "GLOBAL",
            "security_level": security_level,
            "trust_level": trust_level
        }
        
        return text.strip(), metadata

document_loader = DocumentLoader()