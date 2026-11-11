import base64
import json
from pathlib import Path

# Bold 11pt Carlito advance widths (px @ 96dpi), from Carlito-Bold.ttf.
# Same metrics local and production when the print format embeds Carlito.
_ADDR_WIDTH = {
	" ": 3.32, ",": 3.78, ".": 3.92, "/": 6.3, "-": 4.49, "–": 7.3, "—": 13.28,
	"(": 4.57, ")": 4.57, "&": 10.33, "'": 3.42, ":": 4.05, ";": 4.05, "+": 7.3,
	"0": 7.43, "1": 7.43, "2": 7.43, "3": 7.43, "4": 7.43, "5": 7.43, "6": 7.43,
	"7": 7.43, "8": 7.43, "9": 7.43,
	"a": 7.24, "b": 7.87, "c": 6.14, "d": 7.87, "e": 7.38, "f": 4.64, "g": 6.95,
	"h": 7.87, "i": 3.6, "j": 3.75, "k": 7.04, "l": 3.6, "m": 11.93, "n": 7.87,
	"o": 7.88, "p": 7.87, "q": 7.87, "r": 5.21, "s": 5.85, "t": 5.08, "u": 7.87,
	"v": 6.94, "w": 10.93, "x": 6.74, "y": 6.95, "z": 5.83,
	"A": 8.89, "B": 8.22, "C": 7.76, "D": 9.25, "E": 7.15, "F": 6.73, "G": 9.35,
	"H": 9.25, "I": 3.91, "J": 4.86, "K": 8.02, "L": 6.2, "M": 12.82, "N": 9.66,
	"O": 9.92, "P": 7.81, "Q": 10.06, "R": 8.26, "S": 6.93, "T": 7.26, "U": 9.57,
	"V": 8.67, "W": 13.29, "X": 8.08, "Y": 7.62, "Z": 7.01,
}
# Value cell beside the establishment label (~430px after 76px left + 90% width).
# Pack line 1 first; word wrap only — never split mid-word.
_ADDR_LINE_LIMIT = 420


def _addr_width(text):
	return sum(_ADDR_WIDTH.get(char, 7.9) for char in text)


def wrap_establishment_address(text):
	"""Fill line 1 first; move to line 2 only when the next word no longer fits."""
	text = " ".join(str(text or "").split())
	if not text:
		return ["", ""]
	words = text.split(" ")
	used = 0
	for index, word in enumerate(words):
		gap = _ADDR_WIDTH[" "] if index else 0
		next_width = used + gap + _addr_width(word)
		if index and next_width > _ADDR_LINE_LIMIT:
			return [" ".join(words[:index]), " ".join(words[index:])]
		used = next_width
	return [text, ""]


_EMPLOYEE_PRINT_FONT_CSS = None


def employee_print_font_faces():
	"""Embed Carlito so PDF/print match local and production without OS fonts."""
	global _EMPLOYEE_PRINT_FONT_CSS
	if _EMPLOYEE_PRINT_FONT_CSS is not None:
		return _EMPLOYEE_PRINT_FONT_CSS

	fonts_dir = Path(__file__).resolve().parents[1] / "public" / "fonts"
	faces = []
	for filename, weight in (
		("Carlito-Regular.ttf", 400),
		("Carlito-Bold.ttf", 700),
	):
		path = fonts_dir / filename
		if not path.is_file():
			continue
		payload = base64.b64encode(path.read_bytes()).decode("ascii")
		faces.append(
			"@font-face{"
			"font-family:'Carlito';"
			f"src:url(data:font/truetype;charset=utf-8;base64,{payload}) format('truetype');"
			f"font-weight:{weight};"
			"font-style:normal;"
			"font-display:block;"
			"}"
		)
	_EMPLOYEE_PRINT_FONT_CSS = "\n".join(faces)
	return _EMPLOYEE_PRINT_FONT_CSS


def parse_json(value):
	if not value:
		return []
	try:
		return json.loads(value)
	except Exception:
		return []
