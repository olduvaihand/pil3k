#
# The Python Imaging Library.
# $Id$
#
# PDF (Acrobat) file handling
#
# History:
# 1996-07-16 fl   Created
# 1997-01-18 fl   Fixed header
# 2004-02-21 fl   Fixes for 1/L/CMYK images, etc.
# 2004-02-24 fl   Fixes for 1 and P images.
#
# Copyright (c) 1997-2004 by Secret Labs AB.  All rights reserved.
# Copyright (c) 1996-1997 by Fredrik Lundh.
#
# See the README file for information on usage and redistribution.
#

##
# Image plugin for PDF images (output only).
##

__version__ = "0.4"

import Image, ImageFile
import StringIO


#
# --------------------------------------------------------------------

# object ids:
#  1. catalogue
#  2. pages
#  3. image
#  4. page
#  5. page contents

def _obj(fp, obj, **dict):
    fp.write("{0} 0 obj\n".format(obj))
    if dict:
        fp.write("<<\n")
        for k, v in dict.items():
            if v is not None:
                fp.write("/{0} {1}\n".format(k, v))
        fp.write(">>\n")

def _endobj(fp):
    fp.write("endobj\n")

##
# (Internal) Image save plugin for the PDF format.

def _save(im, fp, filename):
    resolution = im.encoderinfo.get("resolution", 72.0)

    #
    # make sure image data is available
    im.load()

    xref = [0]*(5+1) # placeholders

    fp.write("%PDF-1.2\n")
    fp.write("% created by PIL PDF driver " + __version__ + "\n")

    #
    # Get image characteristics

    width, height = im.size

    # FIXME: Should replace ASCIIHexDecode with RunLengthDecode (packbits)
    # or LZWDecode (tiff/lzw compression).  Note that PDF 1.2 also supports
    # Flatedecode (zip compression).

    bits = 8
    params = None

    if im.mode == "1":
        filter = "/ASCIIHexDecode"
        colorspace = "/DeviceGray"
        procset = "/ImageB" # grayscale
        bits = 1
    elif im.mode == "L":
        filter = "/DCTDecode"
        # params = "<< /Predictor 15 /Columns {0} >>".format(width-2)
        colorspace = "/DeviceGray"
        procset = "/ImageB" # grayscale
    elif im.mode == "P":
        filter = "/ASCIIHexDecode"
        colorspace = "[ /Indexed /DeviceRGB 255 <"
        palette = im.im.getpalette("RGB")
        for i in range(256):
            r = ord(palette[i*3])
            g = ord(palette[i*3+1])
            b = ord(palette[i*3+2])
            colorspace = colorspace + "{0:02x}{1:02x}{2:02x} ".format(r, g, b)
        colorspace = colorspace + "> ]"
        procset = "/ImageI" # indexed color
    elif im.mode == "RGB":
        filter = "/DCTDecode"
        colorspace = "/DeviceRGB"
        procset = "/ImageC" # color images
    elif im.mode == "CMYK":
        filter = "/DCTDecode"
        colorspace = "/DeviceCMYK"
        procset = "/ImageC" # color images
    else:
        raise ValueError("cannot save mode {0}".format(im.mode))

    #
    # catalogue

    xref[1] = fp.tell()
    _obj(fp, 1, Type = "/Catalog",
                Pages = "2 0 R")
    _endobj(fp)

    #
    # pages

    xref[2] = fp.tell()
    _obj(fp, 2, Type = "/Pages",
                Count = 1,
                Kids = "[4 0 R]")
    _endobj(fp)

    #
    # image

    op = StringIO.StringIO()

    if filter == "/ASCIIHexDecode":
        if bits == 1:
            # FIXME: the hex encoder doesn't support packed 1-bit
            # images; do things the hard way...
            data = im.tostring("raw", "1")
            im = Image.new("L", (len(data), 1), None)
            im.putdata(data)
        ImageFile._save(im, op, [("hex", (0,0)+im.size, 0, im.mode)])
    elif filter == "/DCTDecode":
        ImageFile._save(im, op, [("jpeg", (0,0)+im.size, 0, im.mode)])
    elif filter == "/FlateDecode":
        ImageFile._save(im, op, [("zip", (0,0)+im.size, 0, im.mode)])
    elif filter == "/RunLengthDecode":
        ImageFile._save(im, op, [("packbits", (0,0)+im.size, 0, im.mode)])
    else:
        raise ValueError("unsupported PDF filter ({0})".format(filter))

    xref[3] = fp.tell()
    _obj(fp, 3, Type = "/XObject",
                Subtype = "/Image",
                Width = width, # * 72.0 / resolution,
                Height = height, # * 72.0 / resolution,
                Length = len(op.getvalue()),
                Filter = filter,
                BitsPerComponent = bits,
                DecodeParams = params,
                ColorSpace = colorspace)

    fp.write("stream\n")
    fp.write(op.getvalue())
    fp.write("\nendstream\n")

    _endobj(fp)

    #
    # page

    xref[4] = fp.tell()
    _obj(fp, 4)
    fp.write("<<\n"\
             "/Type /Page\n"\
             "/Parent 2 0 R\n"\
             "/Resources <<\n"\
             "/ProcSet [ /PDF {0} ]\n"\
             "/XObject << /image 3 0 R >>\n"\
             ">>\n"\
             "/MediaBox [ 0 0 {1} {2} ]\n"\
             "/Contents 5 0 R\n"\
             ">>\n".format(procset, int(width*72.0/resolution),
                 int(height*72.0/resolution)))
    _endobj(fp)

    #
    # page contents

    op = StringIO.StringIO()

    op.write("q {0} 0 0 {1} 0 0 cm /image Do Q\n".format(
        int(width*72.0/resolution), int(height*72.0/resolution)))

    xref[5] = fp.tell()
    _obj(fp, 5, Length = len(op.getvalue()))

    fp.write("stream\n")
    fp.write(op.getvalue())
    fp.write("\nendstream\n")

    _endobj(fp)

    #
    # trailer
    startxref = fp.tell()
    fp.write("xref\n0 {0}\n0000000000 65535 f \n".format(len(xref)))
    for x in xref[1:]:
        fp.write("{0:010d} 00000 n \n".format(x))
    fp.write("trailer\n<<\n/Size {0}\n/Root 1 0 R\n>>\n".format(len(xref)))
    fp.write("startxref\n{0}\n%%EOF\n".format(startxref))
    fp.flush()

#
# --------------------------------------------------------------------

Image.register_save("PDF", _save)

Image.register_extension("PDF", ".pdf")

Image.register_mime("PDF", "application/pdf")
