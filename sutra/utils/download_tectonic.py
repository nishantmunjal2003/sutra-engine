import os
import shutil
import urllib.request
import zipfile
import tempfile

TECTONIC_VERSION = "0.15.0"
TECTONIC_URL = f"https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40{TECTONIC_VERSION}/tectonic-{TECTONIC_VERSION}-x86_64-pc-windows-msvc.zip"

def get_tectonic_path() -> str:
    # 1. Check if tectonic is on system PATH
    system_tectonic = shutil.which("tectonic")
    if system_tectonic:
        return system_tectonic

    # 2. Check if local cached tectonic exists
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(base_dir, "resources", "bin")
    local_tectonic = os.path.join(bin_dir, "tectonic.exe")

    if os.path.exists(local_tectonic):
        return local_tectonic

    # If not found, download and cache it
    download_tectonic_if_missing()
    return local_tectonic

def download_tectonic_if_missing():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(base_dir, "resources", "bin")
    os.makedirs(bin_dir, exist_ok=True)
    local_tectonic = os.path.join(bin_dir, "tectonic.exe")

    if os.path.exists(local_tectonic):
        return

    print(f"Downloading Tectonic v{TECTONIC_VERSION} local binary...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "tectonic.zip")
        # Download the zip
        urllib.request.urlretrieve(TECTONIC_URL, zip_path)
        
        # Extract tectonic.exe
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Tectonic zip contains tectonic.exe directly
            zip_ref.extract("tectonic.exe", bin_dir)
            
    print(f"Tectonic downloaded and cached at: {local_tectonic}")

if __name__ == "__main__":
    download_tectonic_if_missing()
