from __future__ import absolute_import, division, print_function, with_statement
import sys
import os
import binascii
import array

from cffi import FFI
from cffi.verifier import Verifier

PY3 = sys.version_info >= (3,)
try:
    xrange = range
except:
    pass

include_dir = os.path.split(os.path.realpath(__file__))[0]
ffi = FFI()

def _create_modulename(cdef_sources, source, sys_version):
    """
        This is the same as CFFI's create modulename except we don't include the
        CFFI version.
        """
    key = '\x00'.join([sys_version[:3], source, cdef_sources])
    key = key.encode('utf-8')
    k1 = hex(binascii.crc32(key[0::2]) & 0xffffffff)
    k1 = k1.lstrip('0x').rstrip('L')
    k2 = hex(binascii.crc32(key[1::2]) & 0xffffffff)
    k2 = k2.lstrip('0').rstrip('L')
    return '_Croaring_cffi_{0}{1}'.format(k1, k2)

CDEF="""
typedef struct roaring_array_s {
    int32_t size;
    int32_t allocation_size;
    void **containers;
    uint16_t *keys;
    uint8_t *typecodes;
    uint8_t flags;
} roaring_array_t;

typedef struct roaring_bitmap_s {
    roaring_array_t high_low_container;
} roaring_bitmap_t;

typedef struct roaring_uint32_iterator_s {
    const roaring_bitmap_t *parent;
    int32_t container_index;
    int32_t in_container_index;
    int32_t run_index;
    uint32_t current_value;
    bool has_value;
    const void *container;
    uint8_t typecode;
    uint32_t highbits;
} roaring_uint32_iterator_t;

typedef struct roaring_bulk_context_s {
    void *container;
    int idx;
    uint16_t key;
    uint8_t typecode;
} roaring_bulk_context_t;

roaring_bitmap_t *roaring_bitmap_create_with_capacity(uint32_t cap);

void roaring_bitmap_free(const roaring_bitmap_t *r);

void roaring_bitmap_add(roaring_bitmap_t *r, uint32_t x);

void roaring_bitmap_add_many(roaring_bitmap_t *r, size_t n_args,
                             const uint32_t *vals);

void roaring_bitmap_remove(roaring_bitmap_t *r, uint32_t x);

void roaring_bitmap_remove_many(roaring_bitmap_t *r, size_t n_args,
                                const uint32_t *vals);

bool roaring_bitmap_contains(const roaring_bitmap_t *r, uint32_t val);

uint64_t roaring_bitmap_get_cardinality(const roaring_bitmap_t *r);

size_t roaring_bitmap_portable_size_in_bytes(const roaring_bitmap_t *r);

bool roaring_bitmap_run_optimize(roaring_bitmap_t *r);

size_t roaring_bitmap_shrink_to_fit(roaring_bitmap_t *r);

size_t roaring_bitmap_portable_serialize(const roaring_bitmap_t *r, char *buf);

roaring_bitmap_t *roaring_bitmap_of_ptr(size_t n_args, const uint32_t *vals);

void roaring_bitmap_to_uint32_array(const roaring_bitmap_t *r, uint32_t *ans);

bool roaring_bitmap_equals(const roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

roaring_bitmap_t *roaring_bitmap_or(const roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

void roaring_bitmap_or_inplace(roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

roaring_bitmap_t *roaring_bitmap_or_many(size_t number, const roaring_bitmap_t **rs);

roaring_bitmap_t *roaring_bitmap_or_many_heap(uint32_t number, const roaring_bitmap_t **rs);

roaring_bitmap_t *roaring_bitmap_and(const roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

void roaring_bitmap_and_inplace(roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

roaring_bitmap_t *roaring_bitmap_andnot(const roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

uint64_t roaring_bitmap_andnot_cardinality(const roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

void roaring_bitmap_andnot_inplace(roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

void roaring_bitmap_xor_inplace(roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

roaring_bitmap_t *roaring_bitmap_portable_deserialize_safe(const char *buf, size_t maxbytes);

bool roaring_bitmap_is_subset(const roaring_bitmap_t *r1, const roaring_bitmap_t *r2);

bool roaring_bitmap_intersect(const roaring_bitmap_t *r1, const roaring_bitmap_t *r2);


void roaring_bitmap_add_bulk(roaring_bitmap_t *r, roaring_bulk_context_t *context, uint32_t val);

bool roaring_bitmap_contains_bulk(const roaring_bitmap_t *r,
                                  roaring_bulk_context_t *context,
                                  uint32_t val);


size_t roaring_bitmap_frozen_size_in_bytes(const roaring_bitmap_t *r);

void roaring_bitmap_frozen_serialize(const roaring_bitmap_t *r, char *buf);

const roaring_bitmap_t *roaring_bitmap_frozen_view(const char *buf, size_t length);


roaring_uint32_iterator_t *roaring_create_iterator(const roaring_bitmap_t *r);

bool roaring_advance_uint32_iterator(roaring_uint32_iterator_t *it);

bool roaring_previous_uint32_iterator(roaring_uint32_iterator_t *it);

bool roaring_move_uint32_iterator_equalorlarger(roaring_uint32_iterator_t *it, uint32_t val);

void roaring_free_uint32_iterator(roaring_uint32_iterator_t *it);

uint32_t roaring_read_uint32_iterator(roaring_uint32_iterator_t *it,
                                      uint32_t* buf, uint32_t count);

void *malloc_aligned(size_t size, size_t alignment);
"""

