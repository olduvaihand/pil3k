#
# THIS IS WORK IN PROGRESS
#
# The Python Imaging Library.
# $Id$
#
# ARG animation support code
#
# history:
# 1996-12-30 fl   Created
# 1996-01-06 fl   Added safe scripting environment
# 1996-01-10 fl   Added JHDR, UHDR and sYNC support
# 2005-03-02 fl   Removed AAPP and ARUN support
#
# Copyright (c) Secret Labs AB 1997.
# Copyright (c) Fredrik Lundh 1996-97.
#
# See the README file for information on usage and redistribution.
#

__version__ = "0.4"

import Image # from pil3k
import ImageFile # from pil3k
import ImagePalette # from pil3k

from pil3k.PngImagePlugin import i16, i32, ChunkStream, _MODES

MAGIC = b"\x8aARG\r\n\x1a\n"

# --------------------------------------------------------------------
# ARG parser

class ArgStream(ChunkStream):
    "Parser callbacks for ARG data"

    def __init__(self, fp):

        ChunkStream.__init__(self, fp)

        self.eof = 0
        self.im = None
        self.palette = None

        self.__reset()

    def __reset(self):

        # reset decoder state (called on init and sync)

        self.count = 0
        self.id = None
        self.action = (b"NONE",)

        self.images = {}
        self.names = {}


    def chunk_AHDR(self, offset, nbytes):
        "AHDR -- animation header"

        # assertions
        if self.count != 0:
            raise SyntaxError("misplaced AHDR chunk")

        s = self.fp.read(nbytes)
        self.size = i32(s), i32(s[4:])
        try:
            self.mode, self.rawmode = _MODES[(s[8], s[9])]
        except:
            raise SyntaxError("unknown ARG mode")

        if Image.DEBUG:
            print("AHDR size", self.size)
            print("AHDR mode", self.mode, self.rawmode)

        return s

    def chunk_AFRM(self, offset, nbytes):
        "AFRM -- next frame follows"

        # assertions
        if self.count != 0:
            raise SyntaxError("misplaced AFRM chunk")

        self.show = 1
        self.id = 0
        self.count = 1
        self.repair = None

        s = self.fp.read(nbytes)
        if len(s) >= 2:
            self.id = i16(s)
            if len(s) >= 4:
                self.count = i16(s[2:4])
                if len(s) >= 6:
                    self.repair = i16(s[4:6])
                else:
                    self.repair = None

        if Image.DEBUG:
            print("AFRM", self.id, self.count)

        return s

    def chunk_ADEF(self, offset, nbytes):
        "ADEF -- store image"

        # assertions
        if self.count != 0:
            raise SyntaxError("misplaced ADEF chunk")

        self.show = 0
        self.id = 0
        self.count = 1
        self.repair = None

        s = self.fp.read(nbytes)
        if len(s) >= 2:
            self.id = i16(s)
            if len(s) >= 4:
                self.count = i16(s[2:4])

        if Image.DEBUG:
            print("ADEF", self.id, self.count)

        return s

    def chunk_NAME(self, offset, nbytes):
        "NAME -- name the current image"

        # assertions
        if self.count == 0:
            raise SyntaxError("misplaced NAME chunk")

        name = self.fp.read(nbytes)
        self.names[self.id] = name

        return name

    def chunk_AEND(self, offset, nbytes):
        "AEND -- end of animation"

        if Image.DEBUG:
            print("AEND")

        self.eof = 1

        raise EOFError("end of ARG file")

    def __getmodesize(self, s, full=1):

        size = i32(s), i32(s[4:])

        try:
            mode, rawmode = _MODES[(s[8], s[9])]
        except:
            raise SyntaxError("unknown image mode")

        if full:
            if s[12]:
                pass # interlace not yet supported
            if s[11]:
                raise SyntaxError("unknown filter category")

        return size, mode, rawmode

    def chunk_PAST(self, offset, nbytes):
        "PAST -- paste one image into another"

        # assertions
        if self.count == 0:
            raise SyntaxError("misplaced PAST chunk")

        if self.repair is not None:
            # we must repair the target image before we
            # start pasting

            # brute force; a better solution would be to
            # update only the dirty rectangles in images[id].
            # note that if images[id] doesn't exist, it must
            # be created

            self.images[self.id] = self.images[self.repair].copy()
            self.repair = None

        s = self.fp.read(nbytes)
        im = self.images[i16(s)]
        x, y = i32(s[2:6]), i32(s[6:10])
        bbox = x, y, im.size[0]+x, im.size[1]+y

        if im.mode in [b"RGBA"]:
            # paste with transparency
            # FIXME: should handle P+transparency as well
            self.images[self.id].paste(im, bbox, im)
        else:
            # paste without transparency
            self.images[self.id].paste(im, bbox)

        self.action = (b"PAST",)
        self.__store()

        return s

    def chunk_BLNK(self, offset, nbytes):
        "BLNK -- create blank image"

        # assertions
        if self.count == 0:
            raise SyntaxError("misplaced BLNK chunk")

        s = self.fp.read(nbytes)
        size, mode, rawmode = self.__getmodesize(s, 0)

        # store image (FIXME: handle colour)
        self.action = (b"BLNK",)
        self.im = Image.core.fill(mode, size, 0)
        self.__store()

        return s

    def chunk_IHDR(self, offset, nbytes):
        "IHDR -- full image follows"

        # assertions
        if self.count == 0:
            raise SyntaxError("misplaced IHDR chunk")

        # image header
        s = self.fp.read(nbytes)
        size, mode, rawmode = self.__getmodesize(s)

        # decode and store image
        self.action = (b"IHDR",)
        self.im = Image.core.new(mode, size)
        self.decoder = Image.core.zip_decoder(rawmode)
        self.decoder.setimage(self.im, (0,0) + size)
        self.data = b""

        return s

    def chunk_DHDR(self, offset, nbytes):
        "DHDR -- delta image follows"

        # assertions
        if self.count == 0:
            raise SyntaxError("misplaced DHDR chunk")

        s = self.fp.read(nbytes)

        size, mode, rawmode = self.__getmodesize(s)

        # delta header
        diff = s[13]
        offs = i32(s[14:18]), i32(s[18:22])

        bbox = offs + (offs[0]+size[0], offs[1]+size[1])

        if Image.DEBUG:
            print("DHDR", diff, bbox)

        # FIXME: decode and apply image
        self.action = (b"DHDR", diff, bbox)

        # setup decoder
        self.im = Image.core.new(mode, size)

        self.decoder = Image.core.zip_decoder(rawmode)
        self.decoder.setimage(self.im, (0,0) + size)

        self.data = b""

        return s

    def chunk_JHDR(self, offset, nbytes):
        "JHDR -- JPEG image follows"

        # assertions
        if self.count == 0:
            raise SyntaxError("misplaced JHDR chunk")

        # image header
        s = self.fp.read(nbytes)
        size, mode, rawmode = self.__getmodesize(s, 0)

        # decode and store image
        self.action = (b"JHDR",)
        self.im = Image.core.new(mode, size)
        self.decoder = Image.core.jpeg_decoder(rawmode)
        self.decoder.setimage(self.im, (0,0) + size)
        self.data = b""

        return s

    def chunk_UHDR(self, offset, nbytes):
        "UHDR -- uncompressed image data follows (EXPERIMENTAL)"

        # assertions
        if self.count == 0:
            raise SyntaxError("misplaced UHDR chunk")

        # image header
        s = self.fp.read(nbytes)
        size, mode, rawmode = self.__getmodesize(s, 0)

        # decode and store image
        self.action = (b"UHDR",)
        self.im = Image.core.new(mode, size)
        self.decoder = Image.core.raw_decoder(rawmode)
        self.decoder.setimage(self.im, (0,0) + size)
        self.data = b""

        return s

    def chunk_IDAT(self, offset, nbytes):
        "IDAT -- image data block"

        # pass compressed chunks through the decoder
        s = self.fp.read(nbytes)
        self.data = self.data + s
        n, e = self.decoder.decode(self.data)
        if n < 0:
            # end of image
            if e < 0:
                raise IOError("decoder error {0}".format(e))
        else:
            self.data = self.data[n:]

        return s

    def chunk_DEND(self, offset, nbytes):
        return self.chunk_IEND(offset, nbytes)

    def chunk_JEND(self, offset, nbytes):
        return self.chunk_IEND(offset, nbytes)

    def chunk_UEND(self, offset, nbytes):
        return self.chunk_IEND(offset, nbytes)

    def chunk_IEND(self, offset, nbytes):
        "IEND -- end of image"

        # we now have a new image.  carry out the operation
        # defined by the image header.

        # won't need these anymore
        del self.decoder
        del self.data

        self.__store()

        return self.fp.read(nbytes)

    def __store(self):

        # apply operation
        cid = self.action[0]

        if cid in [b"BLNK", b"IHDR", b"JHDR", b"UHDR"]:
            # store
            self.images[self.id] = self.im

        elif cid == b"DHDR":
            # paste
            cid, mode, bbox = self.action
            im0 = self.images[self.id]
            im1 = self.im
            if mode == 0:
                im1 = im1.chop_add_modulo(im0.crop(bbox))
            im0.paste(im1, bbox)

        self.count = self.count - 1

        if self.count == 0 and self.show:
            self.im = self.images[self.id]
            raise EOFError() # end of this frame

    def chunk_PLTE(self, offset, nbytes):
        "PLTE -- palette data"

        s = self.fp.read(nbytes)
        if self.mode == "P":
            self.palette = ImagePalette.raw("RGB", s)
        return s

    def chunk_sYNC(self, offset, nbytes):
        "SYNC -- reset decoder"

        if self.count != 0:
            raise SyntaxError("misplaced sYNC chunk")

        s = self.fp.read(nbytes)
        self.__reset()
        return s


