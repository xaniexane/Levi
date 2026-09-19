"""LEVI's modeless wayfinder: one text stream, search *as* navigation.

Studied from: retired-software-revival-research-20260916-0004/report.md (§26).

The studied mechanism pairs two ideas: *modelessness* — no separate modes
for finding, editing, and commanding — and *Leap keys* — jump to a position
by naming it instead of stepping toward it.

LEVI-native remix: the whole document is one unified text stream. The model
knows no files, no apps, no modes. Typing narrows a live candidate set
(incremental search-as-navigation); the current selection IS the search
result; every command operates on the current selection. You describe where
you want to be, and you are there.

Honesty: LOAD-BEARING as a navigation/selection model for text streams.
Search is case-insensitive substring matching (no regex engine); the stream
lives in memory; "Leap keys" here means describe-and-jump, never a
keybinding system. Stdlib only, no network.
"""

ORIGIN = "levi-revival/leapfind"


class LeapStream:
    """One unified text stream. Typing is search; the selection is the result.

    There are no modes: ``type()`` always searches, ``leap()`` always jumps,
    and the edit commands always act on whatever is currently selected.
    """

    def __init__(self, text=""):
        self.lines = text.split("\n") if text else []
        self.query = ""
        self._sel = 0  # index into the current candidate list
        self.caret = 0  # line number the eye is resting on
        self.clipboard = ""

    # -- incremental search-as-navigation ----------------------------------
    def _matches(self):
        q = self.query.lower()
        if not q:
            return list(enumerate(self.lines))
        return [(i, ln) for i, ln in enumerate(self.lines) if q in ln.lower()]

    @property
    def candidates(self):
        """Live candidate list: ``[(line_no, text), ...]`` matching the query."""
        return self._matches()

    @property
    def selection(self):
        """The current selection — always the live search result, never stale."""
        matches = self._matches()
        if not matches:
            return None
        self._sel = max(0, min(self._sel, len(matches) - 1))
        return matches[self._sel]

    def type(self, text):
        """Type characters: the query grows and the selection narrows live."""
        self.query += text
        self._sel = 0
        return self.selection

    def backspace(self, n=1):
        """Erase query characters: the candidate set widens back out."""
        self.query = self.query[:-n] if n <= len(self.query) else ""
        self._sel = 0
        return self.selection

    def clear_query(self):
        self.query = ""
        self._sel = 0
        return self.selection

    def step(self, delta=1):
        """Move the selection within the candidates (wrap-around)."""
        matches = self._matches()
        if matches:
            self._sel = (self._sel + delta) % len(matches)
        return self.selection

    # -- Leap keys: name it, be there --------------------------------------
    def leap(self, pattern):
        """Describe a position by name; the caret jumps straight to it."""
        self.query = pattern
        self._sel = 0
        sel = self.selection
        if sel is not None:
            self.caret = sel[0]
        return sel

    def jump(self):
        """Move the caret to the current selection."""
        sel = self.selection
        if sel is not None:
            self.caret = sel[0]
        return self.caret

    # -- commands operate on the current selection --------------------------
    def _require_selection(self):
        sel = self.selection
        if sel is None:
            raise LookupError("no selection: the query matches nothing")
        return sel

    def delete_selection(self):
        """Delete the selected line; selection falls to the next match."""
        i, _ = self._require_selection()
        del self.lines[i]
        self._sel = 0
        return self.selection

    def replace_selection(self, new_text):
        """Replace the selected line in place."""
        i, _ = self._require_selection()
        self.lines[i] = new_text
        return (i, new_text)

    def yank(self):
        """Copy the selection to the clipboard."""
        _, text = self._require_selection()
        self.clipboard = text
        return text

    def paste_below(self, text=None):
        """Insert text (or the clipboard) below the selected line."""
        i, _ = self._require_selection()
        self.lines.insert(i + 1, self.clipboard if text is None else text)
        return self.candidates

    @property
    def text(self):
        return "\n".join(self.lines)

    def __len__(self):
        return len(self.lines)
