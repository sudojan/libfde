
"""Usage: refgen FILE [-o OUTFILE]

Preprocess FILE and expand type reference declarations.
The result is output to stdout.

Arguments:
  FILE        input file
  OUTFILE     output file

Options:
  -o OUTFILE --output=OUTFILE   the output file

"""

from docopt import docopt
import sys, re


class TypeSpec(object):

  _procItf     = '\s*procedure\s*\(\s*\w*\s*\)\s*'
  _dimSize     = '(?::|\d+)'
  _dimSpec     = '\s*dimension\s*\(\s*%s(?:\s*,\s*%s)*\s*\)\s*' % (_dimSize, _dimSize)
  _keyAssign   = '\s*(\w+)\s*=\s*(\w+)\s*'
  procItfMatch = re.compile( _procItf ).match
  dimSpecMatch = re.compile( _dimSpec ).match
  declWatcher  = dict()

  _template = dict(
    header = """
    !#################################
    !# {typeId}
    !#################################
    """,

    access_decl = """
    {access} :: {ident}
    """
  )

  def __init__( self, access, typeId, baseType, dimType ):
    self._isProc   = bool(self.procItfMatch( baseType ))
    self._isScalar = dimType == 'scalar'
    self._isArray  = bool(self.dimSpecMatch( dimType ))

    # sanity checks
    if not (self._isScalar ^ self._isArray):
      raise TypeError('ERROR at processing type "%s": invalid dimension specification "%s"' % (typeId, dimType))

    if access not in ('public', 'private'):
      raise ValueError('ERROR at processing type "%s": invalid access specification "%s"' % (typeId, access))

    self.access    = access
    self.typeId    = typeId
    self.baseType  = baseType
    self.dimType   = dimType
    self.dimSize   = ('', ', %s' % dimType)[self._isArray]
    self.dimSpec   = ('', ', dimension(%s)' % ','.join( [':'] * (dimType.count(',')+1) ))[self._isArray]
    self.baseExtra = ('', ', nopass')[self._isProc]
    self.valAttrib = (', target, intent(in)', '')[self._isProc]
    self.shapeArg  = ('', ', shape(src)')[self._isArray]

    self._declared    = False
    self._implemented = False


  def expand( self, out, *args, **kwArgs ):
    for what in filter( None, args ):
      out( self._template[what].format( **dict( self.__dict__, **kwArgs ) ) )

  
  def expandAccess( self, out, access, *identList ):
    for ident in filter( None, identList ):
      if ident not in self.declWatcher:
        out( self._template['access_decl'].format( access = access, ident = ident ) )
        self.declWatcher[ident] = access


  def expandAccessString( self, out, access, accessString ):
    self.expandAccess( out, access, *accessString.format( **self.__dict__ ).split(', ') )



