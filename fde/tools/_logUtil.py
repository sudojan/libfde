
import logging
import os


def define_logger_py3(filename,
        file_loglevel=logging.INFO,
        console_loglevel=logging.WARNING):
    """
    Same as `define_logger` but with clearer and more intuitive
    implementation using the handlers kwarg in `logging.basicConfig`.
    However, this is only available in python3
    When dropping support for python 2, this method can be used
    """
    # define a Handler which writes messages to the log file
    file = logging.FileHandler(filename, mode='w')

    # define a Handler which writes messagesto the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(console_loglevel)
    # console.setFormatter(logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))

    # set up logging to file
    logging.basicConfig(level=file_loglevel,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M',
                        handlers=[file, console])

    # Now, we can log to the root logger, or any other logger. First the root...
    # logging.info('Initialize logger, done.')


def get_logger_py3(name):
    return logging.getLogger('{}: pid {}'.format(name, os.getpid()))


def define_logger(filename,
        file_loglevel=logging.INFO,
        console_loglevel=logging.WARNING):
    # set up logging to file - see previous section for more details
    logging.basicConfig(level=file_loglevel,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M',
                        filename=filename,
                        filemode='w',)
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(console_loglevel)
    # add the handler to the root logger
    logging.getLogger().addHandler(console)


def get_logger(name, console_loglevel=None):
    if console_loglevel is None:
        return logging.getLogger('{}: pid {}'.format(name, os.getpid()))

    console = logging.StreamHandler()
    console.setLevel(console_loglevel)
    # add the handler to the root logger
    return logging.getLogger('{}: pid {}'.format(name, os.getpid())).addHandler(console)