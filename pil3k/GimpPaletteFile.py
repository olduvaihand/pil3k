#
# Python Imaging Library
# $Id$
#
# stuff to read GIMP palette files
#
# History:
# 1997-08-23 fl     Created
# 2004-09-07 fl     Support GIMP 2.0 palette files.
#
# Copyright (c) Secret Labs AB 1997-2004.  All rights reserved.
# Copyright (c) Fredrik Lundh 1997-2004.
#
# See the README file for information on usage and redistribution.
#

import re

##
# File handler for GIMP's palette format.

class GimpPaletteFile(object):

    rawmode = "RGB"

    def __init__(self, fp):

        self.palette = map(lambda i: bytes((i,)*3), range(256))

        if fp.readline()[:12] != b"GIMP Palette":
            raise SyntaxError("not a GIMP palette file")

        i = 0

        while i <= 255:

            s = fp.readline()

            if not s:
                break
            # skip fields and comment lines
            if re.match(br"\w+:|#", s):
                continue
            if len(s) > 100:
                raise SyntaxError("bad palette file")

            v = tuple(map(int, s.split()[:3]))
            if len(v) != 3:
                raise ValueError("bad palette entry")

            if 0 <= i <= 255:
                self.palette[i] = bytes(v)

            i = i + 1

        self.palette = b''.join(self.palette)


    def getpalette(self):

        return self.palette, self.rawmode
