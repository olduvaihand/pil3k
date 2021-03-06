#
# The Python Imaging Library.
# $Id$
#
# XBM File handling
#
# History:
# 1995-09-08 fl   Created
# 1996-11-01 fl   Added save support
# 1997-07-07 fl   Made header parser more tolerant
# 1997-07-22 fl   Fixed yet another parser bug
# 2001-02-17 fl   Use 're' instead of 'regex' (Python 2.1) (0.4)
# 2001-05-13 fl   Added hotspot handling (based on code from Bernhard Herzog)
# 2004-02-24 fl   Allow some whitespace before first #define
#
# Copyright (c) 1997-2004 by Secret Labs AB
# Copyright (c) 1996-1997 by Fredrik Lundh
#
# See the README file for information on usage and redistribution.
#

__version__ = "0.6"

import re

import Image # from pil3k
import ImageFile # from pil3k

# XBM header
xbm_head = re.compile(
    br"\s*#define[ \t]+[^_]*_width[ \t]+(?P<width>[0-9]+)[\r\n]+"
    br"#define[ \t]+[^_]*_height[ \t]+(?P<height>[0-9]+)[\r\n]+"
    br"(?P<hotspot>"
    br"#define[ \t]+[^_]*_x_hot[ \t]+(?P<xhot>[0-9]+)[\r\n]+"
    br"#define[ \t]+[^_]*_y_hot[ \t]+(?P<yhot>[0-9]+)[\r\n]+"
    br")?"
    br"[\\000-\\377]*_bits\\[\\]"
)

def _accept(prefix):
    return prefix.lstrip()[:7] == b"#define"

##
# Image plugin for X11 bitmaps.

class XbmImageFile(ImageFile.ImageFile):

    format = "XBM"
    format_description = "X11 Bitmap"

    def _open(self):

        m = xbm_head.match(self.fp.read(512))

        if m:

            xsize = int(m.group("width"))
            ysize = int(m.group("height"))

            if m.group("hotspot"):
                self.info["hotspot"] = (
                    int(m.group("xhot")), int(m.group("yhot"))
                    )

            self.mode = "1"
            self.size = xsize, ysize

            self.tile = [("xbm", (0, 0)+self.size, m.end(), None)]


def _save(im, fp, filename):

    if im.mode != "1":
        raise IOError("cannot write mode {0} as XBM".format(im.mode))

    data = []

    data.append("#define im_width {0}\n".format(im.size[0]))
    data.append("#define im_height {0}\n".format(im.size[1]))

    hotspot = im.encoderinfo.get("hotspot")
    if hotspot:
        data.append("#define im_x_hot {0}\n".format(hotspot[0]))
        data.append("#define im_y_hot {0}\n".format(hotspot[1]))

    data.append("static char im_bits[] = {\n")

    data = ''.join(data).encode('latin_1', errors='replace')

    ImageFile._save(im, fp, [("xbm", (0,0)+im.size, 0, None)])

    fp.write(b"};\n")


Image.register_open("XBM", XbmImageFile, _accept)
Image.register_save("XBM", _save)

Image.register_extension("XBM", ".xbm")

Image.register_mime("XBM", "image/xbm")
