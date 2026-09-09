import os
import re
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "https://jats.nlm.nih.gov/publishing/1.3/xsd/"
TARGET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "schemas", "JATS-1.3"))

SCHEMA_REGEX = re.compile(r'schemaLocation\s*=\s*"([^"]+)"')

def download_jats_schemas_if_missing():
    """
    Crawls and downloads all JATS 1.3 XSD schema files from NLM if they don't exist locally.
    Preserves relative folder structure so lxml can resolve imports offline.
    """
    root_schema = "JATS-journalpublishing1-3-mathml3.xsd"
    root_path = os.path.join(TARGET_DIR, root_schema)
    
    if os.path.exists(root_path):
        print(f"JATS 1.3 schema already present locally in: {TARGET_DIR}")
        return True

    print("JATS 1.3 schema files missing. Starting crawl and download from NLM...")
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    visited = set()
    
    def crawl_and_download(relative_path: str, parent_url: str):
        # Resolve full URL relative to parent
        url = urllib.parse.urljoin(parent_url, relative_path)
        if url in visited:
            return
        visited.add(url)
        
        # Calculate local storage path preserving relative folder structure
        if url.startswith(BASE_URL):
            rel_url_path = url[len(BASE_URL):]
        else:
            rel_url_path = os.path.basename(relative_path)
            
        local_path = os.path.abspath(os.path.join(TARGET_DIR, rel_url_path.replace("/", os.sep)))
        
        # Ensure target subdirectory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        print(f"Downloading: {url} -> {local_path}")
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SutraPress/0.1'}
            )
            with urllib.request.urlopen(req) as response:
                content = response.read()
                
            with open(local_path, "wb") as f:
                f.write(content)
                
            # Scan for nested schema imports
            content_str = content.decode("utf-8", errors="ignore")
            imports = SCHEMA_REGEX.findall(content_str)
            for imp in imports:
                crawl_and_download(imp, url)
                
        except urllib.error.URLError as e:
            print(f"Error downloading schema file from {url}: {str(e)}")
            raise

    try:
        crawl_and_download(root_schema, BASE_URL)
        print("Successfully cached JATS 1.3 XSD schemas locally with directory structure.")
        return True
    except Exception as e:
        print(f"Crawl and download of JATS 1.3 schemas failed: {str(e)}")
        # Delete root path if it was partially written
        if os.path.exists(root_path):
            os.remove(root_path)
        return False

if __name__ == "__main__":
    download_jats_schemas_if_missing()
