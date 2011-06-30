/*
 * PIL FreeType Driver
 *
 * a FreeType 2.X driver for PIL
 *
 * history:
 * 2001-02-17 fl  Created (based on old experimental freetype 1.0 code)
 * 2001-04-18 fl  Fixed some egcs compiler nits
 * 2002-11-08 fl  Added unicode support; more font metrics, etc
 * 2003-05-20 fl  Fixed compilation under 1.5.2 and newer non-unicode builds
 * 2003-09-27 fl  Added charmap encoding support
 * 2004-05-15 fl  Fixed compilation for FreeType 2.1.8
 * 2004-09-10 fl  Added support for monochrome bitmaps
 * 2006-06-18 fl  Fixed glyph bearing calculation
 * 2007-12-23 fl  Fixed crash in family/style attribute fetch
 * 2008-01-02 fl  Handle Unicode filenames properly
 *
 * Copyright (c) 1998-2007 by Secret Labs AB
 */

#include "Python.h"
#include "Imaging.h"

#if !defined(USE_FREETYPE_2_0)
/* undef/comment out to use freetype 2.0 */
#define USE_FREETYPE_2_1
#endif

#if defined(USE_FREETYPE_2_1)
/* freetype 2.1 and newer */
#include <ft2build.h>
#include FT_FREETYPE_H
#else
/* freetype 2.0 */
#include <freetype/freetype.h>
#endif

#if !defined(FT_LOAD_TARGET_MONO)
#define FT_LOAD_TARGET_MONO  FT_LOAD_MONOCHROME
#endif

/* -------------------------------------------------------------------- */
/* error table */

#undef FTERRORS_H
#undef __FTERRORS_H__

#define FT_ERRORDEF( e, v, s ) { e, s },
#define FT_ERROR_START_LIST  {
#define FT_ERROR_END_LIST    { 0, 0 } };

struct {
    int code;
    const char* message;
} ft_errors[] =

#include <freetype/fterrors.h>

/* -------------------------------------------------------------------- */
/* font objects */

static FT_Library library;

typedef struct {
    PyObject_HEAD
    FT_Face face;
} FontObject;

staticforward PyTypeObject Font_Type;

/* round a 26.6 pixel coordinate to the nearest larger integer */
#define PIXEL(x) ((((x)+63) & -64)>>6)

static PyObject*
geterror(int code)
{
    int i;

    for (i = 0; ft_errors[i].message; i++)
        if (ft_errors[i].code == code) {
            PyErr_SetString(PyExc_IOError, ft_errors[i].message);
            return NULL;
        }

    PyErr_SetString(PyExc_IOError, "unknown freetype error");
    return NULL;
}

static PyObject*
getfont(PyObject* self_, PyObject* args, PyObject* kw)
{
    /* create a font object from a file name and a size (in pixels) */

    FontObject* self;
    int error;
    char* filename;
    int size;
    int index = 0;
    unsigned char* encoding = NULL;
    static char* kwlist[] = {
        "filename", "size", "index", "encoding", NULL
    };

    if (!PyArg_ParseTupleAndKeywords(args, kw, "eti|is", kwlist,
           Py_FileSystemDefaultEncoding, &filename, &size, &index, &encoding))
        return NULL;

    if (!library) {
        PyErr_SetString(PyExc_IOError, "failed to initialize FreeType library");
        return NULL;
    }

    self = PyObject_New(FontObject, &Font_Type);
    if (!self)
        return NULL;

    error = FT_New_Face(library, filename, index, &self->face);

    if (!error)
        error = FT_Set_Pixel_Sizes(self->face, 0, size);

    if (!error && encoding && strlen((char*)encoding) == 4) {
        FT_Encoding encoding_tag = FT_MAKE_TAG(
            encoding[0], encoding[1], encoding[2], encoding[3]
            );
        error = FT_Select_Charmap(self->face, encoding_tag);
    }

    if (error) {
        PyObject_Del(self);
        return geterror(error);
    }

    return (PyObject*)self;
}
    
static int
font_getchar(PyObject* string, int index, FT_ULong* char_out)
{
    if (PyUnicode_Check(string)) {
        Py_UNICODE* p = PyUnicode_AS_UNICODE(string);
        int size = PyUnicode_GET_SIZE(string);

        if (index >= size)
            return 0;
        *char_out = p[index];
        return 1;
    }
    return 0;
}

