#
# Python Imaging Library
# $Id$
#
# stuff to read simple, teragon-style palette files
#
# History:
#       97-08-23 fl     Created
#
# Copyright (c) Secret Labs AB 1997.
# Copyright (c) Fredrik Lundh 1997.
#
# See the README file for information on usage and redistribution.
#

##
# File handler for Teragon-style palette files.

class PaletteFile(object):

    rawmode = "RGB"

    def __init__(self, fp):

        self.palette = map(lambda i: (i, i, i), range(256))

        while True:

            s = fp.readline()

            if not s:
                break
            if s[0] == b"#":
                continue
            if len(s) > 100:
                raise SyntaxError("bad palette file")

            v = map(int, s.split())
            try:
                [i, r, g, b] = v
            except ValueError:
                [i, r] = v
                g = b = r

            if 0 <= i <= 255:
                self.palette[i] = bytes((r, g, b))

        self.palette = b''.join(self.palette)


    def getpalette(self):

        return self.palette, self.rawmode
