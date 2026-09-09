import urllib.request
import re

url = "https://jats.nlm.nih.gov/publishing/1.3/xsd/JATS-journalpublishing1-3-mathml3.xsd"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
content = urllib.request.urlopen(req).read().decode('utf-8')

print("All imports in JATS-journalpublishing1-3-mathml3.xsd:")
for imp in re.findall(r'schemaLocation\s*=\s*"([^"]+)"', content):
    print(f" - {imp}")
