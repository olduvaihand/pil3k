#
# The Python Imaging Library.
# $Id$
#
# EPS file handling
#
# History:
# 1995-09-01 fl   Created (0.1)
# 1996-05-18 fl   Don't choke on "atend" fields, Ghostscript interface (0.2)
# 1996-08-22 fl   Don't choke on floating point BoundingBox values
# 1996-08-23 fl   Handle files from Macintosh (0.3)
# 2001-02-17 fl   Use 're' instead of 'regex' (Python 2.1) (0.4)
# 2003-09-07 fl   Check gs.close status (from Federico Di Gregorio) (0.5)
#
# Copyright (c) 1997-2003 by Secret Labs AB.
# Copyright (c) 1995-2003 by Fredrik Lundh
#
# See the README file for information on usage and redistribution.
#

__version__ = "0.5"

import re

import Image # from pil3k
import ImageFile # from pil3k

#
# --------------------------------------------------------------------

def i32(c):
    return c[0] + (c[1]<<8) + (c[2]<<16) + (c[3]<<24)

def o32(i):
    return bytes((i&255, i>>8&255, i>>16&255, i>>24&255))

split = re.compile(br"^%%([^:]*):[ \t]*(.*)[ \t]*$")
field = re.compile(br"^%[%!\w]([^:]*)[ \t]*$")

def Ghostscript(tile, size, fp):
    """Render an image using Ghostscript (Unix only)"""

    # Unpack decoder tile
    decoder, tile, offset, data = tile[0]
    length, bbox = data

    import tempfile
    import os

    file = tempfile.mktemp()

    # Build ghostscript command
    command = ["gs",
               "-q",                            # quite mode
               "-g{0}x{1}".format(*size),       # set output geometry (pixels)
               "-dNOPAUSE -dSAFER",             # don't pause between pages, safe mode
               "-sDEVICE=ppmraw",               # ppm driver
               "-sOutputFile={0}".format(file), # output file
               "- >/dev/null 2>/dev/null"]

    command = ' '.join(command)

    # push data through ghostscript
    try:
        gs = os.popen(command, "w")
        # adjust for image origin
        if bbox[0] != 0 or bbox[1] != 0:
            gs.write("{0} {1} translate\n".format(-bbox[0], -bbox[1]).encode(
                'latin_1', errors='replace'))
        fp.seek(offset)
        while length > 0:
            s = fp.read(8192)
            if not s:
                break
            length = length - len(s)
            gs.write(s)
        status = gs.close()
        if status:
            raise IOError("gs failed (status {0})".format(status))
        im = Image.core.open_ppm(file)
    finally:
        try:
            os.unlink(file)
        except:
            pass

    return im


class PSFile(object):
    """Wrapper that treats either CR or LF as end of line."""

    def __init__(self, fp):
        self.fp = fp
        self.char = None
        
    def __getattr__(self, id):
        v = getattr(self.fp, id)
        setattr(self, id, v)
        return v

    def seek(self, offset, whence=0):
        self.char = None
        self.fp.seek(offset, whence)

    def tell(self):
        pos = self.fp.tell()
        if self.char:
            pos = pos - 1
        return pos

    def readline(self):
        s = b""
        if self.char:
            c = self.char
            self.char = None
        else:
            c = self.fp.read(1)
        while c not in b"\r\n":
            s = s + c
            c = self.fp.read(1)
        if c == b"\r":
            self.char = self.fp.read(1)
            if self.char == b"\n":
                self.char = None
        return s + b"\n"


def _accept(prefix):
    return prefix[:4] == b"%!PS" or i32(prefix) == 0xC6D3D0C5

##
# Image plugin for Encapsulated Postscript.  This plugin supports only
# a few variants of this format.

