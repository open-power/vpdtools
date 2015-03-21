#!/usr/bin/env python
# Created 03/20/15 by Jason Albert
# Program to deconstruct a VPD image into template files

############################################################
# Imports - Imports - Imports - Imports - Imports - Imports
############################################################
import os
# Get the path the script resides in
scriptPath = os.path.dirname(os.path.realpath(__file__))
import sys
sys.path.insert(0,scriptPath + "/pymod");
import cmdline
import out
import xml.etree.ElementTree as ET
import struct
import re
import binascii

############################################################
# Classes - Classes - Classes - Classes - Classes - Classes
############################################################
class RecordInfo:
    """Stores the info about each vpd record"""
    def __init__(self):
        # The name of the record where the toc entry is located
        self.tocName = None
        # The location of the Record Offset
        self.recordOffset = None
        # The location of the Record Length
        self.recordLength = None
        # The location of the ECC Offset
        self.eccOffset = None
        # The location of the ECC Length
        self.eccLength = None

############################################################
# Function - Functions - Functions - Functions - Functions
############################################################
def help():
    out.msg("reverseVpd.py -v image.vpd -o outputpath -d")
    out.msg("Required Args")
    out.setIndent(2)
    out.msg("-v|--vpdfile           The valid vpd formatted input file")
    out.msg("-o|--outpath           The output path for the files created by the tool")
    out.setIndent(0)
    out.msg("Optional Args")
    out.setIndent(2)
    out.msg("-d|--debug             Enables debug printing")
    out.msg("-h|--help              This help text")
    out.msg("-r|--create-records    Create tvpd files for each record in the vpd")
    out.setIndent(0)

# Function to write out the resultant tvpd xml file
def writeTvpd(manifest, outputFile):
    tree = ET.ElementTree(manifest)
    tree.write(outputFile, encoding="utf-8", xml_declaration=True)
    return None

############################################################
# Main - Main - Main - Main - Main - Main - Main - Main
############################################################
rc = 0

################################################
# Command line options
clErrors = 0

# Help text
if (cmdline.parseOption("-h","--help")):
    help()
    exit(0)

# Get the manifest file and get this party started
clVpdFile = cmdline.parseOptionWithArg("-v", "--vpdfile")
if (clVpdFile == None):
    out.error("The -v arg is required!")
    clErrors+=1

# Look for output path
clOutputPath = cmdline.parseOptionWithArg("-o", "--outpath")
if (clOutputPath == None):
    out.error("The -o arg is required")
    clErrors+=1
else:
    # Make sure the path exists, we aren't going to create it
    if (os.path.exists(clOutputPath) != True):
        out.error("The given output path %s does not exist!" % clOutputPath)
        out.error("Please create the output directory and run again")
        clErrors+=1

# Error check the command line
if (clErrors):
    out.error("Missing/incorrect required cmdline args!  Please review the output above to determine which ones!")
    exit(clErrors)

# Debug printing
clDebug = cmdline.parseOption("-d", "--debug")

# Create separate binary files for each record
clBinaryRecords = cmdline.parseOption("-r", "--create-records")

# All cmdline args should be processed, so if any left throw an error
if (len(sys.argv) != 1):
    out.error("Extra cmdline args detected - %s" % (sys.argv[1:])) # [1:] don't inclue script name in the list
    exit(len(sys.argv))

################################################
# Read in the VPD file and break it apart
out.setIndent(0)
out.msg("==== Stage 1: Parsing the VPD file")
out.setIndent(2)

# Create our output name from the input name
vpdName = os.path.splitext(os.path.basename(clVpdFile))[0]

# Open the vpdfile
vpdContents = open(clVpdFile, mode='rb').read()

# Jump right to where the VTOC should be and make sure it says VTOC
offset = 61
if (vpdContents[offset:(offset+4)].decode() != "VTOC"):
    out.error("Did not find VTOC at the expected offset!")
    exit(1)
offset+=4

# Skip the PT keyword and read the 1 byte length to loop over the VTOC contents and create our record list
offset+=2 # PT skip
tocLength = vpdContents[offset]
print("tocLength: %d" % tocLength)
offset+=1

# Keep a dictionary of the record names we come across
recordNames = dict()

