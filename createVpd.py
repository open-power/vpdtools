#!/usr/bin/env python
# Created 01/26/15 by Jason Albert
# Program to create VPD images from input template files

############################################################
# Imports - Imports - Imports - Imports - Imports - Imports
############################################################
import sys
sys.path.insert(0,"pymod");
import cmdline
import os
import xml.etree.ElementTree as ET
import glob

############################################################
# Function - Functions - Functions - Functions - Functions
############################################################
def help():
    print("createVpd.py")
    print("Required Args")
    print("Optional Args")
    print("-h|--help              This help text")

def merge(files):
    first = None
    for filename in files:
        data = ET.parse(filename).getroot()
        if first is None:
            first = data
        else:
            first.extend(data)
    if first is not None:
        return first

############################################################
# Main - Main - Main - Main - Main - Main - Main - Main
############################################################
rc = 0
# Get the path the script is being called from
cwd = os.path.dirname(os.path.abspath(__file__))

################################################
# Command line options
clError = 0

# Help text
if (cmdline.parseOption("-h","--help")):
    help()
    exit(0)

# We can run in two different modes
# 1) manifest mode - you pass in one xml file that gives all the required input args
# 2) cmdline mode - you pass in multiple command line args that recreate what would be in the manifest
# Forr now let's get manifest mode working since that will be the easiest



# Get the manifest file and get this party started
clManifestFile = cmdline.parseOptionWithArg("-m", "--manifest")
if (clManifestFile == None):
    print("ERROR: The -m arg is required!")
    clError+=1
else:
    # Make sure the file exists
    if (os.path.exists(clManifestFile) != True):
        print("ERROR: The manifest file given does not exist")
        clError+=1

# Look for output files
clOutputPath = cmdline.parseOptionWithArg("-o")
if (clOutputPath == None):
    print("ERROR: The -o arg is required")
    clError+=1

# Error check the command line
if (clError):
    print("ERROR: Missing/incorrect cmdline args!  Please review the output above to determine which ones!")
    exit(clError)

# All cmdline args should be processed, so if any left throw an error
if (len(sys.argv) != 1):
    print("ERROR: Extra cmdline args detected - %s" % (sys.argv[1:])) # [1:] don't inclue script name in the list
    exit(len(sys.argv))


################################################
# Work with the manifest

# Read in the manifest        
manifest = ET.parse(clManifestFile).getroot()

# Do some basic error checking of what we've read in

# Make sure the root starts with the vpd tag
if (manifest.tag != "vpd"):
    print("ERROR: The manifest file does not start with a <vpd> tag")
    exit(1)

# Print the top level tags from the parsing
print("Top level tag/attrib found")
for child in manifest:
    print("  ", child.tag, child.attrib)

# Let's make sure the required fields are found
# The <name></name> tag is required
if (manifest.find("name") == None):
    print("ERROR: top level tag <name></name> not found")
    exit(1)
else:
    # Stash away the name for easy access
    name = manifest.find("name").text

# The <size></size> tag is required
if (manifest.find("size") == None):
    print("ERROR: top level tag <size></size> not found")
    exit(1)

# At least one <record></record> tag is required
if (manifest.find("record") == None):
    print("ERROR: At least one top level tag <record></record> not found")
    exit(1)

# Read thru the record tags now and look for 1 of two cases
# A pointer to another file containing the record info to read in
# The actual record info in the file


#print("++++++++++++++++")
#print(ET.tostring(manifest))
#print("++++++++++++++++")

print("|||||||||||||||||||||||||||")

for desc in manifest.iter('kwdesc'):
    print(desc.tag, desc.attrib, desc.text)

if (clOutputPath != None):
    tree = ET.ElementTree(manifest)
    tree.write(clOutputPath + "/" + name + ".tvpd", encoding="utf-8", xml_declaration=True)


