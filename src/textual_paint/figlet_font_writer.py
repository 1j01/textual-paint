
__author__ = "Patrick Gillespie"
__maintainer__ = "Isaiah Odhner"
__copyright__ = "Copyright (c) Patrick Gillespie"
__license__ = "MIT"
"""
Copyright (c) 2023 Patrick Gillespie

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from enum import Enum

class FIGletFontWriter:
    """Used to write FIGlet fonts.
    
    createFigFileData() returns a string that can be written to a .flf file.

    It can automatically fix some common problems with FIGlet fonts, such as
    incorrect character widths/heights, and missing lowercase characters.

    This Python code is based on JS from http://patorjk.com/figlet-editor/
    """

    class Layout(Enum):
        """Layout options for FIGcharacter spacing."""

        FULL = 0
        """Represents each FIGcharacter occupying the full width or height of its arrangement of sub-characters as designed."""
        FITTED = 1
        """Moves FIGcharacters closer together until sub-characters touch."""
        UNIVERSAL_SMUSHING = 2
        """Overlaps FIGcharacters by one sub-character, with the latter character taking precedence."""
        CONTROLLED_SMUSHING = 3
        """Overlaps FIGcharacters by one sub-character, using a configurable set of rules for overlap handling."""

    charOrder: list[int] = [ii for ii in range(32, 127)] + [196, 214, 220, 228, 246, 252, 223]
    R"""Character codes that are required to be in any FIGlet font.
    
    Printable portion of the ASCII character set:
