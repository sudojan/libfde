
#include "exception.fpp"

module block_try
  use exception
  implicit none

  integer*4 :: itr, x, y
  real*8    :: res

  contains

  recursive subroutine main_prog()
    integer*4 :: loop, val

    loop = 0
    val  = 1

    !-- standard try block --
    _tryBlock(10)
      ! only in subroutines
      ! containing subroutines must be recursive!
      ! can't share local variables!
      res = func( itr + 42 )
      print *, itr, ": res = ", res
    _tryCatch(10, _catchAny)
      case default; print *, "catched exception"
    _tryEnd(10)


    !-- nesting of try blocks --
    _tryBlock(11)
      print *, "entering outer block"

      _tryBlock(12)
        print *, "entering inner block"
        print *, func( -1 )

      _tryCatch(12, (/ArithmeticError/))
        case default; print *, "catched ArithmeticError"
      _tryEnd(12)
      print *, "leaving outer block"

    _tryCatch(11, _catchAny)
      case default; print *, "catched exception"
    _tryEnd(11)


    !-- try-do-while block --
    itr = 0
    _tryDo(21)
      itr = itr + 1
      res = func( itr )
      print *, itr, ": res = ", res
    _tryCatch(21, (/ArithmeticError/))
      ! just ignore
    _tryWhile(21, itr < 10)


    !-- use exception to break endless loop --
    itr = 10
    _tryBlock(22)
      do while (.true.)
        print *, func( itr )
        itr = itr + 1
      end do
    _tryCatch(22, (/OverflowError/))
    _tryEnd(22)


    !-- try-for-loop --
    _tryFor(30, itr = 20, itr > -5, itr = itr - 1)
      res = func( itr )
      print *, itr, ": res = ", res

      _tryFor(31, x = -1, x < 3, x = x + 1 )
        print *, func( x )
      _tryCatch(31, _catchAny)
        case (NotImplementedError); continue
        case default;               _exit !<< only possible to exit inner loop!
      _tryEndFor(31)

    _tryCatch(30, (/ArithmeticError, RuntimeError/))
      case (RuntimeError); _exit
      case default;        continue
    _tryEndFor(30)

    print *, val, loop

  end subroutine


  real*8 function func( x ) result(res)
    integer*4 :: x
    if (x < 0) &
      call throw( NotImplementedError )
    if (x == 5) &
      call throw( ZeroDivisionError )
    if (x >= 20) &
      call throw( OverflowError )
    res = 1.0/(x - 5)
  end function

end module


program main
  use block_try

  call main_prog()
  print *, "main finish"
  
end program

