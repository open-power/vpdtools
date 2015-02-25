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
import struct

############################################################
# Function - Functions - Functions - Functions - Functions
############################################################
def help():
    print("createVpd.py")
    print("Required Args")
    print("Optional Args")
    print("-h|--help              This help text")

def error(msg):
    print("ERROR: %s" % msg)

def debug(msg):
    print("DEBUG: %s" % msg)

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

def parseTvpd(tvpdFile, topLevel):
    tvpdRoot = ET.parse(tvpdFile).getroot()

    # Do some basic error checking of what we've read in

    # Make sure the root starts with the vpd tag
    if (tvpdRoot.tag != "vpd"):
        error("%s does not start with a <vpd> tag" % tvpdFile)
        return(1, None)

    # Print the top level tags from the parsing
    print("Top level tag/attrib found")
    for child in tvpdRoot:
        print("  ", child.tag, child.attrib)

    # Let's make sure the required fields are found
    # Some are only required in a top level file, not when it's just an individual record file
    # The <name></name> tag is required
    if (topLevel == True):
        if (tvpdRoot.find("name") == None):
            error("top level tag <name></name> not found")
            return(1, None)

        # The <size></size> tag is required
        if (tvpdRoot.find("size") == None):
            error("top level tag <size></size> not found")
            return(1, None)

    # At least one <record></record> tag is required
    if (tvpdRoot.find("record") == None):
        error("At least one top level tag <record></record> not found")
        return(1, None)

    # The file is good
    return(0, tvpdRoot)

    

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
    error("The -m arg is required!")
    clError+=1
else:
    # Make sure the file exists
    if (os.path.exists(clManifestFile) != True):
        error("The manifest file given does not exist")
        clError+=1

# Look for output files
clOutputPath = cmdline.parseOptionWithArg("-o")
if (clOutputPath == None):
    error("The -o arg is required")
    clError+=1

# Error check the command line
if (clError):
    error("Missing/incorrect cmdline args!  Please review the output above to determine which ones!")
    exit(clError)

# All cmdline args should be processed, so if any left throw an error
if (len(sys.argv) != 1):
    error("Extra cmdline args detected - %s" % (sys.argv[1:])) # [1:] don't inclue script name in the list
    exit(len(sys.argv))


################################################
# Work with the manifest

# Read in the manifest 
(rc, manifest) = parseTvpd(clManifestFile, True)
if (rc):
    error("Error occurred reading in the manifest!")
    exit(rc)

# Stash away some variables for use later
name = manifest.find("name").text

# We need to read in/create all the records
# Then we need to parse thru them all and make sure they are correct
# Then loop thru again and write out the data
# Doing this as two stages of looping so all errors can be surfaced at once instead of iteratively
# The first pass will also allow for calculation of total record sizes to help in the creation of the VTOC during write phase.

# Look for reference files
for record in manifest.iter("record"):
    src = record.find("src")
    if (src != None):
        # We have a reference to a different file, read that in
        (rc, recordTvpd) = parseTvpd(src.text, False)
        if (rc):
            error("Error occurred reading in %s" % src.text)
            exit(rc)
        # Now merge the main manifest with the new record
        #manifest.extend(recordTvpd)
        #manifest.remove(record)
        subRecord = recordTvpd.find("record");
        manifest.insert(list(manifest).index(record), subRecord)
        manifest.remove(record)

#print("++++++++++++++++")
#print(ET.tostring(manifest))
#print("++++++++++++++++")

print("|||||||||||||||||||||||||||")

for desc in manifest.iter('kwdesc'):
    print(desc.tag, desc.attrib, desc.text)

# Write out the full template vpd representing the data contained in our image
if (clOutputPath != None):
    tree = ET.ElementTree(manifest)
    tree.write(clOutputPath + "/" + name + ".tvpd", encoding="utf-8", xml_declaration=True)

# Write out the binary file
if (clOutputPath != None):
    # Open up our file to write
    vpdFile = open(clOutputPath + "/" + name + ".vpd", "wb")
    for record in manifest.iter("record"):
        print("record:", record.tag, record.attrib, record.text)
        for keyword in record.iter("keyword"):
            print("  keyword:", keyword.tag, keyword.attrib, keyword.text)
            print("  keyword:", keyword.find("kwdesc"))
            
            # Write the keyword
            print("keyword attrib is %s" % keyword.attrib.get("name"))
            vpdFile.write(keyword.attrib.get("name").encode())
            # Write the length of the data
            datavalue = keyword.find("datavalue").text
            print("keyword length is %d" % len(datavalue))
            datalen = len(datavalue)
            vpdFile.write(struct.pack('B', datalen))
            # Write the data
            vpdFile.write(datavalue.encode())

    # Done with the file
    vpdFile.close()