# --------------------------------------------------------------------
# ARG reader

def _accept(prefix):
    return prefix[:8] == MAGIC

##
# Image plugin for the experimental Animated Raster Graphics format.

class ArgImageFile(ImageFile.ImageFile):

    format = "ARG"
    format_description = "Animated raster graphics"

    def _open(self):

        if Image.warnings:
            Image.warnings.warn(
                "The ArgImagePlugin driver is obsolete, and will be removed "
                "from a future release of PIL.  If you rely on this module, "
                "please contact the PIL authors.",
                RuntimeWarning
                )

        if self.fp.read(8) != MAGIC:
            raise SyntaxError("not an ARG file")

        self.arg = ArgStream(self.fp)

        # read and process the first chunk (AHDR)

        cid, offset, nbytes = self.arg.read()

        if cid != b"AHDR":
            raise SyntaxError("expected an AHDR chunk")

        s = self.arg.call(cid, offset, nbytes)

        self.arg.crc(cid, s)

        # image characteristics
        self.mode = self.arg.mode
        self.size = self.arg.size

    def load(self):

        if self.arg.im is None:
            self.seek(0)

        # image data
        self.im = self.arg.im
        self.palette = self.arg.palette

        # set things up for further processing
        Image.Image.load(self)

    def seek(self, frame):

        if self.arg.eof:
            raise EOFError("end of animation")

        self.fp = self.arg.fp

        while True:

            #
            # process chunks

            cid, offset, nbytes = self.arg.read()

            if self.arg.eof:
                raise EOFError("end of animation")

            try:
                s = self.arg.call(cid, offset, nbytes)
            except EOFError:
                break

            except AttributeError:
                if Image.DEBUG:
                    print(cid, nbytes, "(unknown)")
                s = self.fp.read(nbytes)

            self.arg.crc(cid, s)

        self.fp.read(4) # ship extra CRC

    def tell(self):
        return 0

    def verify(self):
        "Verify ARG file"

        # back up to first chunk
        self.fp.seek(8)

        self.arg.verify(self)
        self.arg.close()

        self.fp = None

#
# --------------------------------------------------------------------

Image.register_open("ARG", ArgImageFile, _accept)

Image.register_extension("ARG", ".arg")

Image.register_mime("ARG", "video/x-arg")
