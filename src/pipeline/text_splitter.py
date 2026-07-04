# src/pipeline/text_splitter.py
from typing import List, Dict, Any

class AdvancedTextSplitter:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        # Оптимизировано: 800 символов гарантирует емкий контекст без превышения лимитов токенов ИИ
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str, metadata_template: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks = []
        text_len = len(text)
        start = 0

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            
            if end < text_len:
                for separator in ["\n\n", "\n", ". ", " "]:
                    last_sep = text.rfind(separator, start + int(self.chunk_size * 0.75), end)
                    if last_sep != -1:
                        end = last_sep + len(separator)
                        break
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_data = {
                    "text": chunk_text,
                    "metadata": {
                        **metadata_template,
                        "chunk_start": start,
                        "chunk_end": end
                    }
                }
                chunks.append(chunk_data)
                
            start = end - self.chunk_overlap
            if start >= text_len or end == text_len:
                break
                
        return chunks

text_splitter = AdvancedTextSplitter()