# Loop through the toc and read out the record locations
tocOffset = 0
while (tocOffset < tocLength):
    # Get the record name
    recordName = vpdContents[(tocOffset + offset):(tocOffset + offset + 4)].decode()
    # Create the entry with the name
    recordNames[recordName] = RecordInfo()
    tocOffset+=4
    # Skip the record type
    tocOffset+=2
    # recordOffset
    recordNames[recordName].recordOffset = struct.unpack('<H', vpdContents[(tocOffset + offset):(tocOffset + offset + 2)])[0]
    print("recordOffset: ", recordNames[recordName].recordOffset)
    tocOffset+=2
    # recordLength
    recordNames[recordName].recordLength = struct.unpack('<H', vpdContents[(tocOffset + offset):(tocOffset + offset + 2)])[0]
    tocOffset+=2
    # eccOffset
    recordNames[recordName].eccOffset = struct.unpack('<H', vpdContents[(tocOffset + offset):(tocOffset + offset + 2)])[0]
    tocOffset+=2
    # eccLength
    recordNames[recordName].eccLength = struct.unpack('<H', vpdContents[(tocOffset + offset):(tocOffset + offset + 2)])[0]
    tocOffset+=2
    
# We have all the record offsets in memory along with the entire VPD image.
# Go onto our next step and create XML in memory

################################################
# Create tvpd XML
out.setIndent(0)
out.msg("==== Stage 2: Creating tvpd XML")
out.setIndent(2)

# Create our top level level XML
vpd = ET.Element("vpd")

# Loop thru our records and create our record/keyword entries
for recordName in recordNames:
    # Create our record
    record=ET.SubElement(vpd, "record", {'name':recordName})

    # Start walking thru our record reading keywords out
    # As we get to each keyword, we'll create the keyword tag and it's sub tags
    recordOffset = recordNames[recordName].recordOffset

    # Skip the LR tag
    recordOffset+=1

    # Get the length
    recordLength = struct.unpack('<H', vpdContents[recordOffset:(recordOffset + 2)])[0]
    recordOffset+=2

    # Now loop and read until we get until the end of the record
    recordEnd = recordOffset + recordLength
    print("recordOffset: %d, recordLength: %d" % (recordOffset, recordLength))
    while (recordOffset < recordEnd):
        # Read the keyword
        keywordName = vpdContents[recordOffset:(recordOffset + 2)].decode()
        print("keyword: %s" % keywordName)
        recordOffset+=2

        # Determine if length is 1 or 2 bytes
        if (keywordName[0] == "#"):
            keywordLength = struct.unpack('<H', vpdContents[recordOffset:(recordOffset + 2)])[0]
            recordOffset+=2
        else:
            keywordLength = vpdContents[recordOffset]
            recordOffset+=1

        # Get the keyword data out
        keywordData = vpdContents[recordOffset:(recordOffset + keywordLength)]
        recordOffset+=keywordLength

        # If the keyword is PF, we are at the end at skip it
        if (keywordName == "PF"):
            continue

        # Create our keyword tag and subtags
        keyword=ET.SubElement(record, "keyword", {"name":keywordName})
        ET.SubElement(keyword, "kwdesc").text = "The " + keywordName + " keyword"
        allAscii = keywordData.isalpha()
        if (allAscii):
            ET.SubElement(keyword, "kwformat").text = "ascii"
        else:
            ET.SubElement(keyword, "kwformat").text = "hex"
        ET.SubElement(keyword, "kwlen").text = str(keywordLength)
        if (allAscii):
            ET.SubElement(keyword, "kwdata").text = keywordData.decode()
        else:
            ET.SubElement(keyword, "kwdata").text = binascii.hexlify(keywordData)

    # We should be done with all the keywords, which means it's pointing to the SR tag
    if (vpdContents[recordOffset] != 0x78):
        out.error("Small resource tag not found!")
        exit(1)

# We now have a correct tvpd, use it to create a binary VPD image
out.setIndent(0)
out.msg("==== Stage 3: Writing the tvpd output file")
out.setIndent(2)
# Create our output file names 
tvpdFileName = clOutputPath + "/" + vpdName + ".tvpd"

# This is our easy one, write the XML back out
# Write out the full template vpd representing the data contained in our image
writeTvpd(vpd, tvpdFileName)
out.msg("Wrote tvpd file: %s" % tvpdFileName)