static PyObject*
font_getsize(FontObject* self, PyObject* args)
{
    int i, x;
    FT_ULong ch;
    FT_Face face;
    int xoffset;
    FT_Bool kerning = FT_HAS_KERNING(self->face);
    FT_UInt last_index = 0;

    /* calculate size and bearing for a given string */

    PyObject* string;
    if (!PyArg_ParseTuple(args, "O:getsize", &string))
        return NULL;

    if (!PyUnicode_Check(string)) {
        PyErr_SetString(PyExc_TypeError, "expected string");
        return NULL;
    }

    face = NULL;
    xoffset = 0;

    for (x = i = 0; font_getchar(string, i, &ch); i++) {
        int index, error;
        face = self->face;
        index = FT_Get_Char_Index(face, ch);
        if (kerning && last_index && index) {
            FT_Vector delta;
            FT_Get_Kerning(self->face, last_index, index, ft_kerning_default,
                           &delta);
            x += delta.x;
        }
        error = FT_Load_Glyph(face, index, FT_LOAD_DEFAULT);
        if (error)
            return geterror(error);
        if (i == 0)
            xoffset = face->glyph->metrics.horiBearingX;
        x += face->glyph->metrics.horiAdvance;
        last_index = index;
    }

    if (face) {
        int offset;
        /* left bearing */
        if (xoffset < 0)
            x -= xoffset;
        else
            xoffset = 0;
        /* right bearing */
        offset = face->glyph->metrics.horiAdvance -
            face->glyph->metrics.width -
            face->glyph->metrics.horiBearingX;
        if (offset < 0)
            x -= offset;
    }

    return Py_BuildValue("(ii)(ii)", PIXEL(x),
            PIXEL(self->face->size->metrics.height), PIXEL(xoffset), 0);
}

static PyObject*
font_getabc(FontObject* self, PyObject* args)
{
    FT_ULong ch;
    FT_Face face;
    double a, b, c;
    /* calculate ABC values for a given string */
    PyObject* string;

    if (!PyArg_ParseTuple(args, "O:getabc", &string))
        return NULL;

    if (!PyUnicode_Check(string)) {
        PyErr_SetString(PyExc_TypeError, "expected string");
        return NULL;
    }

    if (font_getchar(string, 0, &ch)) {
        int index, error;

        face = self->face;
        index = FT_Get_Char_Index(face, ch);
        error = FT_Load_Glyph(face, index, FT_LOAD_DEFAULT);
        if (error)
            return geterror(error);
        a = face->glyph->metrics.horiBearingX / 64.0;
        b = face->glyph->metrics.width / 64.0;
        c = (face->glyph->metrics.horiAdvance - 
             face->glyph->metrics.horiBearingX -
             face->glyph->metrics.width) / 64.0;
    } else
        a = b = c = 0.0;

    return Py_BuildValue("ddd", a, b, c);
}

static PyObject*
font_render(FontObject* self, PyObject* args)
{
    int i, x, y;
    Imaging im;
    int index, error, ascender;
    int load_flags;
    unsigned char *source;
    FT_ULong ch;
    FT_GlyphSlot glyph;
    FT_Bool kerning = FT_HAS_KERNING(self->face);
    FT_UInt last_index = 0;
    /* render string into given buffer (the buffer *must* have
       the right size, or this will crash) */
    PyObject* string;
    long id;
    int mask = 0;

    if (!PyArg_ParseTuple(args, "Ol|i:render", &string, &id, &mask))
        return NULL;

    if (!PyUnicode_Check(string)) {
        PyErr_SetString(PyExc_TypeError, "expected string");
        return NULL;
    }

    im = (Imaging)id;

    load_flags = FT_LOAD_RENDER;
    if (mask)
        load_flags |= FT_LOAD_TARGET_MONO;

    for (x = i = 0; font_getchar(string, i, &ch); i++) {
        if (i == 0 && self->face->glyph->metrics.horiBearingX < 0)
            x = -PIXEL(self->face->glyph->metrics.horiBearingX);
        index = FT_Get_Char_Index(self->face, ch);
        if (kerning && last_index && index) {
            FT_Vector delta;
            FT_Get_Kerning(self->face, last_index, index, ft_kerning_default,
                           &delta);
            x += delta.x >> 6;
        }
        error = FT_Load_Glyph(self->face, index, load_flags);
        if (error)
            return geterror(error);
        glyph = self->face->glyph;
        if (mask) {
            /* use monochrome mask (on palette images, etc) */
            int xx, x0, x1;
            source = (unsigned char*)glyph->bitmap.buffer;
            ascender = PIXEL(self->face->size->metrics.ascender);
            xx = x + glyph->bitmap_left;
            x0 = 0;
            x1 = glyph->bitmap.width;
            if (xx < 0)
                x0 = -xx;
            if (xx + x1 > im->xsize)
                x1 = im->xsize - xx;
            for (y = 0; y < glyph->bitmap.rows; y++) {
                int yy = y + ascender - glyph->bitmap_top;
                if (yy >= 0 && yy < im->ysize) {
                    /* blend this glyph into the buffer */
                    unsigned char *target = im->image8[yy] + xx;
                    int i, j, m = 128;
                    for (i = j = 0; j < x1; j++) {
                        if (j >= x0 && (source[i] & m))
                            target[j] = 255;
                        if (!(m >>= 1)) {
                            m = 128;
                            i++;
                        }
                    }
                }
                source += glyph->bitmap.pitch;
            }
        } else {
            /* use antialiased rendering */
            int xx, x0, x1;
            source = (unsigned char*)glyph->bitmap.buffer;
            ascender = PIXEL(self->face->size->metrics.ascender);
            xx = x + glyph->bitmap_left;
            x0 = 0;
            x1 = glyph->bitmap.width;
            if (xx < 0)
                x0 = -xx;
            if (xx + x1 > im->xsize)
                x1 = im->xsize - xx;
            for (y = 0; y < glyph->bitmap.rows; y++) {
                int yy = y + ascender - glyph->bitmap_top;
                if (yy >= 0 && yy < im->ysize) {
                    /* blend this glyph into the buffer */
                    int i;
                    unsigned char *target = im->image8[yy] + xx;
                    for (i = x0; i < x1; i++) {
                        if (target[i] < source[i])
                            target[i] = source[i];
                    }
                }
                source += glyph->bitmap.pitch;
            }
        }
        x += PIXEL(glyph->metrics.horiAdvance);
        last_index = index;
    }

    Py_RETURN_NONE;
}