SOURCE = """
#include <roaring.c>
roaring_bitmap_t *roaring_bitmap_and_many(size_t number, const roaring_bitmap_t **x) {
    if (number == 0) {
        return roaring_bitmap_create_with_capacity(0);
    }
    if (number == 1) {
        return roaring_bitmap_copy(x[0]);
    }
    roaring_bitmap_t *answer = roaring_bitmap_copy(x[0]);
    for (size_t i = 2; i < number; i++) {
        roaring_bitmap_and_inplace(answer, x[i]);
    }
    return answer;
}

bool croaring_get_elt(const roaring_bitmap_t *ra, int64_t index, uint32_t *ans){
    uint32_t position = llabs(index);
    if(index == 0){
        *ans = roaring_bitmap_minimum(ra);
        return true;
    }
    else if(index == -1){
        *ans =  roaring_bitmap_maximum(ra);
        return true;
    }
    else if(index < 0){
        position = roaring_bitmap_get_cardinality(ra) + index;
    }
    if(roaring_bitmap_select(ra, position , ans))
         return true;
    return false;
}

roaring_bitmap_t *croaring_union(const roaring_bitmap_t **x, size_t size , bool using_heap) {
    if (size == 0) {
        return roaring_bitmap_create_with_capacity(0);
    }
    if (size == 1) {
        return roaring_bitmap_copy(x[0]);
    }

    if (size == 2) {
        return roaring_bitmap_or(x[0], x[1]);
    }

    if(using_heap)
        return roaring_bitmap_or_many_heap(size, x);
    return roaring_bitmap_or_many(size, x);
}

roaring_bitmap_t *croaring_intersection(const roaring_bitmap_t **x, size_t size) {
    if (size == 0) {
        return roaring_bitmap_create_with_capacity(0);
    }

    if (size == 1) {
        return roaring_bitmap_copy(x[0]);
    }

    if (size == 2) {
        return roaring_bitmap_and(x[0], x[1]);
    }

    return roaring_bitmap_and_many(size, x);
}

size_t
small_align(size_t size, size_t alignment)
{
	return (size - 1 + alignment) & ~(alignment - 1);
}

void *
malloc_aligned(size_t size, size_t alignment)
{
	void *ptr = malloc(size + alignment - 1);
	return (void *)small_align((uintptr_t)ptr, alignment);
}
"""
ffi.cdef(CDEF)
ffi.verifier = Verifier(ffi,
                        SOURCE ,
                        include_dirs=[include_dir],
                        modulename=_create_modulename(CDEF, SOURCE, sys.version),
                        extra_compile_args=['-std=c99','-O3','-msse4.2'])

