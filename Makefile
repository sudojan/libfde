
F90C ?= gfortran
CFG  ?= debug
ARCH ?= 32

mk_F90_FLAGS_gfortran_debug   = -ggdb -cpp -ffree-line-length-none $(_F90_FLAGS)
mk_F90_FLAGS_gfortran_release = -O3 -cpp -ffree-line-length-none $(_F90_FLAGS)
mk_F90C_gfortran              = gfortran-4.9

mk_F90_FLAGS_ifort_debug      = -g -fpp -allow nofpp-comments $(_F90_FLAGS)
mk_F90_FLAGS_ifort_release    = -O3 -fpp -allow nofpp-comments $(_F90_FLAGS)
mk_F90C_ifort                 = ifort

mk_F90C_PP_FLAGS    = $(PP_FLAGS:%=-D%)
mk_F90_FLAGS        = $(mk_F90_FLAGS_$(F90C)_$(CFG)) -m$(ARCH) $(mk_F90C_PP_FLAGS)
mk_F90C             = $(mk_F90C_$(F90C))
mk_INCLUDE_PATHLIST = -I. -I./include

mk_TAG              = $(F90C).$(CFG).$(ARCH)

.SECONDARY:
.PHONY: clean

TPP_FILES = $(wildcard *.tpp)
BASE_OBJ  = crc.o crc_impl.o type_info.o base_string.o generic_ref.o dynamic_string.o \
						abstract_list.o base_types.o var_item.o hash_map.o

# file specific compiler flags ...
crc_impl_F90_FLAGS_gfortran  = -fno-range-check
crc_impl_F90_FLAGS_ifort     = -assume noold_boz


all: clean dynstring gref varitem alist map

base: $(BASE_OBJ)

libadt: clean
	$(MAKE) _F90_FLAGS=-fpic base
	$(mk_F90C) -shared $(BASE_OBJ) -o $@.$(mk_TAG).so

libcall: libadt test_lib_call.o
	$(mk_F90C) test_lib_call.o -L. -ladt.$(mk_TAG) -lcrc -o $@.$(mk_TAG)

dynstring: $(BASE_OBJ) test_dynamic_string.o
	$(mk_F90C) $(mk_F90_FLAGS) $(mk_INCLUDE_PATHLIST) $? -o $@.$(mk_TAG)

gref: $(BASE_OBJ) test_type_references.o test_generic_ref.o
	$(mk_F90C) $(mk_F90_FLAGS) $(mk_INCLUDE_PATHLIST) $? -o $@.$(mk_TAG)

varitem: $(BASE_OBJ) test_var_item.o
	$(mk_F90C) $(mk_F90_FLAGS) $(mk_INCLUDE_PATHLIST) $? -o $@.$(mk_TAG)

alist: $(BASE_OBJ) test_abstract_list.o
	$(mk_F90C) $(mk_F90_FLAGS) $(mk_INCLUDE_PATHLIST) $? -o $@.$(mk_TAG)

map: $(BASE_OBJ) test_hash_map.o
	$(mk_F90C) $(mk_F90_FLAGS) $(mk_INCLUDE_PATHLIST) $? -o $@.$(mk_TAG)

clean:
	rm -f *.mod *.o *.debug.* *.release.* $(TPP_FILES:%.tpp=%)

test: clean dynstring gref varitem alist map
	./dynstring.$(mk_TAG)
	./gref.$(mk_TAG)
	./varitem.$(mk_TAG)
	./alist.$(mk_TAG)
	./map.$(mk_TAG)


%.f90: %.f90.tpp
	python typegen.py $< -o $@

%.o: %.f90
	$(mk_F90C) $(mk_F90_FLAGS) $($(notdir $*)_F90_FLAGS_$(F90C)) $(mk_INCLUDE_PATHLIST) -c $< -o $@