static void
font_dealloc(FontObject* self)
{
    FT_Done_Face(self->face);
    PyObject_Del(self);
}

static PyMethodDef font_methods[] = {
    {"render", (PyCFunction)font_render, METH_VARARGS,
        "FIXME: font_render doc string"},
    {"getsize", (PyCFunction)font_getsize, METH_VARARGS,
        "FIXME: font_getsize doc string"},
    {"getabc", (PyCFunction)font_getabc, METH_VARARGS,
        "FIXME: font_getabc doc string"},
    {NULL, NULL, 0, NULL}    /* sentinel */
};

static PyObject*  
font_getattro(FontObject* self, PyObject* name)
{
    PyObject* res;

    res = PyObject_GenericGetAttr((PyObject*)self, name);

    if (res)
        return res;

    PyErr_Clear();

    /* attributes */
    if (!strcmp(name, "family")) {
        if (self->face->family_name)
            return PyUnicode_FromString(self->face->family_name);
        Py_RETURN_NONE;
    }
    if (!strcmp(name, "style")) {
        if (self->face->style_name)
            return PyUnicode_FromString(self->face->style_name);
        Py_RETURN_NONE;
    }
    if (!strcmp(name, "ascent"))
        return PyLong_FromLong(PIXEL(self->face->size->metrics.ascender));
    if (!strcmp(name, "descent"))
        return PyLong_FromLong(-PIXEL(self->face->size->metrics.descender));

    if (!strcmp(name, "glyphs"))
        /* number of glyphs provided by this font */
        return PyLong_FromLong(self->face->num_glyphs);

    PyErr_SetString(PyExc_AttributeError, name);
    return NULL;
}

statichere PyTypeObject Font_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Font",                                  /* tp_name */
    sizeof(FontObject),                      /* tp_basicsize */
    0,                                       /* tp_itemsize */
    (destructor)font_dealloc,                /* tp_dealloc */
    0,                                       /* tp_print */
    0,                                       /* tp_getattr */
    0,                                       /* tp_setattr */
    0,                                       /* tp_reserved */
    0,                                       /* tp_repr */
    0,                                       /* tp_as_number */
    0,                                       /* tp_as_sequence */
    0,                                       /* tp_as_mapping */
    0,                                       /* tp_hash */
    0,                                       /* tp_call */
    0,                                       /* tp_str */
    (getattrofunc)font_getattro,             /* tp_getattro */
};

static PyMethodDef _functions[] = {
    {"getfont", (PyCFunction)getfont, METH_VARARGS|METH_KEYWORDS,
        "FIXME: getfont doc string"},
    {NULL, NULL, 0, NULL}   /* sentinel */
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_imagingft",           /* m_name */
    "FIXME: doc string",    /* m_doc */
    -1,                     /* m_size */
    _functions,             /* m_methods */
    NULL,                   /* m_reload */
    NULL,                   /* m_traverse */
    NULL,                   /* m_clear */
    NULL                    /* m_free */
};

PyMODINIT_FUNC
PyInit__imagingft(PyObject*)
{
    PyObject* module = PyModule_Create(&moduledef);
    PyObject* dict;
    PyObject* value;

    if (module == NULL)
        return NULL;

    int major, minor, patch;

    /* Patch object type */
    Font_Type.tp_new = PyType_GenericNew;
    if (PyType_Ready(&Font_Type) < 0)
        return NULL;

    dict = PyModule_GetDict(module);

    if (FT_Init_FreeType(&library))
        return; /* leave it uninitalized */

    FT_Library_Version(library, &major, &minor, &patch);

    value = PyUnicode_FromFormat("%d.%d.%d", major, minor, patch);
    PyDict_SetItemString(dict, "freetype2_version", value);

    return module;
}
