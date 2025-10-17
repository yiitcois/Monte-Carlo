import os

def detect_format(path: str) -> str:
    ext = os.path.splitext(path.lower())[1]
    if ext == ".xml":
        return "msproject_xml"
    if ext == ".xer":
        return "primavera_xer"
    if ext == ".csv":
        return "csv_generic"
    # fallback (try by content)
    with open(path, "rb") as f:
        head = f.read(100).lower()
    if b"<project" in head and b"<tasks>" in head:
        return "msproject_xml"
    raise ValueError(f"Desteklenmeyen format: {path}")