class RefType(TypeSpec):

  _template  = dict( TypeSpec._template,
    info = """
    !@ _TypeGen_declare_RefType( {access}, {typeId}, {baseType}, {dimType}{keySpecStr} )""",

    # parameters:
    #   typeId:    type identifier
    #   baseType:  fortran base type | type(...) | procedure(...) [needs baseExtra: , nopass]
    #   baseExtra: ('', ', nopass')[is_procedure] 
    #   dimSpec:   ('', ', dimension(:,...)')[has_dimension]
    #
    type = """
    type, private :: {typeId}_wrap_t
       {baseType}{baseExtra}{dimSpec}, pointer :: ptr
    end type

    type, private :: {typeId}_encoder_t
      type(TypeInfo_t), pointer :: typeInfo
      type({typeId}_wrap_t)     :: ref_wrap
    end type

    type(TypeInfo_t), target :: type_{typeId}
    """,

    # parameters:
    #   access:    private | public
    #   typeId:    type identifier
    #
    ref_itf = """
    interface ref_of     ; module procedure {typeId}_encode_ref_ ; end interface
    interface {typeId}   ; module procedure {typeId}_decode_ref_ ; end interface
    interface is_{typeId}; module procedure {typeId}_in_ref_     ; end interface
    interface static_type; module procedure {typeId}_typeinfo_   ; end interface
    """,

    access_ref = "{typeId}, is_{typeId}",
  
    # parameters:
    #   access: private | public
    #   typeId: type identifier
    #
    # NOTE: we can't create operator interfaces for procedure encoders/decoders.
    #   For the encoder, this is, because fortran can't distinguish different procedure types.
    #   For the decoder, it's obviously due to various compiler bugs ...
    #
    proc_itf = """
    interface ref_from_{typeId}; module procedure {typeId}_encode_ref_ ; end interface
    interface {typeId}_from_ref; module procedure {typeId}_decode_ref_ ; end interface
    interface is_{typeId}      ; module procedure {typeId}_in_ref_     ; end interface
    interface static_type      ; module procedure {typeId}_typeinfo_   ; end interface
    """,

    access_proc = "ref_from_{typeId}, {typeId}_from_ref, is_{typeId}",
  
    # parameters:
    #   typeId:     type identifier
    #   baseType:   fortran base type | type(...) | procedure(...)
    #   dimSpec:    ('', ', dimension(:,...)')[has_dimension]
    #
    ref_encoder = """
    function {typeId}_encode_ref_( val ) result(res)
      use iso_c_binding
      {baseType}{dimSpec}{valAttrib} :: val
      type({typeId}_encoder_t),        target :: encoder
      type(GenericRef_Encoding_t)             :: dummy
      type(GenericRef_Encoding_t)             :: res( ceiling( storage_size(encoder) / real(storage_size(dummy)) ) )
      type(GenericRef_Encoding_t), dimension(:), pointer :: fptr

      encoder%typeInfo     => static_type(val)
      encoder%ref_wrap%ptr => val
      call c_f_pointer( c_loc(encoder), fptr, shape(res) )
      res = fptr
    end function
    """,
    
    # parameters:
    #   typeId:    type identifier
    #   baseType:  fortran base type | type(...) | procedure(...)
    #   dimSpec:   ('', ', dimension(:,...)')[has_dimension]
    #
    ref_decoder = """
    function {typeId}_decode_ref_( val ) result(res)
      use iso_c_binding
      type(GenericRef_t), intent(in) :: val
      {baseType}{dimSpec},   pointer :: res
      type({typeId}_wrap_t), pointer :: wrap
      
      call c_f_pointer( gr_get_TypeReference(val), wrap )
      res => wrap%ptr
    end function
    """,
    
    # parameters:
    #   typeId:        type identifier
    #   baseType:      fortran base type | type(...) | procedure(...)
    #   dimSpec:       ('', ', dimension(:,...)')[has_dimension]
    #   code_clonePtr: 'tgt => src' | 'call <typeId>_clone_ptr_( tgt, src )'
    ref_cloner = """
    subroutine {typeId}_clone_ref_( tgt_ref, src_ref )
      use iso_c_binding
      type(GenericRef_t)                      :: tgt_ref
      type(GenericRef_t),          intent(in) :: src_ref
      {baseType}{dimSpec},            pointer :: src, tgt => null()
    
      src => {typeId}_decode_ref_( src_ref )
      {code_clonePtr}
      tgt_ref =  {typeId}_encode_ref_( tgt )
    end subroutine
    """,

    ptr_cloner = dict(
      # parameters:
      #   typeId:   type identifier
      #   baseType: fortran base type | type(...)
      #   dimSpec:  ('', ', dimension(:,...)')[has_dimension]
      #   shapeArg: (", shape(src)" | "")[is_scalar]
      _shallow = """
      subroutine {typeId}_clone_ptr_( tgt, src )
        use iso_c_binding
        {baseType}{dimSpec}, pointer, intent(out) :: tgt
        {baseType}{dimSpec},           intent(in) :: src
        character(len=1), dimension(:),   pointer :: tmp
        allocate( tmp( product(shape(src)) * storage_size(src)/8 ) )
        call c_f_pointer( c_loc(tmp(1)), tgt{shapeArg} )
        tgt = src
      end subroutine
      """,

      # parameters:
      #   typeId:      type identifier
      #   baseType:    fortran base type | type(...)
      _type = """
      subroutine {typeId}_clone_ptr_( tgt, src )
        {baseType}, pointer, intent(out) :: tgt
        {baseType},           intent(in) :: src
        type(TypeInfo_t),        pointer :: ti

        allocate( tgt ) !< initializes res as default {typeId}
        ti => static_type( tgt )
        if (associated( ti%initProc )) &
          call ti%initProc( tgt, 1, src )
        tgt = src
      end subroutine
      """
    ),

    # parameters:
    #   typeId:    type identifier
    #   baseType:  fortran base type | type(...) | procedure(...)
    #   dimSpec:   ('', ', dimension(:,...)')[has_dimension]
    c2f_caster = """
    subroutine {typeId}_c2f_cast_( ptr_c, ptr_f )
      use iso_c_binding
      type(c_ptr),                   intent(in) :: ptr_c
      {baseType}{dimSpec}, pointer, intent(out) :: ptr_f
      type({typeId}_wrap_t),            pointer :: wrap
      call c_f_pointer( ptr_c, wrap )
      ptr_f => wrap%ptr
    end subroutine
    """,

    # parameters:
    #   typeId: type identifier
    #
    ref_inspector = """
    subroutine {typeId}_inspect_( val, res, n )
      type(GenericRef_t), intent(in) :: val
      integer                        :: n
      integer                        :: res(n)
      res(:n) = shape( {typeId}_decode_ref_( val ) )
    end subroutine
    """,

    # parameters:
    ref_typechecker = """
    function {typeId}_in_ref_( self ) result(res)
      type(GenericRef_t), intent(in) :: self
      logical                        :: res
      res = associated( dynamic_type(self), type_{typeId} )
    end function
    """,

    # parameters:
    #   typeId:     type identifier
    #   baseType:   fortran base type | type(...) | procedure(...)
    #   dimSpec:    ('', ', dimension(:,...)')[has_dimension]
    #   initProc:   ', initProc = <funcId>'
    #   assignProc: ', assignProc = <funcId>'
    #   deleteProc: ', deleteProc = <funcId>'
    #   shapeProc:  ', shapeProc = <funcId>'
    ref_typeinfo = """
    function {typeId}_typeinfo_( self ) result(res)
      {baseType}{dimSpec}       :: self
      type(TypeInfo_t), pointer :: res

      res => type_{typeId}
      if (.not. res%initialized) &
        call init_TypeInfo( res, '{typeId}', '{baseType}' &
                            , int(storage_size(self),4) &
                            , size(shape(self)){initProc}{assignProc}{deleteProc}{shapeProc}{cloneProc} &
                            , castProc = {typeId}_c2f_cast_ &
                            , cloneRefProc = {typeId}_clone_ref_ )
    end function
    """,

    # parameters:
    #   typeId:     type identifier
    #   baseType:   fortran base type | type(...) | procedure(...)
    #   dimSpec:    ('', ', dimension(:,...)')[has_dimension]
    proc_typeinfo = """
    function {typeId}_typeinfo_( self ) result(res)
      {baseType}{dimSpec}       :: self
      type(TypeInfo_t), pointer :: res

      res => type_{typeId}
      if (.not. res%initialized) &
        call init_TypeInfo( res, '{typeId}', '{baseType}', 0, 0 )
    end function
    """
  )


  def __init__( self, access, typeId, baseType, dimType, keySpecs ):
    super(RefType, self).__init__( access, typeId, baseType, dimType )

    keySpecs  = dict( re.findall( self._keyAssign, keySpecs ) )
    typeProcs = dict( (k,v) for k,v in keySpecs.items() if k.endswith('Proc') )

    if keySpecs: self.keySpecStr = ', ' + ', '.join( '%s = %s' % i for i in keySpecs.items() )
    else       : self.keySpecStr = ''

    if self._isArray:
      typeProcs.setdefault( 'shapeProc', typeId + '_inspect_' )

    if self._isProc:
      keySpecs.setdefault( 'cloneMode', '_none' ) #< if not set explicitly, we disable cloning for procedure types
      if typeProcs:
        print 'WARNING: given type procs %s are ignored for procedure type "%s"' % (typeProcs, typeId)

    for procId in ('initProc', 'assignProc', 'deleteProc', 'shapeProc'):
      procArg  = ''
      procName = typeProcs.get( procId, '' )
      if procName not in ('', '_none'):
        procArg = ', %s = %s' % (procId, procName)
      setattr( self, procId, procArg )

    # handle type cloning ...
    ptrClonerId     = keySpecs.get('cloneMode', '_shallow')               #< by default clone via shallow copy
    self._ptrCloner = self._template['ptr_cloner'].get( ptrClonerId, '' ) #< get code for default implementation
    
    if self._ptrCloner:
      # we implement a default cloner (_shallow or _type) - so update ptrClonerId
      ptrClonerId = typeId + '_clone_ptr_'
    elif ptrClonerId == '_none':
      # cloning disabled via _none - so there's no ptrClonerId
      ptrClonerId = ''
    
    if ptrClonerId:
      self.code_clonePtr = 'call %s( tgt, src )' % ptrClonerId
      self.cloneProc     = ', cloneObjProc = %s' % ptrClonerId
    else:
      self.code_clonePtr = 'tgt => src'
      self.cloneProc  = ''

    self._itf       = ('ref_itf',       'proc_itf'     )[self._isProc]
    self._access    = ('access_ref',    'access_proc'  )[self._isProc]
    self._refCloner = ('ref_cloner',    ''             )[self._isProc]
    self._inspector = ('ref_inspector', ''             )[self._isProc]
    self._typeinfo  = ('ref_typeinfo',  'proc_typeinfo')[self._isProc]


  def declare( self, out ):
    if not self._declared:
      self.expand( out, 'info', 'type', self._itf )
      self.expandAccess( out, self.access, 'ref_of', 'static_type' )
      self.expandAccessString( out, self.access, self._template[self._access] )
      TypeGenerator.setDeclaration( self.typeId, self )
      self._declared = True


  def implement( self, out ):
    if not self._implemented:
      self.expand( out, 'header', 'ref_encoder', 'ref_decoder', 'c2f_caster', 'ref_typechecker',
                   self._refCloner, self._inspector, self._typeinfo )
      out( self._ptrCloner.format( **self.__dict__ ) )
      self._implemented = True


  
