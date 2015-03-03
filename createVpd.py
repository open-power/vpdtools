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
import struct
import re
import binascii

############################################################
# Function - Functions - Functions - Functions - Functions
############################################################
def help():
    print("createVpd.py")
    print("Required Args")
    print("Optional Args")
    print("-h|--help              This help text")

# Common function for error printing
def error(msg):
    print("ERROR: %s" % msg)

# Common function for debug printing
def debug(msg):
    print("DEBUG: %s" % msg)

# Write out the resultant tvpd xml file
def writeTvpd(manifest, outputFile):
    tree = ET.ElementTree(manifest)
    tree.write(outputFile, encoding="utf-8", xml_declaration=True)

# Parses a tvpd file using ET and then checks to ensure some basic required fields are present
def parseTvpd(tvpdFile, topLevel):
    # Read in the file
    tvpdRoot = ET.parse(tvpdFile).getroot()

    # Do some basic error checking of what we've read in
    # Make sure the root starts with the vpd tag
    if (tvpdRoot.tag != "vpd"):
        error("%s does not start with a <vpd> tag" % tvpdFile)
        return(1, None)

    # Print the top level tags from the parsing
    if (clDebug):
        debug("Top level tag/attrib found")
        for child in tvpdRoot:
            debug("  %s %s" % (child.tag, child.attrib))

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

def writeDataToVPD(vpdFile, data, offset = None):
    rc = 0

    # If the user gave an offset, save the current offset and seek to the new one
    entryOffset = None
    if (offset != None):
        entryOffset = vpdFile.tellg()
        vpdFile.seekg(offset)

    # Write the data
    vpdFile.write(data)

    # Restore the offset to original location if given
    if (offset != None):
        vpdFile.seekg(entryOffset)

    return rc

def writeKeywordToVPD(vpdFile, keyword, length, data, format):
    rc = 0

    # Write the keyword
    vpdFile.write(keyword.encode())
    # Write the length
    if (keyword[0] == "#"):
        vpdFile.write(struct.pack("<H", length))
    else:
        vpdFile.write(struct.pack("<B", length))
    # Write the data
    if (format == "ascii"):
        # Pad if necessary
        data = data.ljust(length, '\0')
        # Write it
        vpdFile.write(data.encode())
    elif (format == "hex"):
        # Pad if necessary (* 2 to convert nibble data to byte length)
        data = data.ljust((length * 2), '0')
        # Write it
        vpdFile.write(binascii.a2b_hex(data))
    else:
        error("Unknown format type %s passed into writeKeywordToVPD" % format)
        return 1

    return 0

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

clDebug = cmdline.parseOption("-d", "--debug")

# We can run in two different modes
# 1) manifest mode - you pass in one xml file that gives all the required input args
# 2) cmdline mode - you pass in multiple command line args that recreate what would be in the manifest - might not be needed
# For now let's get manifest mode working since that will be the easiest

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

print("==== Stage 1: Loading manifest file")
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
        # ET doesn't have a replace function.  You can do an extend/remove, but that changes the order of the file
        # The goal is to preserve record & keyword order, so this method doesn't work
        # The below code will insert the refrenced record from the file in the list above the current record location
        # Then remove the original record, preserving order
        # Since the referenced file also starts with <vpd> tag, you need to get one level down and find the start of the record element, hence the find
        subRecord = recordTvpd.find("record");
        manifest.insert(list(manifest).index(record), subRecord)
        manifest.remove(record)

