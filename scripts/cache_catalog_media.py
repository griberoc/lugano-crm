"""Cache only public catalog photos as local responsive WebP files.
Print the URL mapping; it is reviewed and added to ui.js separately.
"""
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from PIL import Image, ImageOps

root = Path(__file__).resolve().parents[1]
output = root / "frontend/assets/catalog"
output.mkdir(exist_ok=True)
products = []
for page in range(1, 21):
    with urlopen(f"http://127.0.0.1:8000/api/v1/catalog/products?page={page}&page_size=100", timeout=20) as response:
        batch = json.load(response)
    products.extend(batch)
    if len(batch) < 100:
        break
mapping, failures = {}, []
for url in sorted({p.get("image_url") for p in products if p.get("image_url")}):
    if urlparse(url).hostname != "static.ifood-static.com.br":
        continue
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    try:
        with urlopen(Request(url, headers={"User-Agent": "Lugano-media-cache/1.0"}), timeout=20) as response:
            raw = response.read(10_000_001)
        if len(raw) > 10_000_000:
            raise ValueError("Image exceeds limit")
        picture = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
        for size in [400, 800]:
            image = picture.copy()
            image.thumbnail((size, size))
            image.save(output / f"{digest}-{size}.webp", "WEBP", quality=82)
        mapping[url] = f"../assets/catalog/{digest}"
    except Exception as error:
        failures.append({"url": url, "error": type(error).__name__})
print(json.dumps({"products": len(products), "images": mapping, "failures": failures}))
