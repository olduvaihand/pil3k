#
# The Python Imaging Library.
# $Id$
#
# OpenGL pixmap/texture interface (requires imToolkit OpenGL extensions)
#
# History:
# 2003-09-13 fl   Added
#
# Copyright (c) Secret Labs AB 2003.
#
# See the README file for information on usage and redistribution.
#

##
# OpenGL pixmap/texture interface (requires imToolkit OpenGL
# extensions.)
##

import _imaginggl # from pil3k

##
# Texture factory.

class TextureFactory(object):
    pass # overwritten by the _imaginggl module

from pil3k._imaginggl import *
