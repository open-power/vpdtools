# Jason Albert - created 08/21/2014
# Python module to define command cmdline parsing functions

############################################################
# Imports - Imports - Imports - Imports - Imports - Imports
############################################################
import sys
import re

############################################################
# Function - Functions - Functions - Functions - Functions
############################################################
def parseOption(option1, option2=None, remove=True):
    """ 
    Parses the command line for options without args 
    Setting remove to False means the found option will not be removed from argv
    """
   
    # Create a list of options we loop over
    options = list()
    options.append(option1)
    if (option2 != None):
        options.append(option2)

    for option in options:
         # We are going to loop through looking for the option passed in
         # When found, it will be removed from argv
         # Return will be 1 to indicate it's found
         # Since we return once we get a match, we don't have to worry about the fact that we are modifying the list in flight
         for i in range(0, len(sys.argv)):
             if (sys.argv[i] == option):
                 if remove:
                     sys.argv.pop(i) # Remove from the args
                 return 1

    # Found nothing
    return 0

def parseOptionWithArg(option1, option2=None, remove=True):
    """
    Parses the command line for options with args
    They can be in the format of --su2, --su 2 or --su=2
    Setting remove to False means the found option will not be removed from argv
    """

    # The value to return
    optValue = None

    # Create a list of options we loop over
    options = list()
    options.append(option1)
    if (option2 != None):
        options.append(option2)
    
    for option in options:
        # We are going to loop through looking for the option passed in
        # When found, it and it's value will be removed from argv
        # Return wil be 1 to indicate it's found, along with the value
        # Since we return once we get a match, we don't have to worry about the fact that we are modifying the list in flight
        for i in range(0, len(sys.argv)):
            if (re.match('^' + option, sys.argv[i])):
                # We need to handle --option xx, --option=xx, --optionxx
                # An option with a space
                if (sys.argv[i] == option):
                    optValue = sys.argv[i+1]
                    if remove:
                        sys.argv.pop(i) # Remove the option from the args
                        sys.argv.pop(i) # Remove the value from the args.  It's not i+1 because the pop shrunk the list
                    return optValue

                # We'll strip the option off the front, and handle an = if it is there at the front
                else:
                    optValue = sys.argv[i]
                    optValue = re.sub('^' + option, '', optValue) # The option
                    optValue = re.sub('^=', '', optValue) # An = if it's there
                    if remove:
                        sys.argv.pop(i) # Remove from the args
                    return optValue

    # Found nothing
    return None
