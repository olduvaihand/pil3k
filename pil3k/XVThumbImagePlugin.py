#
# The Python Imaging Library.
# $Id$
#
# XV Thumbnail file handler by Charles E. "Gene" Cash
# (gcash@magicnet.net)
#
# see xvcolor.c and xvbrowse.c in the sources to John Bradley's XV,
# available from ftp://ftp.cis.upenn.edu/pub/xv/
#
# history:
# 98-08-15 cec  created (b/w only)
# 98-12-09 cec  added color palette
# 98-12-28 fl   added to PIL (with only a few very minor modifications)
#
# To do:
# FIXME: make save work (this requires quantization support)
#

__version__ = "0.1"

import Image # from pil3k
import ImageFile # from pil3k
import ImagePalette # from pil3k

# standard color palette for thumbnails (RGB332)
PALETTE = b''.join(
    bytes(((r*255)//7, (g*255)//7, (b*255)//3))
        for r in range(8) for g in range(8) for b in range(4)
)

##
# Image plugin for XV thumbnail images.

class XVThumbImageFile(ImageFile.ImageFile):

    format = "XVThumb"
    format_description = "XV thumbnail image"

    def _open(self):

        # check magic
        s = self.fp.read(6)
        if s != b"P7 332":
            raise SyntaxError("not an XV thumbnail file")

        # Skip to beginning of next line
        self.fp.readline()

        # skip info comments
        while True:
            s = self.fp.readline()
            if not s:
                raise SyntaxError("Unexpected EOF reading XV thumbnail file")
            if s[0] != b'#':
                break

        # parse header line (already read)
        s = s.strip().split()

        self.mode = "P"
        self.size = s[0], s[1]

        self.palette = ImagePalette.raw("RGB", PALETTE)

        self.tile = [("raw", (0, 0)+self.size, self.fp.tell(),
            (self.mode, 0, 1))]

# --------------------------------------------------------------------

Image.register_open("XVThumb", XVThumbImageFile)
