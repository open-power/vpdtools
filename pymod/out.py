# Jason Albert - created 03/06/2014
# Python module to define common output functions

############################################################
# Imports - Imports - Imports - Imports - Imports - Imports
############################################################
import os

############################################################
# Variables - Variables - Variables - Variables - Variables
############################################################
class VarBox:
    pass

__m = VarBox()
__m.indent = 0

############################################################
# Function - Functions - Functions - Functions - Functions
############################################################
# Common function for error printing
def error(message):
    print((' ' * __m.indent) + ("ERROR: %s" % message))

def warn(message):
    print((' ' * __m.indent) + ("WARNING: %s" % message))

# Common function for debug printing
def debug(message):
    print((' ' * __m.indent) + ("DEBUG: %s" % message))

def msg(message):
    print((' ' * __m.indent) + message)

def setIndent(num):
    """ 
    Sets the output indent on all printed lines
    """
    __m.indent = num
