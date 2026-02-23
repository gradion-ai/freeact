import pathlib

TARGET_DIRS = [pathlib.Path("examples"), pathlib.Path("docs")]
SUFFIXES = {".py", ".md", ".txt"}
RANGES = [
    (0x202A, 0x202E),
    (0x2066, 0x2069),
]
SINGLES = {0x200E, 0x200F, 0x061C}


def is_target_codepoint(cp):
    if cp in SINGLES:
        return True
    for start, end in RANGES:
        if start <= cp <= end:
            return True
    return False


def iter_files():
    for root in TARGET_DIRS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUFFIXES:
                yield path


def scan_file(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for ch in line:
            cp = ord(ch)
            if is_target_codepoint(cp):
                hits.append((lineno, cp))
    return hits


def main():
    total = 0
    for path in iter_files():
        hits = scan_file(path)
        for lineno, cp in hits:
            total += 1
            print(f"{path}:{lineno}: U+{cp:04X}")

    if total == 0:
        print("NO_BIDI_CONTROL_CHARS")
        return 0

    print(f"TOTAL_HITS: {total}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
