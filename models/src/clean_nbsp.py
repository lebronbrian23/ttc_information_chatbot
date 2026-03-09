# clean_one_file.py
# clean_invisible_and_invalid.py
import io
import re

# Regex covering all common invisible or corrupted characters
BAD_CHARS = re.compile(
    r"[\u00A0"      # NBSP
    r"\u2000-\u200F"  # zero-width and thin spaces
    r"\u2028\u2029"   # line/paragraph separators
    r"\u202F"         # narrow NBSP
    r"\u205F"         # medium mathematical space
    r"\u2060"         # word joiner
    r"\uFEFF"         # BOM
    r"\u00AD"         # soft hyphen
    r"\uFFFD"         # replacement char (�)
    r"]"
)


def clean_file(path):
    with io.open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    cleaned = BAD_CHARS.sub(" ", text)

    if cleaned != text:
        with io.open(path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print("Cleaned invisible/corrupted characters in:", path)
    else:
        print("No invisible/corrupted characters found in:", path)


if __name__ == "__main__":
    filename = input("Enter the file name to clean: ").strip()
    clean_file(filename)
