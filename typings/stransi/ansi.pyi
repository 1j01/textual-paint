"""
This type stub file was generated by pyright.
"""

from typing import Iterable, Text
from ._misc import _CustomText
from .escape import Escape
from .instruction import Instruction

"""A string that can be disassembled into text and ANSI escape sequences."""
class Ansi(_CustomText):
    r"""
    A string that can be disassembled into text and ANSI escape sequences.

    Examples
    --------
    >>> s = Ansi("\x1b[1;31mHello\x1b[m, world!")
    >>> list(s.escapes())
    [Escape('\x1b[1;31m'), 'Hello', Escape('\x1b[m'), ', world!']
    >>> list(s.instructions())  # doctest: +NORMALIZE_WHITESPACE
    [SetAttribute(attribute=<Attribute.BOLD: 1>),
     SetColor(role=<ColorRole.FOREGROUND: 30>,
     color=Ansi256(code=1)),
     'Hello',
     SetAttribute(attribute=<Attribute.NORMAL: 0>),
     ', world!']
    """
    PATTERN = ...
    def escapes(self) -> Iterable[Escape | Text]:
        """Yield ANSI escapes and text in the order they appear."""
        ...
    
    def instructions(self) -> Iterable[Instruction | Text]:
        """Yield ANSI instructions and text in the order they appear."""
        ...
    