print("==== Stage 2: Verifying manifest syntax")
# Now read thru our expanded tvpd and verify/error check syntax
errorsFound = 0
# Keep a dictionary of the record names we come across, will let us find duplicates
recordNames = dict()
# Loop thru our records and then thru the keywords in each record
for record in manifest.iter("record"):
    # Pull the record name out for use throughout
    recordName = record.attrib.get("name")
    
    # --------
    # Make sure we aren't finding a record we haven't already seen
    if (recordName in recordNames):
        error("The record \"%s\" has previously been defined in the tvpd" % recordName)
        errorsFound+=1
    else:
        recordNames[recordName] = 1

    # --------
    # Make sure the record name is 4 charaters long
    if (len(recordName) != 4):
        error("The record name entry \"%s\" is not 4 characters long" % record.attrib.get("name"))
        errorsFound+=1

    # --------
    # Loop through the keywords and verify them
    for keyword in record.iter("keyword"):
        # Pull the keyword name out for use throughout
        keywordName = keyword.attrib.get("name")

        # Setup a dictionary of the supported tags
        kwTags = {"keyword" : False, "kwdesc" : False, "kwformat" : False, "kwlen" : False, "kwvalue" : False}

        # --------
        # We'll loop through all the tags found in this keyword and check for both required and extra ones
        for kw in keyword.iter():
            if kw.tag in kwTags:
                # Mark that we found a required tag
                kwTags[kw.tag] = True
                # Save the values we'll need into variables for ease of use
                if (kw.tag == "kwformat"):
                    kwformat = kw.text
                    kwformat = kwformat.lower()

                if (kw.tag == "kwlen"):
                    kwlen = int(kw.text)

                if (kw.tag == "kwvalue"):
                    kwvalue = kw.text

            else:
                # Flag that we found an unsupported tag.  This may help catch typos, etc..
                error("The unsupported tag \"<%s>\" was found in keyword %s in record %s" % (kw.tag, keywordName, recordName))
                errorsFound+=1
                
        # --------
        # Make sure all the required kwTags were found
        for kw in kwTags:
            if (kwTags[kw] == False):
                error("Required tag \"<%s>\" was not found in keyword %s in record %s" % (kw, keywordName, recordName))
                errorsFound+=1

        # --------
        # Now we know the basics of the template are correct, now do more indepth checking of length, etc..
        # A check to make sure the RT keyword kwvalue matches the name of the record we are in
        if ((keywordName == "RT") and (recordName != kwvalue)):
            error("The value of the RT keyword \"%s\" does not match the record name \"%s\"" % (kwvalue, recordName))
            errorsFound+=1

        # --------
        # Check that the length specified isn't longer than the keyword supports
        # Keywords that start with # are 2 bytes, others are 1 byte
        if (keywordName[0] == "#"):
            maxlen = 65535
        else:
            maxlen = 255
        if (kwlen >= maxlen):
                error("The specified length %d is bigger than the max length %d for keyword %s in record %s" % (kwlen, maxlen, keywordName, recordName))
                errorsFound+=1

        # --------
        # If the input format is hex, make sure the input data is hex only
        if (kwformat == "hex"):
            # Remove white space from the kwvalue for now and future checks
            kwvalue = kwvalue.replace(" ","")
            kwvalue = kwvalue.replace("\n","")
            # Now look to see if there are any characters other than 0-9 & a-f
            match = re.search("([g-zG-Z]+)", kwvalue)
            if (match):
                error("A non hex character \"%s\" was found at %s in the kwvalue for keyword %s in record %s" % (match.group(), match.span(), keywordName, recordName))
                errorsFound+=1

        # --------
        # Verify that the data isn't longer than the length given
        # Future checks could include making sure hex data is hex
        if (kwformat == "ascii"):
            if (len(kwvalue) > kwlen):
                error("The length of the value is longer than the given <kwlen> for keyword %s in record %s" % (keywordName, recordName))
                errorsFound+=1
        elif (kwformat == "hex"):
            # Convert hex nibbles to bytes for len compare
            if ((len(kwvalue)/2) > kwlen):
                error("The length of the value is longer than the given <kwlen> for keyword %s in record %s" % (keywordName, recordName))
                errorsFound+=1
        else:
            error("Unknown keyword format \"%s\" given for keyword %s in record %s" % (kwformat, keywordName, recordName))
            errorsFound+=1

if (errorsFound):
    error("%d error%s found in the tvpd description.  Please review the above errors and correct them." % (errorsFound, "s" if (errorsFound > 1) else ""))
    tvpdFileName = clOutputPath + "/" + name + "-err.tvpd"
    writeTvpd(manifest, tvpdFileName)
    print("Wrote tvpd file: %s" % tvpdFileName)
    exit(errorsFound)

print("==== Stage 3: Writing files")
tvpdFileName = clOutputPath + "/" + name + ".tvpd"
vpdFileName = clOutputPath + "/" + name + ".vpd"
for desc in manifest.iter('kwdesc'):
    print(desc.tag, desc.attrib, desc.text)

# Write out the full template vpd representing the data contained in our image
writeTvpd(manifest, tvpdFileName)
print("  Wrote tvpd file: %s" % tvpdFileName)

# Write out the binary file
# Open up our file to write
vpdFile = open(vpdFileName, "wb")

# Now to create the VPD image
# This could be done by starting at offset 0 and just writing all the needed data to the file in order
# However, The VTOC record depends upon knowing the offsets of all the other records - which haven't been created
# We could write the VTOC with place holder data, then come back and update those fields later
# That would involve 1) creating a tracking variables for all 5 required offsets for each record and then circling back to update the VTOC
#
# Instead, I purpose creating the images for each record first and storing them in memory
# Then we can go through and create the full VPD image in sequence and be able to write the VTOC properly the first time

# Write the ECC block
writeDataToVPD(vpdFile, binascii.a2b_hex("0000000000000000000000"))
# Write the Large Resource Tag
writeDataToVPD(vpdFile, struct.pack('>B', 0x84))
# Write the Record Length
writeDataToVPD(vpdFile, struct.pack('<H', 40))
# Write the RT keyword
writeKeywordToVPD(vpdFile, "RT", 4, "VHDR", "ascii")
# Write the VD keyword
writeKeywordToVPD(vpdFile, "VD", 2, "01", "hex")
# Write the PT keyword
writeKeywordToVPD(vpdFile, "PT", 14, "VHDR", "ascii")

record = bytearray("hi".encode()) + bytearray(" bye".encode())
record += bytearray("this might word".encode())
record += binascii.a2b_hex("0123")

print(record)


exit(0)
#writeVPDData(vpdFile, data, offset = None)

# Write the keyword
#writeKeyword(vpdFile, keyword, length, data, format)

# Now write out all the records
for record in manifest.iter("record"):
    print("record:", record.tag, record.attrib, record.text)
    for keyword in record.iter("keyword"):
        print("  keyword:", keyword.tag, keyword.attrib, keyword.text)
        print("  keyword:", keyword.find("kwdesc").text)
            
        # Write the keyword
        print("keyword attrib is %s" % keyword.attrib.get("name"))
        vpdFile.write(keyword.attrib.get("name").encode())
        # Write the length of the data
        datavalue = keyword.find("kwvalue").text
        print("keyword length is %d" % len(datavalue))
        datalen = len(datavalue)
        vpdFile.write(struct.pack('B', datalen))
        # Write the data
        vpdFile.write(datavalue.encode())

# Done with the file
vpdFile.close()
print("  Wrote vpd file: %s" % vpdFileName)

