
#if defined _MSC_VER
# include <windows.h>
# include <DbgHelp.h>
#else
# include <dlfcn.h>
# include <execinfo.h>
#endif

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "fortres/sharedlib.hpp"
#include "fortres/dirent.hpp"


typedef void (*FrameOperator)( const char * );

void
stack_walk( FrameOperator frameOp, unsigned int skippedFrames = 0 )
{
  void *frames[100];
  int   stackSize;

#if defined _MSC_VER
  HANDLE       process;
  SYMBOL_INFO *symbol;
  char         frameBuffer[512+32];

  process   = GetCurrentProcess();
  SymInitialize( process, NULL, TRUE );
  stackSize = CaptureStackBackTrace( 0, sizeof(frames), frames, NULL );

  symbol = (SYMBOL_INFO *)malloc( sizeof(SYMBOL_INFO) + 256 * sizeof(char) );
  symbol->MaxNameLen   = 255;
  symbol->SizeOfStruct = sizeof(SYMBOL_INFO);

  for (int i = stackSize - 1; i > skippedFrames; --i)
  {
    SymFromAddr( process, (DWORD64)(frames[i]), 0, symbol );
    so_filepath_of( (void *)symbol->Address, frameBuffer, 256 );
    sprintf( frameBuffer, "%s(%s) [0x%0X]", relPath_to(frameBuffer).c_str(), symbol->Name, symbol->Address );
    frameOp( frameBuffer );
  }
  free( symbol );
#else
	char **strings;

	stackSize = backtrace( frames, sizeof(frames) );
	strings   = backtrace_symbols( frames, stackSize );

	if (strings)
	{
    for (int i = stackSize - 1; i > skippedFrames; --i)
			{ frameOp( strings[i] ); }
		free( strings );
	}
#endif
}


void
printFrameLine( const char *frameLine )
  { printf( "%s\n", frameLine ); }


void
printStack( void )
{
  stack_walk( printFrameLine, 1 );
}


