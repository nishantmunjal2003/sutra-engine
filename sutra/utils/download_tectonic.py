import os
import shutil
import urllib.request
import zipfile
import tarfile
import tempfile
import platform

TECTONIC_VERSION = "0.15.0"

def get_tectonic_url() -> str:
    if platform.system().lower() == "windows":
        return f"https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40{TECTONIC_VERSION}/tectonic-{TECTONIC_VERSION}-x86_64-pc-windows-msvc.zip"
    else:
        return f"https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40{TECTONIC_VERSION}/tectonic-{TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz"

def get_tectonic_path() -> str:
    # 1. Check if tectonic is on system PATH
    system_tectonic = shutil.which("tectonic")
    if system_tectonic:
        return system_tectonic

    # 2. Check if local cached tectonic exists
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(base_dir, "resources", "bin")
    bin_name = "tectonic.exe" if platform.system().lower() == "windows" else "tectonic"
    local_tectonic = os.path.join(bin_dir, bin_name)

    if os.path.exists(local_tectonic):
        return local_tectonic

    # If not found, download and cache it
    download_tectonic_if_missing()
    return local_tectonic

def download_tectonic_if_missing():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(base_dir, "resources", "bin")
    os.makedirs(bin_dir, exist_ok=True)
    is_windows = platform.system().lower() == "windows"
    bin_name = "tectonic.exe" if is_windows else "tectonic"
    local_tectonic = os.path.join(bin_dir, bin_name)

    if os.path.exists(local_tectonic):
        return

    url = get_tectonic_url()
    print(f"Downloading Tectonic v{TECTONIC_VERSION} for {platform.system()}...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_name = "tectonic.zip" if is_windows else "tectonic.tar.gz"
        archive_path = os.path.join(tmpdir, archive_name)
        urllib.request.urlretrieve(url, archive_path)
        
        if is_windows:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extract("tectonic.exe", bin_dir)
        else:
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extract("tectonic", bin_dir)
            os.chmod(local_tectonic, 0o755)
            
    print(f"Tectonic downloaded and cached at: {local_tectonic}")

if __name__ == "__main__":
    download_tectonic_if_missing()
