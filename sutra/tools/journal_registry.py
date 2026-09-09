import os
import json
import shutil
from typing import List, Dict, Any, Optional
from sutra.models import JournalSettings

class JournalRegistry:
    def __init__(self, build_root: str):
        self.build_root = build_root
        self.journals_dir = os.path.join(build_root, "journals")
        os.makedirs(self.journals_dir, exist_ok=True)

    def save_journal(self, journal_id: str, settings: JournalSettings) -> None:
        journal_dir = os.path.join(self.journals_dir, journal_id)
        os.makedirs(journal_dir, exist_ok=True)
        
        settings_path = os.path.join(journal_dir, "settings.json")
        # settings.model_dump_json() is standard in Pydantic v2
        with open(settings_path, "w", encoding="utf-8") as f:
            f.write(settings.model_dump_json(indent=4))

    def load_journal(self, journal_id: str) -> Optional[JournalSettings]:
        settings_path = os.path.join(self.journals_dir, journal_id, "settings.json")
        if not os.path.exists(settings_path):
            return None
            
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return JournalSettings(**data)

    def save_logo(self, journal_id: str, file_bytes: bytes, original_filename: str) -> str:
        """Saves journal logo file and updates journal settings if available."""
        journal_dir = os.path.join(self.journals_dir, journal_id)
        os.makedirs(journal_dir, exist_ok=True)

        _, ext = os.path.splitext(original_filename)
        ext = ext.lower() if ext else ".png"
        if ext not in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
            ext = ".png"

        saved_filename = f"logo{ext}"
        logo_path = os.path.join(journal_dir, saved_filename)
        with open(logo_path, "wb") as f:
            f.write(file_bytes)

        # Update existing settings.json if present
        settings = self.load_journal(journal_id)
        if settings:
            settings.identity.logo_filename = saved_filename
            self.save_journal(journal_id, settings)

        return saved_filename

    def get_logo_path(self, journal_id: str) -> Optional[str]:
        """Returns the absolute path to the journal logo if it exists."""
        journal_dir = os.path.join(self.journals_dir, journal_id)
        if not os.path.exists(journal_dir):
            return None

        # Check for settings-specified logo first
        settings = self.load_journal(journal_id)
        if settings and settings.identity and settings.identity.logo_filename:
            target = os.path.join(journal_dir, settings.identity.logo_filename)
            if os.path.exists(target):
                return target

        # Check standard logo file names
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
            target = os.path.join(journal_dir, f"logo{ext}")
            if os.path.exists(target):
                return target

        return None

    def list_journals(self) -> List[Dict[str, Any]]:
        journals = []
        if not os.path.exists(self.journals_dir):
            return journals
            
        for journal_id in os.listdir(self.journals_dir):
            settings_path = os.path.join(self.journals_dir, journal_id, "settings.json")
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        identity = data.get("identity", {}) or {}
                        volumes = data.get("volumes", []) or []
                        active_vol_id = data.get("active_volume_id")
                        active_vol = None
                        if active_vol_id:
                            active_vol = next((v for v in volumes if v.get("id") == active_vol_id), None)
                        if not active_vol and volumes:
                            active_vol = volumes[0]

                        has_logo = bool(self.get_logo_path(journal_id))

                        journals.append({
                            "journal_id": data.get("journal_id"),
                            "journal_name": data.get("journal_name"),
                            "created_at": data.get("created_at"),
                            "columns": data.get("page", {}).get("columns", 1),
                            "paper_size": data.get("page", {}).get("paper_size", "a4"),
                            "issn_print": identity.get("issn_print"),
                            "issn_online": identity.get("issn_online"),
                            "website": identity.get("website"),
                            "publisher": identity.get("publisher"),
                            "has_logo": has_logo,
                            "volume_count": len(volumes),
                            "active_volume": active_vol
                        })
                except Exception:
                    pass
        return journals

    def delete_journal(self, journal_id: str) -> bool:
        journal_dir = os.path.join(self.journals_dir, journal_id)
        if os.path.exists(journal_dir):
            shutil.rmtree(journal_dir)
            return True
        return False

