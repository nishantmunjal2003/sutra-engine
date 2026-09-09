import os
import json
import shutil
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet

class ProjectPersistenceManager:
    """
    Manages project storage at rest with AES symmetric encryption (Fernet).
    Encrypts/decrypts manuscript files, metadata/blocks JSON, and extracted media.
    """
    def __init__(self, build_root: str):
        self.build_root = build_root
        self.projects_dir = os.path.join(build_root, "projects")
        os.makedirs(self.projects_dir, exist_ok=True)
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)

    def _get_or_create_key(self) -> bytes:
        """
        Reads secret key from environment or key file, generates one if missing.
        """
        env_key = os.environ.get("SUTRA_SECRET_KEY")
        if env_key:
            return env_key.encode("utf-8")

        key_path = os.path.join(self.build_root, "secret.key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return f.read().strip()
        
        # Generate new key
        new_key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(new_key)
        return new_key

    def _get_project_dir(self, project_id: str) -> str:
        p_dir = os.path.join(self.projects_dir, project_id)
        os.makedirs(p_dir, exist_ok=True)
        return p_dir

    def save_project(self, project_id: str, state_json: Dict[str, Any], docx_bytes: Optional[bytes] = None):
        """
        Serializes and encrypts the project state, and optionally the source docx.
        """
        p_dir = self._get_project_dir(project_id)
        
        # Save state JSON (encrypted)
        state_data = json.dumps(state_json).encode("utf-8")
        encrypted_state = self.cipher.encrypt(state_data)
        state_path = os.path.join(p_dir, "project_state.json.enc")
        with open(state_path, "wb") as f:
            f.write(encrypted_state)

        # Save docx (encrypted)
        if docx_bytes is not None:
            encrypted_docx = self.cipher.encrypt(docx_bytes)
            docx_path = os.path.join(p_dir, "manuscript.docx.enc")
            with open(docx_path, "wb") as f:
                f.write(encrypted_docx)

    def load_project(self, project_id: str) -> Dict[str, Any]:
        """
        Reads, decrypts, and deserializes the project state.
        """
        p_dir = os.path.join(self.projects_dir, project_id)
        state_path = os.path.join(p_dir, "project_state.json.enc")
        if not os.path.exists(state_path):
            raise FileNotFoundError(f"Project state not found for ID: {project_id}")

        with open(state_path, "rb") as f:
            encrypted_state = f.read()
        
        decrypted_state = self.cipher.decrypt(encrypted_state)
        return json.loads(decrypted_state.decode("utf-8"))

    def load_docx(self, project_id: str) -> bytes:
        """
        Decrypts and returns the original manuscript bytes.
        """
        p_dir = os.path.join(self.projects_dir, project_id)
        docx_path = os.path.join(p_dir, "manuscript.docx.enc")
        if not os.path.exists(docx_path):
            raise FileNotFoundError(f"Manuscript not found for project ID: {project_id}")

        with open(docx_path, "rb") as f:
            encrypted_docx = f.read()

        return self.cipher.decrypt(encrypted_docx)

    def save_raw_pdf(self, project_id: str, pdf_bytes: bytes):
        """
        Encrypts and stores a reference or raw PDF manuscript.
        """
        p_dir = self._get_project_dir(project_id)
        encrypted_pdf = self.cipher.encrypt(pdf_bytes)
        pdf_path = os.path.join(p_dir, "raw_reference.pdf.enc")
        with open(pdf_path, "wb") as f:
            f.write(encrypted_pdf)

    def load_raw_pdf(self, project_id: str) -> bytes:
        """
        Decrypts and returns the raw reference PDF bytes.
        """
        p_dir = os.path.join(self.projects_dir, project_id)
        pdf_path = os.path.join(p_dir, "raw_reference.pdf.enc")
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Raw reference PDF not found for project ID: {project_id}")
        with open(pdf_path, "rb") as f:
            encrypted_pdf = f.read()
        return self.cipher.decrypt(encrypted_pdf)

    def has_raw_pdf(self, project_id: str) -> bool:
        """
        Checks whether a raw reference PDF exists for the given project.
        """
        p_dir = os.path.join(self.projects_dir, project_id)
        return os.path.exists(os.path.join(p_dir, "raw_reference.pdf.enc"))

    def delete_project(self, project_id: str):
        """
        Permanently purges the project folder from storage.
        """
        p_dir = os.path.join(self.projects_dir, project_id)
        if os.path.exists(p_dir):
            shutil.rmtree(p_dir)

    def encrypt_media(self, project_id: str, filename: str, content: bytes):
        """
        Encrypts and stores media assets (images, figures).
        """
        p_dir = self._get_project_dir(project_id)
        media_dir = os.path.join(p_dir, "media")
        os.makedirs(media_dir, exist_ok=True)
        
        encrypted_content = self.cipher.encrypt(content)
        media_path = os.path.join(media_dir, f"{filename}.enc")
        with open(media_path, "wb") as f:
            f.write(encrypted_content)

    def decrypt_media(self, project_id: str, filename: str) -> bytes:
        """
        Decrypts a media asset.
        """
        p_dir = os.path.join(self.projects_dir, project_id)
        media_path = os.path.join(p_dir, "media", f"{filename}.enc")
        if not os.path.exists(media_path):
            raise FileNotFoundError(f"Media asset missing: {filename}")

        with open(media_path, "rb") as f:
            encrypted_content = f.read()
            
        return self.cipher.decrypt(encrypted_content)

    def list_projects(self) -> list:
        """
        Scans all project directories, loads and decrypts their state, and returns the list.
        """
        projects = []
        if not os.path.exists(self.projects_dir):
            return projects
        for p_id in os.listdir(self.projects_dir):
            p_dir = os.path.join(self.projects_dir, p_id)
            if os.path.isdir(p_dir):
                state_path = os.path.join(p_dir, "project_state.json.enc")
                if os.path.exists(state_path):
                    try:
                        state = self.load_project(p_id)
                        projects.append(state)
                    except Exception:
                        pass
        return projects
