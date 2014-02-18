
#include "exception.fpp"

module funx
  use exception, only : throw
  use string_ref

  interface try
    _tryProcedure( tryFunc_1, _args_2 )
      import StringRef
      integer(kind=c_int) :: arg1
      type (StringRef)    :: arg2
    _end_tryProcedure

    !_tryProcedure( tryFunc_2, 3 )
    !  import StringRef
    !  type (StringRef)    :: arg1, arg2
    !  integer(kind=c_int) :: arg3
    !_end_tryProcedure
  end interface

  contains

  subroutine another( msg1, msg2, val1 )!, val2, rval )
    type (StringRef) :: msg1, msg2
    integer*4        :: val1!, val2
    !real*8    :: rval
    print *, str(msg1)
    !if (val1 + val2 < rval) then
      !val2 = val1
    !else
      call throw(val1)
    !endif
    print *, str(msg2)
  end subroutine

  subroutine mayFail( val, msg )
    integer*4        :: val
    type (StringRef) :: msg

    if (val < 10) then
      call throw(1)
    else
      print *, str(msg)
      val = val / 2

      !print *, try( _catch((/1/)), proc(another), str("bla"), str("& text"), val, _argEnd )!, val, 4.2 )
        !case (0); print *, "catched"
      !end select
    endif
  end subroutine

end module

program main
  use funx
  use exception, only : proc
  implicit none
  integer*4 :: val

  val = 2
  select case ( try( _catchAny, proc(mayFail), val, str("test"), _argEnd ) )
    case (1); print *, "catched exception 1"
    case (2); print *, "catched exception 2"
    case (3); print *, "catched exception 3"
    case default; print *, "ok"
  end select

  print *, "finish"

end program

