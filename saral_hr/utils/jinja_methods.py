import json

# Bold 11pt widths for the print font. The limit is one full value line on this
# register, so a longer establishment address breaks onto the second line.
_ADDR_WIDTH = {
    " ": 4.08, ",": 4.08, ".": 4.08, "/": 4.08, "-": 4.89, "–": 8.16, "—": 14.66,
    "(": 4.89, ")": 4.89, "&": 10.59, "'": 3.5, ":": 4.89, ";": 4.89, "+": 8.56,
    "0": 8.16, "1": 8.16, "2": 8.16, "3": 8.16, "4": 8.16, "5": 8.16, "6": 8.16,
    "7": 8.16, "8": 8.16, "9": 8.16,
    "a": 8.16, "b": 8.95, "c": 8.16, "d": 8.95, "e": 8.16, "f": 4.89, "g": 8.95,
    "h": 8.95, "i": 4.08, "j": 4.08, "k": 8.16, "l": 4.08, "m": 13.05, "n": 8.95,
    "o": 8.95, "p": 8.95, "q": 8.95, "r": 5.72, "s": 8.16, "t": 4.89, "u": 8.95,
    "v": 8.16, "w": 11.41, "x": 8.16, "y": 8.16, "z": 7.33,
    "A": 10.59, "B": 10.59, "C": 10.59, "D": 10.59, "E": 9.78, "F": 8.95, "G": 11.41,
    "H": 10.59, "I": 4.08, "J": 8.16, "K": 10.59, "L": 8.95, "M": 12.22, "N": 10.59,
    "O": 11.41, "P": 9.78, "Q": 11.41, "R": 10.59, "S": 9.78, "T": 8.95, "U": 10.59,
    "V": 9.78, "W": 13.84, "X": 9.78, "Y": 9.78, "Z": 8.95,
}
_ADDR_LINE_LIMIT = 590


def _addr_width(text):
    return sum(_ADDR_WIDTH.get(char, 8.95) for char in text)


def wrap_establishment_address(text):
    """Split an establishment address across the two register lines."""
    text = " ".join(str(text or "").split())
    if not text:
        return ["", ""]
    words = text.split(" ")
    used = 0
    for index, word in enumerate(words):
        gap = _ADDR_WIDTH[" "] if index else 0
        if index and used + gap + _addr_width(word) > _ADDR_LINE_LIMIT:
            return [" ".join(words[:index]), " ".join(words[index:])]
        used += gap + _addr_width(word)
    return [text, ""]


def parse_json(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []
