
import sys, re
from extensions import Dict

class ReferenceType(object):

  Scope = dict()
  
  _typeId    = '\s*(\w+)\s*'      #< some type identifier
  _baseType  = '\s*([\w *()]+)'   #< e.g. integer*4, type(Struct), character(*), <interfaceId>, ...
  _dimType   = '\s*([\w ,:()]+)'  #< e.g. scalar, dimension(:,:), procedure
  _keyAssign = '\s*(\w+)\s*=\s*(\w+)\s*'
  _procItf   = '\s*procedure\s*\(%s\)\s*' % _typeId         #< procedure interface
  _dimSpec   = '\s*dimension\s*\(\s*:(?:\s*,\s*:)*\s*\)\s*' #< dimension specification
  _keySpecs  = '((?:,\s*\w+\s*=\s*\w+\s*)*)'
  _typeDecl  = '^\s*!\s*_TypeReference_declare\(%s,%s,%s%s\)' % (_typeId, _baseType, _dimType, _keySpecs)
  _typeImpl  = '^\s*!\s*_TypeReference_implement\(%s\)' % _typeId
  _typeImplA = '^\s*!\s*_TypeReference_implementAll\(\)'
  
  typeDeclMatch    = re.compile( _typeDecl ).match
  typeImplMatch    = re.compile( _typeImpl ).match
  typeImplAllMatch = re.compile( _typeImplA ).match
  procItfMatch     = re.compile( _procItf ).match
  dimSpecMatch     = re.compile( _dimSpec ).match

  _template  = dict(
    header = """
    !#################################
    !# {typeId}
    !#################################
    """,

    # parameters:
    #   access:    private | public
    #   typeId:    type identifier
    #   baseType:  fortran base type | type(...) | procedure(...) [needs baseExtra: , nopass]
    #   baseExtra: ('', ', nopass')[is_procedure] 
    #   dimType:   ('', ', dimension(:,...)')[has_dimension]
    #
    type = """
    type, {access} :: {typeId}
       {baseType}{baseExtra}{dimType}, pointer :: ptr
    end type
    type (TypeInfo), target :: TypeInfo_{typeId}
    """,

    # parameters:
    #   access: private | public
    #
    gen_itf = """
    {access} :: operator(.ref.)
    """,
  
    # parameters:
    #   access: private | public
    #   typeId: type identifier
    #
    ref_itf = """
    interface operator(.ref.);      module procedure GenericRef_encode_{typeId}; end interface
    interface operator(.{typeId}.); module procedure GenericRef_decode_{typeId}; end interface
    {access} :: operator(.{typeId}.)
    """,
  
    # parameters:
    #   access: private | public
    #   typeId: type identifier
    #
    # NOTE: we can't create operator interfaces for procedure encoders/decoders.
    #   For the encoder, this is, because fortran can't distinguish different procedure types.
    #   For the decoder, it's obviously due to various compiler bugs ...
    #
    proc_itf = """
    interface {typeId}_from_ref; module procedure GenericRef_decode_{typeId}; end interface
    {access} :: ref_from_{typeId}
    {access} :: {typeId}_from_ref
    """,
  
    # parameters:
    #   typeId:     type identifier
    #   baseType:   fortran base type | type(...) | procedure(...)
    #   dimType:    ('', ', dimension(:,...)')[has_dimension]
    #   assignProc: ('', ', assignProc = <funcId>')[has_assignProc]
    #   deleteProc: ('', ', deleteProc = <funcId>')[has_deleteProc]
    #   shapeProc:  ('', ', shapeProc = <funcId>')[has_shapeProc]
    #
    ref_encoder = """
    function GenericRef_encode_{typeId}( val ) result(res)
      use iso_c_binding
      {baseType}{dimType}, target, intent(in) :: val
      type (GenericRef)                       :: res
      type ({typeId}),                 target :: wrap
      procedure(),                    pointer :: None => null()
    
      wrap%ptr => val
      if (gr_set_TypeReference( res, c_loc(wrap), storage_size(wrap), TypeInfo_{typeId} )) &
        call gr_init_TypeInfo( TypeInfo_{typeId}, '{typeId}', '{baseType}' &
                               , storage_size(val)/8 &
                               , size(shape(val)){assignProc}{deleteProc}{shapeProc} &
                               , cloneProc = GenericRef_clone_{typeId} )
    end function
    """,
    
    # parameters:
    #   typeId:     type identifier
    #   baseType:   fortran base type | type(...) | procedure(...)
    #   dimType:    ('', ', dimension(:,...)')[has_dimension]
    #
    proc_encoder = """
    function ref_from_{typeId}( val ) result(res)
      use iso_c_binding
      {baseType}{dimType}     :: val
      type (GenericRef)       :: res
      type ({typeId}), target :: wrap
    
      wrap%ptr => val
      if (gr_set_TypeReference( res, c_loc(wrap), storage_size(wrap), TypeInfo_{typeId} )) &
        call gr_init_TypeInfo( TypeInfo_{typeId}, '{typeId}', '{baseType}', 0, 0 )
    end function
    """,
    
    # parameters:
    #   typeId:    type identifier
    #   baseType:  fortran base type | type(...) | procedure(...)
    #   dimType:   ('', ', dimension(:,...)')[has_dimension]
    #
    decoder = """
    function GenericRef_decode_{typeId}( val ) result(res)
      use iso_c_binding
      type (GenericRef), intent(in) :: val
      {baseType}{dimType},  pointer :: res
      type ({typeId}),      pointer :: wrap
      
      call c_f_pointer( gr_get_TypeReference(val), wrap )
      res => wrap%ptr
    end function
    """,
    
    # parameters:
    #   typeId:    type identifier
    #   baseType:  fortran base type | type(...) | procedure(...)
    #   dimType:   ('', ', dimension(:,...)')[has_dimension]
    #   cloneBy:   <cloneCode> [alloc_clone | func_clone]
    #
    cloner = """
    subroutine GenericRef_clone_{typeId}( val, res )
      use iso_c_binding
      type (GenericRef),          intent(in) :: val
      type (GenericRef)                      :: res
      {baseType}{dimType},           pointer :: src, tgt => null()
      character(len=1), dimension(:), pointer :: tmp
    
      src => GenericRef_decode_{typeId}( val ){cloneBy}
      res =  GenericRef_encode_{typeId}( tgt )
    end subroutine
    """,
    
    # parameters:
    #   shapeArg: (", shape(src)" | "")[is_scalar]
    alloc_clone = """
      allocate( tmp( product(shape(src)) * storage_size(src)/8 ) )
      call c_f_pointer( c_loc(tmp(1)), tgt{shapeArg} )
      tgt = src
    """,
    
    # parameters:
    #   clonerFunc: id of clone function
    func_clone = """
      tgt => {clonerFunc}( src )
    """,

    # parameters:
    #   typeId: type identifier
    #
    inspector = """
    subroutine GenericRef_inspect_{typeId}( val, res, n )
      type (GenericRef), intent(in) :: val
      integer                       :: n
      integer                       :: res(n)
      res(:n) = shape( GenericRef_decode_{typeId}( val ) )
    end subroutine
    """
  )


  def __init__( self, typeId, baseType, dimType, keySpecs ):
    self._isProc   = bool(self.procItfMatch( baseType ))
    self._isScalar = dimType == 'scalar'
    self._isArray  = bool(self.dimSpecMatch( dimType ))
    self._typeProc = dict( re.findall( self._keyAssign, keySpecs ) )

    # sanity check
    if not (self._isScalar ^ self._isArray):
      raise TypeError('invalid dimension specification "%s"' % dimType)

    self.access    = 'public'
    self.typeId    = typeId
    self.baseType  = baseType
    self.baseExtra = ('', ', nopass')[self._isProc]
    self.valTarget = (', target, intent(in)', '')[self._isProc]
    self.dimType   = ('', ', %s' % dimType)[self._isArray]
    self.shapeArg  = ('', ', shape(src)')[self._isArray]

    self.assignProc = ', assignProc = %s' % self._typeProc.get('assignProc')
    self.deleteProc = ', deleteProc = %s' % self._typeProc.get('deleteProc')
    self.shapeProc  = ('', ', shapeProc  = GenericRef_inspect_%s' % typeId)[self._isArray]
    self.cloneProc  = self._typeProc.get('cloneProc')
    self.cloneType  = ('alloc_clone', 'func_clone')[bool(self.cloneProc)]
    self.cloneBy    = self._template[self.cloneType].format( **self.__dict__ )
    
    self._type    = self._template['type']
    self._itf     = self._template[('ref_itf', 'proc_itf')[self._isProc]]
    self._encoder = self._template[('ref_encoder', 'proc_encoder')[self._isProc]]
    self._decoder = self._template['decoder']
    self._cloner  = (self._template['cloner'], '')[self._isProc]
    self._inspect = (self._template['inspector'], '')[self._isProc]

    self._declared    = False
    self._implemented = False

    #print Dict.str(self.__dict__)
    ReferenceType.Scope[typeId] = self


  def declare( self ):
    if not self._declared:
      if len(ReferenceType.Scope) == 1:
        sys.stdout.write( self._template['gen_itf'].format( **self.__dict__ ) )

      sys.stdout.write( self._type.format( **self.__dict__ ) )
      sys.stdout.write( self._itf.format( **self.__dict__ ) )
      self._declared = True


  def implement( self ):
    if not self._implemented:
      sys.stdout.write( self._template['header'].format( **self.__dict__ ) )
      sys.stdout.write( self._encoder.format( **self.__dict__ ) )
      sys.stdout.write( self._decoder.format( **self.__dict__ ) )
      sys.stdout.write( self._cloner.format( **self.__dict__ ) )
      sys.stdout.write( self._inspect.format( **self.__dict__ ) )
      self._implemented = True


  @classmethod
  def convert( _class, fileName ):

    with open(fileName) as f:
      for l in f.readlines():

        match = _class.typeDeclMatch( l )
        if match:
          _class( *map( str.strip, match.groups() ) ).declare()
          continue

        match = _class.typeImplMatch( l )
        if match:
          _class.Scope[ match.groups()[0] ].implement()
          continue

        if _class.typeImplAllMatch( l ):
          for decl in sorted( _class.Scope.items() ):
            decl[1].implement()
          continue

        sys.stdout.write( l )



if __name__ == '__main__':
  ReferenceType.convert( sys.argv[1] )