class ListItem(TypeSpec):
  
  _template  = dict( TypeSpec._template,
    info = """
    !@ _TypeGen_declare_ListItem( {access}, {typeId}, {baseType}, {dimType} )""",

    type = """
    type, private :: {typeId}_item_t
      type(Item_t)        :: super
      {baseType}{dimSize} :: value
    end type
    type(TypeInfo_t), target :: type_{typeId}_item
    """,

    item_itf = """
    interface new_ListItem    ; module procedure {typeId}_new_item_    ; end interface
    interface new_ListItem_of ; module procedure {typeId}_new_item_of_ ; end interface
    interface item_type       ; module procedure {typeId}_itemtype_    ; end interface
    interface {typeId}        ; module procedure {typeId}_item_value_  ; end interface
    """,

    alias_itf = """
    interface new_ListItem_of ; module procedure {typeId}{aliasId}_new_item_of_ ; end interface
    """,

    access_itf = "new_ListItem, new_ListItem_of, item_type, {typeId}",

    item_type = """
    function {typeId}_itemtype_( val ) result(res)
      {baseType}{dimSpec}, intent(in) :: val
      type(TypeInfo_t),       pointer :: res
      type({typeId}_item_t)           :: item
      res => type_{typeId}_item
      if (.not. res%initialized) &
        call init_TypeInfo( res, '{typeId}_item', 'type({typeId}_item_t)', &
          int(storage_size(item),4), 0, subtype = static_type(val), cloneObjProc = {typeId}_clone_item_ )
    end function
    """,

    new_item = """
    function {typeId}_new_item_( valPtr ) result(res)
      {baseType}{dimSpec}, pointer, intent(out) :: valPtr
      type(Item_t),                     pointer :: res
      type({typeId}_item_t),            pointer :: tgt => null()
      type(TypeInfo_t),                 pointer :: ti

      allocate( tgt )
      ti => static_type( tgt%value )
      if (associated( ti%initProc )) &
        call ti%initProc( tgt%value, 0 ) !< init value as default instance!
      valPtr => tgt%value
      res    => tgt%super
      res%typeInfo => item_type(valPtr)
    end function
    """,

    new_item_of = """
    function {typeId}_new_item_of_( val ) result(res)
      {baseType}{dimSpec}, intent(in) :: val
      type(Item_t),           pointer :: res
      {baseType}{dimSpec},    pointer :: val_ptr
      res     => {typeId}_new_item_( val_ptr )
      val_ptr =  val
    end function
    """,

    new_item_of_alias = """
    function {typeId}{aliasId}_new_item_of_( val ) result(res)
      {baseType}{dimSpec},        intent(in) :: val
      type(Item_t),                  pointer :: res
      {aliasBaseType}{aliasDimSpec}, pointer :: val_ptr
      res     => {typeId}_new_item_( val_ptr )
      val_ptr =  val
    end function
    """,

    clone_item = """
    subroutine {typeId}_clone_item_( tgt, src )
      type(Item_t), pointer, intent(out) :: tgt
      type({typeId}_item_t),  intent(in) :: src
      type({typeId}_item_t),     pointer :: ptr => null()
      type(TypeInfo_t),          pointer :: ti

      allocate( ptr )
      ti => static_type( ptr%value )
      if (associated( ti%initProc )) &
        call ti%initProc( ptr%value, 0 ) !< init value as default instance!
      ptr%value = src%value
      tgt => ptr%super
      tgt%typeInfo => item_type(src%value)
    end subroutine
    """,

    item_value = """
    function {typeId}_item_value_( idx ) result(res)
      use iso_c_binding
      type(ListIndex_t)              :: idx
      {baseType}{dimSpec},   pointer :: res
      type({typeId}_item_t), pointer :: ptr
      call c_f_pointer( c_loc(idx%node), ptr )
      res => ptr%value
    end function
    """
  )

  def __init__( self, access, typeId, baseType, dimType ):
    if access != 'alias':
      self.aliasId = ''
    else:
      self.aliasId = '_alias%d' % TypeGenerator.getAliasCount( typeId, self )
      access = 'private'
    super(ListItem, self).__init__( access, typeId, baseType, dimType )


  def declare( self, out ):
    if not self._declared:
      if self.aliasId: self.expand( out, 'info', 'alias_itf' )
      else           : self.expand( out, 'info', 'type', 'item_itf' )
      self.expandAccessString( out, self.access, self._template['access_itf'] )
      TypeGenerator.setDeclaration( self.typeId, self )
      self._declared = True


  def implement( self, out ):
    if not self._implemented:
      if self.aliasId:
        alias = TypeGenerator.getBaseDeclaration( self.typeId, self )
        self.expand( out, 'new_item_of_alias', aliasBaseType = alias.baseType, aliasDimSpec = alias.dimSpec )
      else:
        self.expand( out, 'new_item', 'new_item_of', 'item_type', 'clone_item', 'item_value' )
      self._implemented = True