32 (blank/space) 64 @             96  `
33 !             65 A             97  a
34 "             66 B             98  b
35 #             67 C             99  c
36 $             68 D             100 d
37 %             69 E             101 e
38 &             70 F             102 f
39 '             71 G             103 g
40 (             72 H             104 h
41 )             73 I             105 i
42 *             74 J             106 j
43 +             75 K             107 k
44 ,             76 L             108 l
45 -             77 M             109 m
46 .             78 N             110 n
47 /             79 O             111 o
48 0             80 P             112 p
49 1             81 Q             113 q
50 2             82 R             114 r
51 3             83 S             115 s
52 4             84 T             116 t
53 5             85 U             117 u
54 6             86 V             118 v
55 7             87 W             119 w
56 8             88 X             120 x
57 9             89 Y             121 y
58 :             90 Z             122 z
59 ;             91 [             123 {
60 <             92 \             124 |
61 =             93 ]             125 }
62 >             94 ^             126 ~
63 ?             95 _
Additional required Deutsch FIGcharacters, in order:
196 Ä (umlauted "A" -- two dots over letter "A")
214 Ö (umlauted "O" -- two dots over letter "O")
220 Ü (umlauted "U" -- two dots over letter "U")
228 ä (umlauted "a" -- two dots over letter "a")
246 ö (umlauted "o" -- two dots over letter "o")
252 ü (umlauted "u" -- two dots over letter "u")
223 ß ("ess-zed" -- see FIGcharacter illustration below)
                              ___
                             / _ \
                            | |/ /
          Ess-zed >>--->    | |\ \
                            | ||_/
                            |_|

Additional characters must use code tagged characters, which are not yet supported.
"""

    def __init__(
        self,
        figChars: dict[int, str] = {},
        height: int | None = None,
        baseline: int | None = None,
        maxLength: int | None = None,
        commentLines: list[str] = [],
        rightToLeft: bool = False,
        horizontalLayout: Layout = Layout.UNIVERSAL_SMUSHING,
        verticalLayout: Layout = Layout.UNIVERSAL_SMUSHING,
        codeTagCount: int = 0,
        hardBlank: str = "$",
        endMark: str = "@",
        caseInsensitive: bool = False,
    ) -> None:
        """Creates a new FIGletFontWriter.

        All parameters are optional, and can be set later.
        Validation is performed at construction and when createFigFileData() is called.

        Args:
            figChars (dict[int, str], optional): Dictionary that maps character codes to FIGcharacter strings. Defaults to {}.
            height (int, optional): Height of a FIGcharacter, in sub-characters. Defaults to None, auto-calculated.
            baseline (int, optional): Distance from the top of the FIGcharacter to the baseline. If not specified, defaults to height. Defaults to None.
            maxLength (int, optional): Maximum length of a line INCLUDING two endMark characters. Defaults to None, auto-calculated.
            commentLines (list[str], optional): List of lines of informational text to be included in the header. It's recommended to include at least the name of the font and the name of the author. Defaults to [].
            rightToLeft (bool, optional): Indicates RTL writing direction. Defaults to False.
            horizontalLayout (FIGletFontWriter.Layout, optional): controls FIGcharacter spacing. Defaults to Layout.UNIVERSAL_SMUSHING.
            verticalLayout (FIGletFontWriter.Layout, optional): controls FIGcharacter spacing. Defaults to Layout.UNIVERSAL_SMUSHING.
            codeTagCount (int, optional): Number of extra FIGcharacters included in the font (in addition to the required 102 untagged characters). Outputting tagged characters is not yet supported. Defaults to 0.
            hardBlank (str, optional): Character rendered as a space which can prevent smushing. Defaults to "$".
            endMark (str, optional): Character used to mark the end of a line. Defaults to "@".
            caseInsensitive (bool, optional): Overwrites lowercase with copies of uppercase. Defaults to False.

        Raises:
            ValueError: If any of the parameters are invalid.
        """

        self.figChars: dict[int, str] = figChars
        """Dictionary that maps character codes to FIGcharacter strings."""
        
        self.height = height
        """Height of a FIGcharacter, in sub-characters."""
        
        self.baseline = baseline
        """Distance from the top of the FIGcharacter to the baseline. If not specified, defaults to height."""
        
        self.maxLength = maxLength
        """Maximum length of a line INCLUDING two endMark characters."""
        
        self.commentLines: list[str] = commentLines
        """List of comment lines to be included in the header. It's recommended to include at least the name of the font and the name of the author."""
        
        self.rightToLeft = rightToLeft
        """Indicates RTL writing direction (or LTR if False)."""
        
        self.codeTagCount = codeTagCount
        """Number of extra FIGcharacters included in the font (in addition to the required 102 untagged characters). Outputting tagged characters is not yet supported."""
        
        self.hardBlank = hardBlank
        """Character rendered as a space which can prevent smushing."""
        
        self.endMark = endMark
        """Denotes the end of a line. Two of these characters in a row denotes the end of a FIGcharacter."""
        
        self.horizontalLayout = horizontalLayout
        """Defines how FIGcharacters are spaced horizontally."""
        
        self.verticalLayout = verticalLayout
        """Defines how FIGcharacters are spaced vertically."""
        
        self.hRule = [False] * 7
        """Horizontal Smushing Rules, 1-6 (0 is not used, so that indices correspond with the names of the parameters).
        
        horizontalLayout must be Layout.CONTROLLED_SMUSHING for these to take effect."""
        
        self.vRule = [False] * 6
        """Vertical Smushing Rules, 1-5 (0 is not used, so that indices correspond with the names of the parameters).
        
        verticalLayout must be Layout.CONTROLLED_SMUSHING for these to take effect."""
        
        self.caseInsensitive = caseInsensitive
        """Makes lowercase same as uppercase. Note that this is one-way overwrite. It doesn't check if a character already exists, and it won't fill in uppercase using lowercase."""

        self._validateOptions()
    
    def _validateOptions(self) -> None:
        """Called on init and before generating a font file.
        
        See also _fixFigChars() which actively fixes things.
        """
        # Check enums
        if self.horizontalLayout not in [val for val in self.Layout]:
            raise ValueError(f"Invalid horizontalLayout: {repr(self.horizontalLayout)} ({type(self.horizontalLayout)})")
        if self.verticalLayout not in [val for val in self.Layout]:
            raise ValueError(f"Invalid verticalLayout: {repr(self.verticalLayout)} ({type(self.verticalLayout)})")
        # Check sentinel values
        if self.hardBlank == self.endMark:
            raise ValueError(f"hardBlank and endMark cannot be the same character: {repr(self.hardBlank)}")
        if len(self.endMark) != 1:
            raise ValueError(f"endMark must be a single character: {repr(self.endMark)}")
        if len(self.hardBlank) != 1:
            raise ValueError(f"hardBlank must be a single character: {repr(self.hardBlank)}")
        # Check there's no newlines in the comment lines
        for line in self.commentLines:
            if "\n" in line:
                raise ValueError(f"Strings in commentLines cannot contain newlines: {repr(line)}")
        # Check codeTagCount
        if self.codeTagCount != 0:
            raise NotImplementedError("codeTagCount is not yet supported")

    def _getOldLayoutValue(self) -> int:
        val = 0
        if self.horizontalLayout == self.Layout.FULL:
            return -1
        elif self.horizontalLayout == self.Layout.FITTED:
            return 0
        elif self.horizontalLayout == self.Layout.UNIVERSAL_SMUSHING:
            return 0
        else:
            val += 1 if self.hRule[1] else 0
            val += 2 if self.hRule[2] else 0
            val += 4 if self.hRule[3] else 0
            val += 8 if self.hRule[4] else 0
            val += 16 if self.hRule[5] else 0
            val += 32 if self.hRule[6] else 0
        return val

    def _getFullLayoutValue(self) -> int:
        val = 0

        # horizontal rules
        if self.horizontalLayout == self.Layout.FULL:
            val += 0
        elif self.horizontalLayout == self.Layout.FITTED:
            val += 64
        elif self.horizontalLayout == self.Layout.UNIVERSAL_SMUSHING:
            val += 128
        else:
            val += 128
            val += 1 if self.hRule[1] else 0
            val += 2 if self.hRule[2] else 0
            val += 4 if self.hRule[3] else 0
            val += 8 if self.hRule[4] else 0
            val += 16 if self.hRule[5] else 0
            val += 32 if self.hRule[6] else 0

        # vertical rules
        if self.verticalLayout == self.Layout.FULL:
            val += 0
        elif self.verticalLayout == self.Layout.FITTED:
            val += 8192
        elif self.verticalLayout == self.Layout.UNIVERSAL_SMUSHING:
            val += 16384
        else:
            val += 16384
            val += 256 if self.vRule[1] else 0
            val += 512 if self.vRule[2] else 0
            val += 1024 if self.vRule[3] else 0
            val += 2048 if self.vRule[4] else 0
            val += 4096 if self.vRule[5] else 0

        return val

    def _generateFigFontHeader(self) -> str:
        header: list[str] = []
        baseline = self.baseline

        if self.height is None:
            raise ValueError("Height must be specified, or should be automatically determined.")
        if baseline is None:
            baseline = self.height
        baseline = int(baseline)
        if baseline <= 0 or baseline > self.height:
            baseline = self.height

        header.append('flf2a' + self.hardBlank)
        header.append(str(self.height))
        header.append(str(baseline))
        header.append(str(self.maxLength))
        header.append(str(self._getOldLayoutValue()))
        header.append(str(len(self.commentLines)))
        header.append("1" if self.rightToLeft else "0")
        header.append(str(self._getFullLayoutValue()))
        header.append(str(self.codeTagCount))

        return ' '.join(header)

    def _fixFigChars(self) -> None:
        # Height must be constant for all FIGcharacters.
        # Width can vary, but must be consistent for all rows within a FIGcharacter.
        height = 0
        charWidth: dict[int, int] = {}
        maxWidth = 0

        # Fix case insensitivity
        if self.caseInsensitive is True:
            for ii in range(97, 123):
                self.figChars[ii] = self.figChars[ii - 32]

        # Calculate max height and ensure consistent width for each FIGcharacter
        for idx in self.figChars:
            figChar = self.figChars[idx].replace('\r\n', '\n').split('\n')
            height = max(height, len(figChar))
            charWidth[idx] = 0

            for line in figChar:
                charWidth[idx] = max(charWidth[idx], len(line))

            for i in range(len(figChar)):
                if len(figChar[i]) < charWidth[idx]:
                    figChar[i] += ' ' * (charWidth[idx] - len(figChar[i]))

                maxWidth = max(maxWidth, charWidth[idx])

            self.figChars[idx] = '\n'.join(figChar)

        # Fix any height issues
        for idx in self.figChars:
            figChar = self.figChars[idx].replace('\r\n', '\n').split('\n')
            if len(figChar) < height:
                blankLines = [' ' * charWidth[idx] for _ in range(height - len(figChar))]
                self.figChars[idx] = '\n'.join(figChar) + '\n' + '\n'.join(blankLines)

        self.height = height
        self.maxLength = maxWidth + 2 # Two end marks signify end of FIGcharacter

    def createFigFileData(self) -> str:
        """Generates the FIGlet file data for the current font."""
        self._validateOptions()
        self._fixFigChars()

        output = self._generateFigFontHeader() + '\n'
        output += "\n".join(self.commentLines) + '\n'

        for char in self.charOrder:
            figChar = self.figChars.get(char)
            if figChar is None:
                raise Exception(f"Character {char} missing from figChars")
            output += (self.endMark + '\n').join(figChar.split('\n'))
            output += self.endMark + self.endMark + '\n'

        return output

__all__ = ["FIGletFontWriter"]
