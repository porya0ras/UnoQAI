import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

# pyrefly: ignore [missing-import]
import face_recognition
import numpy as np


class FaceRegistry:
    def __init__(self, db_path: str = "data/faces.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.crops_dir = self.db_path.parent / "crops"
        self.crops_dir.mkdir(parents=True, exist_ok=True)

        if not self.db_path.exists():
            self._save([])

    def _load(self) -> list[dict]:
        with self.db_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    
    def _save(self, records: list[dict]) -> None:
        with self.db_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, ensure_ascii=False, indent=2)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def find_or_create_person(
        self,
        face_encoding: np.ndarray,
        face_crop=None,
        tolerance: float = 0.55,
    ) -> dict:
        records = self._load()
        
        if records:
            known_encodings = [
                np.array(record["encoding"], dtype=np.float64)
                for record in records
            ]

            distances = face_recognition.face_distance(
                known_encodings,
                face_encoding,
            )

            best_index = int(np.argmin(distances))
            best_distance = float(distances[best_index])

            if best_distance <= tolerance:
                record = records[best_index]
                record["last_seen_at"] = self._now()
                record["seen_count"] = int(record.get("seen_count", 0)) + 1
                record["last_distance"] = best_distance

                records[best_index] = record
                self._save(records)

                return {
                    "status": "matched",
                    "person": record,
                    "distance": best_distance,
                    "is_new": False,
                }

        person_id = f"person_{uuid.uuid4().hex[:8]}"

        new_record = {
            "person_id": person_id,
            "name": None,
            "encoding": face_encoding.tolist(),
            "first_seen_at": self._now(),
            "last_seen_at": self._now(),
            "seen_count": 1,
            "asked_name": False,
        }

        records.append(new_record)
        self._save(records)

        return {
            "status": "created",
            "person": new_record,
            "distance": None,
            "is_new": True,
        }

    def update_person_name(self, person_id: str, name: str) -> dict | None:
        records = self._load()

        for index, record in enumerate(records):
            if record["person_id"] == person_id:
                record["name"] = name
                record["name_updated_at"] = self._now()
                record["asked_name"] = True

                records[index] = record
                self._save(records)
                return record

        return None

    def mark_name_asked(self, person_id: str) -> None:
        records = self._load()

        for index, record in enumerate(records):
            if record["person_id"] == person_id:
                record["asked_name"] = True
                records[index] = record
                self._save(records)
                return