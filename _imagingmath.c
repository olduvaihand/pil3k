/*
 * The Python Imaging Library
 *
 * a simple math add-on for the Python Imaging Library
 *
 * history:
 * 1999-02-15 fl   Created
 * 2005-05-05 fl   Simplified and cleaned up for PIL 1.1.6
 *
 * Copyright (c) 1999-2005 by Secret Labs AB
 * Copyright (c) 2005 by Fredrik Lundh
 *
 * See the README file for information on usage and redistribution.
 */

#include "Python.h"

#include "Imaging.h"

#include "math.h"
#include "float.h"

#define MAX_INT32 2147483647.0
#define MIN_INT32 -2147483648.0

#if defined(_MSC_VER) && _MSC_VER < 1500
#define powf(a, b) ((float)pow((double)(a), (double)(b)))
#endif

#define UNOP(name, op, type)\
void\
name(Imaging out, Imaging im1)\
{\
    int x, y;\
    \
    for (y = 0; y < out->ysize; y++) {\
        type* p0 = (type*)out->image[y];\
        type* p1 = (type*)im1->image[y];\
        for (x = 0; x < out->xsize; x++) {\
            *p0 = op(type, *p1);\
            p0++; p1++;\
        }\
    }\
}

#define BINOP(name, op, type)\
void\
name(Imaging out, Imaging im1, Imaging im2)\
{\
    int x, y;\
    \
    for (y = 0; y < out->ysize; y++) {\
        type* p0 = (type*)out->image[y];\
        type* p1 = (type*)im1->image[y];\
        type* p2 = (type*)im2->image[y];\
        for (x = 0; x < out->xsize; x++) {\
            *p0 = op(type, *p1, *p2);\
            p0++; p1++; p2++;\
        }\
    }\
}

#define NEG(type, v1) -(v1)
#define INVERT(type, v1) ~(v1)

#define ADD(type, v1, v2) (v1)+(v2)
#define SUB(type, v1, v2) (v1)-(v2)
#define MUL(type, v1, v2) (v1)*(v2)

#define MIN(type, v1, v2) ((v1)<(v2))?(v1):(v2)
#define MAX(type, v1, v2) ((v1)>(v2))?(v1):(v2)

#define AND(type, v1, v2) (v1)&(v2)
#define OR(type, v1, v2) (v1)|(v2)
#define XOR(type, v1, v2) (v1)^(v2)
#define LSHIFT(type, v1, v2) (v1)<<(v2)
#define RSHIFT(type, v1, v2) (v1)>>(v2)

#define ABS_I(type, v1) abs((v1))
#define ABS_F(type, v1) fabs((v1))

/* --------------------------------------------------------------------
 * some day, we should add FPE protection mechanisms.  see pyfpe.h for
 * details.
 *   
 * PyFPE_START_PROTECT("Error in foobar", return 0)
 * PyFPE_END_PROTECT(result)
 */

#define DIV_I(type, v1, v2) ((v2)!=0)?(v1)/(v2):0
#define DIV_F(type, v1, v2) ((v2)!=0.0F)?(v1)/(v2):0.0F

#define MOD_I(type, v1, v2) ((v2)!=0)?(v1)%(v2):0
#define MOD_F(type, v1, v2) ((v2)!=0.0F)?fmod((v1),(v2)):0.0F

static int powi(int x, int y)
{
    double v = pow(x, y) + 0.5;

    if (errno == EDOM)
        return 0;

    if (v < MIN_INT32)
        v = MIN_INT32;
    else if (v > MAX_INT32)
        v = MAX_INT32;

    return (int)v;
}

#define POW_I(type, v1, v2) powi(v1, v2)
#define POW_F(type, v1, v2) powf(v1, v2) /* FIXME: EDOM handling */

#define DIFF_I(type, v1, v2) abs((v1)-(v2))
#define DIFF_F(type, v1, v2) fabs((v1)-(v2))

#define EQ(type, v1, v2) (v1)==(v2)
#define NE(type, v1, v2) (v1)!=(v2)
#define LT(type, v1, v2) (v1)<(v2)
#define LE(type, v1, v2) (v1)<=(v2)
#define GT(type, v1, v2) (v1)>(v2)
#define GE(type, v1, v2) (v1)>=(v2)

UNOP(abs_I, ABS_I, INT32)
UNOP(neg_I, NEG, INT32)

BINOP(add_I, ADD, INT32)
BINOP(sub_I, SUB, INT32)
BINOP(mul_I, MUL, INT32)
BINOP(div_I, DIV_I, INT32)
BINOP(mod_I, MOD_I, INT32)
BINOP(pow_I, POW_I, INT32)
BINOP(diff_I, DIFF_I, INT32)

UNOP(invert_I, INVERT, INT32)
BINOP(and_I, AND, INT32)
BINOP(or_I, OR, INT32)
BINOP(xor_I, XOR, INT32)
BINOP(lshift_I, LSHIFT, INT32)
BINOP(rshift_I, RSHIFT, INT32)

BINOP(min_I, MIN, INT32)
BINOP(max_I, MAX, INT32)

