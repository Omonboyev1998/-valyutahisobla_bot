"""Durable forward journal: forward qilingan, lekin hali bazaga yozilmagan kitoblar.

Nega kerak: `add_book()` lar paketlanganda (batch), forward bilan commit
orasida jarayon o'lsa, keyingi skanda o'sha xabarlar yana forward qilinib,
ombor kanalda ikki nusxa paydo bo'lardi. Shuning uchun forward QILISHDAN OLDIN
niyat shu faylga yozilib fsync qilinadi; keyingi skan shu jurnalni o'qib,
allaqachon forward qilinganlarni qayta yubormaydi.

Format: har satr bitta JSON obyekti (append-only JSONL). Buzilgan oxirgi satr
(yarim yozilgan) o'qishda e'tiborsiz qoldiriladi.
"""
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger("BookJournal")


class ForwardJournal:
    """Append-only, fsync qilinadigan kichik jurnal."""

    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)

    def record_forwarded(
        self,
        source_chat_id: Optional[str],
        source_message_id: Optional[int],
        file_name: str,
        file_size: int,
        storage_message_id: Optional[int] = None,
    ) -> None:
        entry = {
            "source_chat_id": str(source_chat_id) if source_chat_id else None,
            "source_message_id": source_message_id,
            "file_name": file_name,
            "file_size": file_size,
            "storage_message_id": storage_message_id,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

    def pending(self) -> List[Dict[str, Any]]:
        """Jurnaldagi yaroqli yozuvlar; har (manba, xabar) uchun ENG OXIRGISI.

        Nusxalovchi bitta xabar uchun ikki marta yozadi: forwarddan oldin
        (storage_message_id hali yo'q) va forwarddan keyin (to'liq). Tiklashda
        bir kitob IKKI marta qo'shilmasligi uchun oxirgisi g'olib bo'ladi.
        """
        if not os.path.exists(self.path):
            return []
        collapsed: Dict[Any, Dict[str, Any]] = {}
        order: List[Any] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    # Yarim yozilgan oxirgi satr - e'tiborsiz qoldiramiz.
                    continue
                if not isinstance(entry, dict):
                    continue
                key = (entry.get("source_chat_id"), entry.get("source_message_id"))
                if key not in collapsed:
                    order.append(key)
                collapsed[key] = entry
        return [collapsed[key] for key in order]

    def forwarded_entries(self) -> List[Dict[str, Any]]:
        """Faqat ANIQ forward qilinganlar (storage_message_id bor).

        Forwarddan OLDIN yozilgan yozuv noaniq: forward muvaffaqiyatsiz
        bo'lishi mumkin edi. Shuning uchun faqat forwarddan keyin yozilgan
        (storage_message_id to'ldirilgan) yozuvlar "yuborilgan" hisoblanadi.
        """
        return [e for e in self.pending() if e.get("storage_message_id")]

    def clear(self) -> None:
        """Paket commit QILINGANDAN KEYIN chaqiriladi: jurnal bo'shatiladi."""
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.flush()
                os.fsync(fh.fileno())
        except FileNotFoundError:
            pass