class TypeGenerator(object):

  scope = dict()
  count = dict()

  _ident     = '\s*(\w+)\s*'      #< some type identifier
  _baseType  = '\s*([\w *=()]+)'  #< e.g. integer*4, type(Struct), character(len=*), <interfaceId>, ...
  _dimType   = '\s*([\w ,:()]+)'  #< e.g. scalar, dimension(:,:), procedure
  _keySpecs  = '((?:,\s*\w+\s*=\s*\w+\s*)*)'
  _typeDecl  = '^\s*!\s*_TypeGen_declare_RefType\(%s,%s,%s,%s%s\)' % (_ident, _ident, _baseType, _dimType, _keySpecs)
  _itemDecl  = '^\s*!\s*_TypeGen_declare_ListItem\(%s,%s,%s,%s\)' % (_ident, _ident, _baseType, _dimType)
  _typeImpl  = '^\s*!\s*_TypeGen_implement\(%s\)' % _ident
  _typeImplA = '^\s*!\s*_TypeGen_implementAll\(\)'
  
  typeDeclMatch    = re.compile( _typeDecl ).match
  itemDeclMatch    = re.compile( _itemDecl ).match
  typeImplMatch    = re.compile( _typeImpl ).match
  typeImplAllMatch = re.compile( _typeImplA ).match

  
  @classmethod
  def setDeclaration( _class, key, decl ):
    key = '%s.%s' % (key, type(decl).__name__)
    _class.count[key] = idx = _class.count.get( key, 0 ) + 1
    if not getattr( decl, 'aliasId', None ):
      idx = 'base'
    _class.scope['%s.%s' % (key, idx)] = decl


  @classmethod
  def getBaseDeclaration( _class, key, decl ):
    return _class.scope[ '%s.%s.base' % (key, type(decl).__name__) ]


  @classmethod
  def getAliasCount( _class, key, decl ):
    return _class.count.get( '%s.%s' % (key, type(decl).__name__), 0 )


  @staticmethod
  def _purgeLines( buf ):
    for l in buf:
      l = l.strip()
      a = (0,1)[l.startswith('!')]
      b = (None,-1)[l.endswith('\\')]
      yield l[a:b]


  @classmethod
  def convert( _class, options ):

    with open(options['FILE']) as f:

      outFile = options.get('--output')
      outChnl = outFile and open( outFile, 'w' ) or sys.stdout
      lineBuf = []

      for line in f.readlines():
        lineBuf.append( line.rstrip() )
        if lineBuf[-1].endswith('\\'):
          continue
        
        bufStr  = '\n'.join( lineBuf ) + '\n'
        lines   = '!' + ''.join( _class._purgeLines( lineBuf ) )
        lineBuf = []

        match = _class.typeDeclMatch( lines )
        if match:
          RefType( *map( str.strip, match.groups() ) ).declare( outChnl.write )
          continue

        match = _class.itemDeclMatch( lines )
        if match:
          ListItem( *map( str.strip, match.groups() ) ).declare( outChnl.write )
          continue

        match = _class.typeImplMatch( lines )
        if match:
          _class.scope[ match.groups()[0] ].implement( outChnl.write )
          continue

        if _class.typeImplAllMatch( lines ):
          for decl in sorted( _class.scope.items() ):
            decl[1].implement( outChnl.write )
          continue

        outChnl.write( bufStr )

      outChnl.close()


if __name__ == '__main__':
  TypeGenerator.convert( docopt( __doc__ ) )