BINOP(eq_I, EQ, INT32)
BINOP(ne_I, NE, INT32)
BINOP(lt_I, LT, INT32)
BINOP(le_I, LE, INT32)
BINOP(gt_I, GT, INT32)
BINOP(ge_I, GE, INT32)

UNOP(abs_F, ABS_F, FLOAT32)
UNOP(neg_F, NEG, FLOAT32)

BINOP(add_F, ADD, FLOAT32)
BINOP(sub_F, SUB, FLOAT32)
BINOP(mul_F, MUL, FLOAT32)
BINOP(div_F, DIV_F, FLOAT32)
BINOP(mod_F, MOD_F, FLOAT32)
BINOP(pow_F, POW_F, FLOAT32)
BINOP(diff_F, DIFF_F, FLOAT32)

BINOP(min_F, MIN, FLOAT32)
BINOP(max_F, MAX, FLOAT32)

BINOP(eq_F, EQ, FLOAT32)
BINOP(ne_F, NE, FLOAT32)
BINOP(lt_F, LT, FLOAT32)
BINOP(le_F, LE, FLOAT32)
BINOP(gt_F, GT, FLOAT32)
BINOP(ge_F, GE, FLOAT32)

static PyObject *
_unop(PyObject* self, PyObject* args)
{
    Imaging out;
    Imaging im1;
    void (*unop)(Imaging, Imaging);
    long op, i0, i1;

    if (!PyArg_ParseTuple(args, "lll", &op, &i0, &i1))
        return NULL;

    out = (Imaging)i0;
    im1 = (Imaging)i1;

    unop = (void*)op;
    
    unop(out, im1);

    Py_RETURN_NONE;
}

static PyObject *
_binop(PyObject* self, PyObject* args)
{
    Imaging out;
    Imaging im1;
    Imaging im2;
    void (*binop)(Imaging, Imaging, Imaging);
    long op, i0, i1, i2;

    if (!PyArg_ParseTuple(args, "llll", &op, &i0, &i1, &i2))
        return NULL;

    out = (Imaging)i0;
    im1 = (Imaging)i1;
    im2 = (Imaging)i2;

    binop = (void*)op;
    
    binop(out, im1, im2);

    Py_RETURN_NONE;
}

static PyMethodDef _functions[] = {
    {"unop", _unop, METH_VARARGS, "FIXME: unop doc string"},
    {"binop", _binop, METH_VARARGS, "FIXME: binop doc string"},
    {NULL, NULL, 0, NULL}    /* sentinel */
};

static void
install(PyObject *d, char* name, void* value)
{
    PyObject *v = PyLong_FromLong((long)value);

    if (!v || PyDict_SetItemString(d, name, v))
        PyErr_Clear();
    Py_XDECREF(v);
}

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_imagingmath",                      /* m_name */
    "FIXME: _imagingmath doc string",    /* m_doc */
    -1,                                  /* m_size */
    _functions,                          /* m_methods */
    NULL,                                /* m_reload */
    NULL,                                /* m_traverse */
    NULL,                                /* m_clear */
    NULL                                 /* m_free */
};

PyMODINIT_FUNC
PyInit__imagingmath(void)
{
    PyObject* module = PyModule_Create(&moduledef);
    PyObject* dict;

    if (module == NULL)
        return NULL;

    dict = PyModule_GetDict(module);

    install(dict, "abs_I", abs_I);
    install(dict, "neg_I", neg_I);
    install(dict, "add_I", add_I);
    install(dict, "sub_I", sub_I);
    install(dict, "diff_I", diff_I);
    install(dict, "mul_I", mul_I);
    install(dict, "div_I", div_I);
    install(dict, "mod_I", mod_I);
    install(dict, "min_I", min_I);
    install(dict, "max_I", max_I);
    install(dict, "pow_I", pow_I);

    install(dict, "invert_I", invert_I);
    install(dict, "and_I", and_I);
    install(dict, "or_I", or_I);
    install(dict, "xor_I", xor_I);
    install(dict, "lshift_I", lshift_I);
    install(dict, "rshift_I", rshift_I);

    install(dict, "eq_I", eq_I);
    install(dict, "ne_I", ne_I);
    install(dict, "lt_I", lt_I);
    install(dict, "le_I", le_I);
    install(dict, "gt_I", gt_I);
    install(dict, "ge_I", ge_I);

    install(dict, "abs_F", abs_F);
    install(dict, "neg_F", neg_F);
    install(dict, "add_F", add_F);
    install(dict, "sub_F", sub_F);
    install(dict, "diff_F", diff_F);
    install(dict, "mul_F", mul_F);
    install(dict, "div_F", div_F);
    install(dict, "mod_F", mod_F);
    install(dict, "min_F", min_F);
    install(dict, "max_F", max_F);
    install(dict, "pow_F", pow_F);

    install(dict, "eq_F", eq_F);
    install(dict, "ne_F", ne_F);
    install(dict, "lt_F", lt_F);
    install(dict, "le_F", le_F);
    install(dict, "gt_F", gt_F);
    install(dict, "ge_F", ge_F);

    return module;
}