class EpsImageFile(ImageFile.ImageFile):
    """EPS File Parser for the Python Imaging Library"""

    format = "EPS"
    format_description = "Encapsulated Postscript"

    def _open(self):

        # FIXME: should check the first 512 bytes to see if this
        # really is necessary (platform-dependent, though...)

        fp = PSFile(self.fp)

        # HEAD
        s = fp.read(512)
        if s[:4] == b"%!PS":
            offset = 0
            fp.seek(0, 2)
            length = fp.tell()
        elif i32(s) == 0xC6D3D0C5:
            offset = i32(s[4:])
            length = i32(s[8:])
            fp.seek(offset)
        else:
            raise SyntaxError("not an EPS file")

        fp.seek(offset)

        box = None

        self.mode = "RGB"
        self.size = 1, 1 # FIXME: huh?

        #
        # Load EPS header

        s = fp.readline()

        while s:

            if len(s) > 255:
                raise SyntaxError("not an EPS file")

            if s[-2:] == b'\r\n':
                s = s[:-2]
            elif s[-1:] == b'\n':
                s = s[:-1]

            try:
                m = split.match(s)
            except re.error as v:
                raise SyntaxError("not an EPS file")

            if m:
                k, v = m.group(1, 2)
                self.info[k] = v
                if k == b"BoundingBox":
                    try:
                        # Note: The DSC spec says that BoundingBox
                        # fields should be integers, but some drivers
                        # put floating point values there anyway.
                        box = map(int, map(float, v.split()))
                        self.size = box[2] - box[0], box[3] - box[1]
                        self.tile = [("eps", (0,0) + self.size, offset,
                                      (length, box))]
                    except:
                        pass

            else:

                m = field.match(s)

                if m:
                    k = m.group(1)
                    if k == b"EndComments":
                        break
                    if k[:8] == b"PS-Adobe":
                        self.info[k[:8]] = k[9:]
                    else:
                        self.info[k] = b""
                else:
                    raise IOError("bad EPS header")

            s = fp.readline()

            if s[:1] != b"%":
                break


        #
        # Scan for an "ImageData" descriptor

        while s[0] == b"%":

            if len(s) > 255:
                raise SyntaxError("not an EPS file")

            if s[-2:] == b'\r\n':
                s = s[:-2]
            elif s[-1:] == b'\n':
                s = s[:-1]

            if s[:11] == b"%ImageData:":

                [x, y, bi, mo, z3, z4, en, id] = s[11:].split(maxsplit=7)

                x = int(x)
                y = int(y)

                bi = int(bi)
                mo = int(mo)

                en = int(en)

                if en == 1:
                    decoder = "eps_binary"
                elif en == 2:
                    decoder = "eps_hex"
                else:
                    break
                if bi != 8:
                    break
                if mo == 1:
                    self.mode = "L"
                elif mo == 2:
                    self.mode = "LAB"
                elif mo == 3:
                    self.mode = "RGB"
                else:
                    break

                if id[:1] == id[-1:] == '"':
                    id = id[1:-1]

                # Scan forward to the actual image data
                while True:
                    s = fp.readline()
                    if not s:
                        break
                    if s[:len(id)] == id:
                        self.size = x, y
                        self.tile2 = [(decoder, (0, 0, x, y), fp.tell(), 0)]
                        return

            s = fp.readline()
            if not s:
                break

        if not box:
            raise IOError("cannot determine EPS bounding box")

    def load(self):
        # Load EPS via Ghostscript
        if not self.tile:
            return
        self.im = Ghostscript(self.tile, self.size, self.fp)
        self.mode = self.im.mode
        self.size = self.im.size
        self.tile = []

#
# --------------------------------------------------------------------

def _save(im, fp, filename, eps=1):
    """EPS Writer for the Python Imaging Library."""

    #
    # make sure image data is available
    im.load()

    #
    # determine postscript image mode
    if im.mode == "L":
        operator = (8, 1, "image")
    elif im.mode == "RGB":
        operator = (8, 3, "false 3 colorimage")
    elif im.mode == "CMYK":
        operator = (8, 4, "false 4 colorimage")
    else:
        raise ValueError("image mode is not supported")

    if eps:
        #
        # write EPS header
        fp.write(b"%!PS-Adobe-3.0 EPSF-3.0\n")
        fp.write(b"%%Creator: PIL 0.1 EpsEncode\n")
        #fp.write("%%CreationDate: %s"...)
        fp.write("%%BoundingBox: 0 0 {0[0]} {0[1]}\n".format(im.size).encode(
            'latin_1', errors='replace'))
        fp.write(b"%%Pages: 1\n")
        fp.write(b"%%EndComments\n")
        fp.write(b"%%Page: 1 1\n")
        fp.write("%%ImageData: {0[0]} {0[1]}".format(im.size).encode('latin_1',
            errors='replace'))
        fp.write("{0[0]} {0[1]} 0 1 1 \"{0[2]}\"\n".format(operator).encode(
            'latin_1', errors='replace'))

    #
    # image header
    fp.write(b"gsave\n")
    fp.write(b"10 dict begin\n")
    fp.write("/buf {0} string def\n".format(im.size[0]*operator[1]).encode(
        'latin_1', errors='replace'))
    fp.write("{0[0]} {0[1]} scale\n".format(im.size).encode('latin_1',
        errors='replace'))
    fp.write("{0[0]} {0[1]} 8\n".format(im.size).encode('latin_1',
        errors='replace')) # <= bits
    fp.write("[{0[0]} 0 0 -{0[1]} 0 {0[1]}]\n".format(im.size).encode(
        'latin_1', errors='replace'))
    fp.write(b"{ currentfile buf readhexstring pop } bind\n")
    fp.write("{0[2]}\n".format(operator).encode('latin_1', errors='replace'))

    ImageFile._save(im, fp, [("eps", (0,0)+im.size, 0, None)])

    fp.write(b"\n%%EndBinary\n")
    fp.write(b"grestore end\n")
    fp.flush()

#
# --------------------------------------------------------------------

Image.register_open(EpsImageFile.format, EpsImageFile, _accept)

Image.register_save(EpsImageFile.format, _save)

Image.register_extension(EpsImageFile.format, ".ps")
Image.register_extension(EpsImageFile.format, ".eps")

Image.register_mime(EpsImageFile.format, "application/postscript")