lib = ffi.verifier.load_library()

class BitSet(object):
    def __init__(self, values=None, croaring = None):
        if croaring:
            assert values is None
            self._croaring = croaring
            return
        elif values is None:
            self._croaring = lib.roaring_bitmap_create_with_capacity(0)
        elif isinstance(values, self.__class__):
            self._croaring = lib.roaring_bitmap_copy(values._croaring)
        elif PY3 and isinstance(values, range):
            _, (start, stop, step) = values.__reduce__()
            if step < 0:
                values = range(min(values), max(values)+1, -step)
                _, (start, stop, step) = values.__reduce__()
            if start >= stop:
                self._croaring = lib.roaring_bitmap_create_with_capacity(0)
            else:
                self._croaring = lib.roaring_bitmap_from_range(start, stop, step)
        elif isinstance(values, array.array):
            address, size = values.buffer_info()
            buffer = ffi.cast("uint32_t*", address)
            self._croaring = lib.roaring_bitmap_of_ptr(size, buffer)
        else:
            self._croaring = lib.roaring_bitmap_create_with_capacity(0)
            self.update(values)

    def update(self, *all_values):
        for values in all_values:
            if isinstance(values, self.__class__):
                self |= values
            elif PY3 and isinstance(values, range):
                self |= self.__class__(values)
            elif isinstance(values, array.array):
                buffer = ffi.cast("uint32_t*", ffi.from_buffer(values))
                lib.roaring_bitmap_add_many(self._croaring, len(values), buffer)
            else:
                lib.roaring_bitmap_add_many(self._croaring, len(values), values)

    def intersection_update(self, *all_values):
        for values in all_values:
            if isinstance(values, self.__class__):
                self &= values
            else:
                self &= self.__class__(values)

    def __repr__(self):
        return str(self)

    def __str__(self):
        values = ', '.join([str(n) for n in self])
        return 'BitSet([%s])' % values

    def __nonzero__(self):
        return not bool(lib.roaring_bitmap_is_empty(self._croaring))

    if PY3:
        __bool__ = __nonzero__
        del __nonzero__

    def __contains__(self, value):
        return bool(lib.roaring_bitmap_contains(self._croaring, value))

    def __iter__(self):
        item_iter = lib.roaring_create_iterator(self._croaring)
        try:
            while item_iter.has_value:
                yield item_iter.current_value
                lib.roaring_advance_uint32_iterator(item_iter)
        finally:
            lib.roaring_free_uint32_iterator(item_iter)

    def __and__(self, other):
        _croaring =  lib.roaring_bitmap_and(self._croaring,  other._croaring)
        return self.__class__(croaring = _croaring)

    def __iand__(self, other):
        lib.roaring_bitmap_and_inplace(self._croaring,  other._croaring)
        return self

    def __or__(self, other):
        _croaring =  lib.roaring_bitmap_or(self._croaring,  other._croaring)
        return self.__class__(croaring = _croaring)

    def __ior__(self, other):
        lib.roaring_bitmap_or_inplace(self._croaring,  other._croaring)
        return self

    def __xor__(self, other):
        _croaring =  lib.roaring_bitmap_xor(self._croaring,  other._croaring)
        return self.__class__(croaring = _croaring)

    def __ixor__(self, other):
        lib.roaring_bitmap_xor_inplace(self._croaring,  other._croaring)
        return self

    def __sub__(self, other):
        _croaring =  lib.roaring_bitmap_andnot(self._croaring,  other._croaring)
        return self.__class__(croaring = _croaring)

    def __isub__(self, other):
        lib.roaring_bitmap_andnot_inplace(self._croaring,  other._croaring)
        return self

    def __add__(self, other):
        return self.__or__(other)

    def __iadd__(self, other):
        return self.__ior__(other)

    def __del__(self):
        if hasattr(self, '_croaring') and self._croaring is not None:
            lib.roaring_bitmap_free(self._croaring)
            del self._croaring

    def _get_elt(self, index):
        out = ffi.new('uint32_t[1]')
        if lib.croaring_get_elt(self._croaring, index, out):
            return out[0]
        else:
            raise IndexError('Index not found %s' % (index))

    def _get_slice(self, sl):
        start, stop, step = sl.indices(len(self))
        sign = 1 if step > 0 else -1
        _croaring = lib.croaring_get_slice(self._croaring, sign , start, stop, step)
        if _croaring == ffi.NULL:
            return self.__class__([elm for elm in self][sl])
        else:
            return self.__class__(croaring = _croaring)

    def __getitem__(self, index):
        if isinstance(index, int):
            return self._get_elt(index)
        elif isinstance(index, slice):
            return self._get_slice(index)
        else:
            return TypeError('Indices must be integers or slices, not %s' % type(index))

    def __richcmp__(self, other, op):
        if op == 0: # <
            return bool(lib.roaring_bitmap_is_strict_subset(self._croaring, other._croaring))
        elif op == 1: # <=
            return bool(lib.roaring_bitmap_is_subset(self._croaring, other._croaring))
        elif op == 2: # ==
            return bool(lib.roaring_bitmap_equals(self._croaring, other._croaring))
        elif op == 3: # !=
            return not (self == other)
        elif op == 4: # >
            return bool(lib.roaring_bitmap_is_strict_subset(self._croaring, other._croaring))
        else:         # >=
            assert op == 5
            return bool(lib.roaring_bitmap_is_subset(self._croaring, other._croaring))

    def __len__(self):
        return lib.roaring_bitmap_get_cardinality(self._croaring)

    def __eq__(self, other):
        return bool(lib.roaring_bitmap_equals(self._croaring, other._croaring))

    def __lt__(self, other):
        return bool(lib.roaring_bitmap_is_strict_subset(self._croaring, other._croaring))

    def __gt__(self, other):
        return other < self

    def __le__(self, other):
        return bool(lib.roaring_bitmap_is_subset(self._croaring, other._croaring))

    def __ge__(self, other):
        return other <= self

    def __copy__(self):
        return self.copy()

    def copy(self):
        return self.__class__(croaring = lib.roaring_bitmap_copy(self._croaring))

    def flip(self, start, end):
        return self.__class__(croaring = lib.roaring_bitmap_flip(self._croaring, ffi.cast("uint64_t",start), ffi.cast("uint64_t", end)))

    def flip_inplace(self, start, end):
        lib.roaring_bitmap_flip(self._croaring, ffi.cast("uint64_t",start), ffi.cast("uint64_t", end))

    def __getstate__(self):
        return self.dumps()

    def __setstate__(self, value):
        inbuf = ffi.new('char[%d]'%(len(value)), value)
        self._croaring = lib.roaring_bitmap_deserialize(inbuf)

    @classmethod
    def union(cls, *bitsets):
        return cls(croaring = lib.croaring_union([b._croaring for b in bitsets] , len(bitsets) , 0))

    @classmethod
    def union_heap(cls, *bitsets):
        return cls(croaring = lib.croaring_union([b._croaring for b in bitsets] , len(bitsets) , 1))

    @classmethod
    def intersection(cls, *bitsets):
        return cls(croaring = lib.croaring_intersection([b._croaring for b in bitsets] , len(bitsets)))

    @classmethod
    def jaccard_index(cls, bitseta, bitsetb):
        return lib.roaring_bitmap_jaccard_index(bitseta._croaring, bitsetb._croaring)

    def union_cardinality(self, other):
        return lib.roaring_bitmap_or_cardinality(self._croaring, other._croaring)

    def intersection_cardinality(self, other):
        return lib.roaring_bitmap_and_cardinality(self._croaring, other._croaring)

    def difference_cardinality(self, other):
        return lib.roaring_bitmap_andnot_cardinality(self._croaring, other._croaring)

    def symmetric_difference_cardinality(self, other):
        return lib.roaring_bitmap_xor_cardinality(self._croaring, other._croaring)

    def add(self, value):
        lib.roaring_bitmap_add(self._croaring, value)

    def discard(self, value):
        lib.roaring_bitmap_remove(self._croaring, value)

    def pop(self, maxvalue = False):
        result = self.maximum() if maxvalue else self.minimum()
        self.remove(result)
        return result

    def remove(self, value):
        lib.roaring_bitmap_remove(self._croaring, value)

    def dumps(self):
        buf_size = lib.roaring_bitmap_size_in_bytes(self._croaring)
        out = ffi.new('char[%d]' % (buf_size))
        size = lib.roaring_bitmap_serialize(self._croaring, out)
        if size < 0:
            return None
        return ffi.buffer(out)[:size]

    def portable_dumps(self):
        buf_size = lib.roaring_bitmap_portable_size_in_bytes(self._croaring)
        out = ffi.new('char[%d]' % (buf_size))
        size = lib.roaring_bitmap_portable_serialize(self._croaring, out)
        if size < 0:
            return None
        return ffi.buffer(out)[:size]

    def frozen_dumps(self):
        buf_size = lib.roaring_bitmap_frozen_size_in_bytes(self._croaring)
        out = ffi.new('char[%d]' % (buf_size))
        lib.roaring_bitmap_frozen_serialize(self._croaring, out)
        return ffi.buffer(out)[:buf_size]

    def clear(self):
        lib.roaring_bitmap_clear(self._croaring)

    @classmethod
    def loads(cls, buf):
        inbuf = ffi.new('char[%d]'%(len(buf)), buf)
        _croaring = lib.roaring_bitmap_deserialize(inbuf)
        return cls(croaring = _croaring)

    @classmethod
    def portable_loads(cls, buf):
        inbuf = ffi.new('char[%d]'%(len(buf)), buf)
        _croaring = lib.roaring_bitmap_portable_deserialize_safe(inbuf, len(buf))
        return cls(croaring = _croaring)

    @classmethod
    def frozen_loads(cls, s):
        size = len(s)
        buf = lib.malloc_aligned(size, 32)
        inbuf = ffi.cast('char *', buf)
        ffi.memmove(inbuf, s, size)
        _croaring = lib.roaring_bitmap_frozen_view(inbuf, size)
        return cls(croaring = _croaring)

    def minimum(self):
        return lib.roaring_bitmap_minimum(self._croaring)

    def maximum(self):
        return lib.roaring_bitmap_maximum(self._croaring)

    def min(self):
        return lib.roaring_bitmap_minimum(self._croaring)

    def max(self):
        return lib.roaring_bitmap_maximum(self._croaring)

    def bytes_size(self):
        return lib.roaring_bitmap_size_in_bytes(self._croaring)

    def run_optimize(self):
        return lib.roaring_bitmap_run_optimize(self._croaring)

    def is_empty(self):
        return bool(lib.roaring_bitmap_is_empty(self._croaring))

    def shrink(self):
        return lib.roaring_bitmap_shrink_to_fit(self._croaring)

    def intersect(self, ohter):
        return bool(lib.roaring_bitmap_intersect(self._croaring, other._croaring))

    def rank(self, value):
        return lib.roaring_bitmap_rank(self._croaring, value)

    def to_array(self):
        size = len(self)
        out = ffi.new('uint32_t[%d]' % (size))
        lib.roaring_bitmap_to_uint32_array(self._croaring, out)
        ar = array.array('I', out)
        return ar

    def get_statistics(self):
        out = ffi.new('roaring_statistics_t[%d]' % (1))
        lib.roaring_bitmap_statistics(self._croaring, out)
        return out[0]

def load_from_file(file_name):
    result = None
    try:
        with open(file_name, 'fb') as f:
            result = BitSet.loads(f.read())
    except Exception as e:
        import logging
        logging.error(str(e))
    return result
