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

############################################################
# Classes - Classes - Classes - Classes - Classes - Classes
############################################################
class RecordInfo:
    """Stores the info about each vpd record"""
    def __init__(self):
        # The packed record in memory
        self.record = bytearray()
        # The packed ecc in memory
        self.ecc = bytearray()
        # The name of the record where the toc entry is located
        self.tocName = None
        # The location of the Record Offset in toc record
        self.tocRecordOffset = None
        # The location of the Record Length in toc record
        self.tocRecordLength = None
        # The location of the ECC Offset in toc record
        self.tocEccOffset = None
        # The location of the ECC Length in toc record
        self.tocEccLength = None

############################################################
# Function - Functions - Functions - Functions - Functions
############################################################
def help():
    print("createVpd.py -m manifest.tvpd -o outputpath -d")
    print("Required Args")
    print("-m|--manifest          The input file detailing all the records and keywords to be in the image")
    print("-o|--outpath           The output path for the files created by the tool")
    print("Optional Args")
    print("-d|--debug             Enables debug printing")
    print("-h|--help              This help text")

# Common function for error printing
def error(msg):
    print("ERROR: %s" % msg)

# Common function for debug printing
def debug(msg):
    print("DEBUG: %s" % msg)

# Function to Write out the resultant tvpd xml file
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

    # Make sure the required fields are found
    # Some are only required in a top level file, not when it's just an individual record file
    if (topLevel == True):
        # The <name></name> tag is required
        if (tvpdRoot.find("name") == None):
            error("<name></name> tag required but not found - %s" % tvpdFile)
            return(1, None)

        # The <size></size> tag is required
        if (tvpdRoot.find("size") == None):
            error("<size></size> tag required but not found - %s" % tvpdFile)
            return(1, None)
    else:
        # The <name></name> tag shouldn't be there
        if (tvpdRoot.find("name") != None):
            error("<name></name> tag found when it should not be - %s" % tvpdFile)
            return(1, None)

        # The <size></size> tag shouldn't be there
        if (tvpdRoot.find("size") == None):
            error("<size></size> tag found when it should not be - %s" % tvpdFile)
            return(1, None)


    # At least one <record></record> tag is required
    if (tvpdRoot.find("record") == None):
        error("At least one <record></record> tag not found - %s" % tvpdFile)
        return(1, None)

    # The file is good
    return(0, tvpdRoot)

# Function to write properly packed/encoded data to the vpdFile
def writeDataToVPD(vpdFile, data, offset = None):
    rc = 0

    # If the user gave an offset, save the current offset and seek to the new one
    entryOffset = None
    if (offset != None):
        entryOffset = vpdFile.tell()
        vpdFile.seekg(offset)

    # Write the data
    vpdFile.write(data)

    # Restore the offset to original location if given
    if (offset != None):
        vpdFile.seekg(entryOffset)

    return rc

# Turn the tvpd keyword data into packed binary data we can write to the file
def packKeyword(keyword, length, data, format):
    # We'll return a bytearray of the packed data
    keywordPack = bytearray()

    # Write the keyword
    keywordPack += bytearray(keyword.encode())
    
    # Write the length
    # The < at the front says to pack it little endian
    if (keyword[0] == "#"):
        # H is 2 bytes
        keywordPack += struct.pack("<H", length)
    else:
        # B is 1 byte
        keywordPack += struct.pack("<B", length)

    # Write the data
    # If the user didn't provide data = length given, we'll pad the end with 0's
    if (format == "ascii"):
        # Pad if necessary
        data = data.ljust(length, '\0')
        # Write it
        keywordPack += bytearray(data.encode())
    elif (format == "hex"):
        # fromhex will deal with spacing in the data, but not carriage returns
        # Remove those before we get to fromhex
        data = data.replace("\n","")
        # Pad if necessary (* 2 to convert nibble data to byte length)
        data = data.ljust((length * 2), '0')
        # Write it
        keywordPack += bytearray.fromhex(data)
    else:
        error("Unknown format type %s passed into packKeyword" % format)
        return NULL

    # The keyword is packed, send it back
    return keywordPack

# Calculate the length of the PF record
def calcPadFill(record):
    pfLength = 0

    # The PF keyword must exist
    # The keyword section of record must be at least 40 bytes long, padfill will be used to acheive that
    # If the keyword section is over over 40, it must be aligned on word boundaries and PF accomplishes that

    # The record passed in at this point is the keywords + 3 other bytes (LR Tag & Record Length)
    # Those 3 bytes happen to match the length of the PF keyword and its length
    # So we'll just use the length of the record, but it's due to those offsetting lengths of 3
    pfLength = 40 - len(record)
    if (pfLength < 1):
        # It's > 40, so now we just need to fill to nearest word
        pfLength = (4 - (len(record) % 4))

    return pfLength

############################################################
# Main - Main - Main - Main - Main - Main - Main - Main
############################################################
rc = 0
# Get the path the script is being called from
cwd = os.path.dirname(os.path.abspath(__file__))

################################################
# Command line options
clErrors = 0

# Help text
if (cmdline.parseOption("-h","--help")):
    help()
    exit(0)

# Debug printing
clDebug = cmdline.parseOption("-d", "--debug")

# We could possibly run in two different modes
# 1) manifest mode - the user passes in one xml file that gives all the required input args
# 2) cmdline mode - the user passes in multiple command line args that recreate what would be in the manifest
# 1 is the easiest option to start with, and maybe all that is needed.  We start with manifest mode!

# Get the manifest file and get this party started
clManifestFile = cmdline.parseOptionWithArg("-m", "--manifest")
if (clManifestFile == None):
    error("The -m arg is required!")
    clErrors+=1
else:
    # Make sure the file exists
    if (os.path.exists(clManifestFile) != True):
        error("The manifest file given does not exist")
        clErrors+=1

# Look for output path
clOutputPath = cmdline.parseOptionWithArg("-o", "--outpath")
if (clOutputPath == None):
    error("The -o arg is required")
    clErrors+=1

# Error check the command line
if (clErrors):
    error("Missing/incorrect cmdline args!  Please review the output above to determine which ones!")
    exit(clErrors)

# All cmdline args should be processed, so if any left throw an error
if (len(sys.argv) != 1):
    error("Extra cmdline args detected - %s" % (sys.argv[1:])) # [1:] don't inclue script name in the list
    exit(len(sys.argv))

# We are going to do this in 3 stages
# 1 - Read in the manifest and any other referenced files.  This will create a complete XML description of the VPD
# 2 - Parse thru the XML records and make sure they are correct.  Also check things like data not greater than length, etc..
# 3 - With the XML verified correct, loop thru it again and write out the VPD data
# Looping thru the XML twice lets all errors be surfaced to the user in stage 2 at once instead of one at a time

################################################
# Work with the manifest
print("==== Stage 1: Loading manifest file")
# Read in the manifest 
(rc, manifest) = parseTvpd(clManifestFile, True)
if (rc):
    error("Problem reading in the manifest! - %s" % clManifestFile)
    exit(rc)

# Stash away some variables for use later
vpdName = manifest.find("name").text

# Look for reference files
for record in manifest.iter("record"):
    src = record.find("src")
    if (src != None):
        # We have a reference to a different file, read that in
        (rc, recordTvpd) = parseTvpd(src.text, False)
        if (rc):
            error("Error occurred reading in %s" % src.text)
            exit(rc)
        # Merge the new record into the main manifest
        # ET doesn't have a replace function.  You can do an extend/remove, but that changes the order of the file
        # The goal is to preserve record & keyword order, so that method doesn't work
        # The below code will insert the refrenced record from the file in the list above the current record location
        # Then remove the original record, preserving order
        # Since the referenced file also starts with <vpd> tag, you need to get one level down and find the start of the record element, hence the find
        subRecord = recordTvpd.find("record");
        manifest.insert(list(manifest).index(record), subRecord)
        manifest.remove(record)

################################################
# Verify the tvpd XML
# read thru the complete tvpd and verify/error check
print("==== Stage 2: Verifying manifest syntax")
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
        error("The record name entry \"%s\" is not 4 characters long" % recordName)
        errorsFound+=1

    # Loop through the keywords and verify them
    for keyword in record.iter("keyword"):
        # Pull the keyword name out for use throughout
        keywordName = keyword.attrib.get("name")

        # Setup a dictionary of the supported tags
        kwTags = {"keyword" : False, "kwdesc" : False, "kwformat" : False, "kwlen" : False, "kwvalue" : False}

        # --------
        # We'll loop through all the tags found in this keyword and check for all required and any extra ones
        for kw in keyword.iter():
            if kw.tag in kwTags:
                # Mark that we found a required tag
                kwTags[kw.tag] = True
                # Save the values we'll need into variables for ease of use
                if (kw.tag == "kwformat"):
                    kwformat = kw.text.lower() # lower() for ease of compare

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
        if (kwlen > maxlen):
            error("The specified length %d is bigger than the max length %d for keyword %s in record %s" % (kwlen, maxlen, keywordName, recordName))
            errorsFound+=1

        # --------
        # If the input format is hex, make sure the input data is hex only
        if (kwformat == "hex"):
            # Remove white space and carriage returns from the kwvalue
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
    tvpdFileName = clOutputPath + "/" + vpdName + "-err.tvpd"
    writeTvpd(manifest, tvpdFileName)
    print("Wrote tvpd file to help in debug: %s" % tvpdFileName)
    exit(errorsFound)

# We now have a correct tvpd, use it to create a binary VPD image
print("==== Stage 3: Creating binary VPD image")
# Create ourput file names 
tvpdFileName = clOutputPath + "/" + vpdName + ".tvpd"
vpdFileName = clOutputPath + "/" + vpdName + ".vpd"

if (clDebug):
    for desc in manifest.iter('kwdesc'):
        print(desc.tag, desc.attrib, desc.text)

# This is our easy one, write the XML back out
# Write out the full template vpd representing the data contained in our image
writeTvpd(manifest, tvpdFileName)
print("  Wrote tvpd file: %s" % tvpdFileName)

# Now the hard part, write out the binary file
# Open up our file to write
vpdFile = open(vpdFileName, "wb")

# Process for creating the binary file
# There are 2 ways the file could be created
# 1 - write the data to file on disk as the records are created
# 2 - write the data to memory and then write the complete image at the end
# Option 2 was selected for a few reasons
# - This isn't a large amount of data where flushing to disk as we went along would help performance
# - When the TOC entries are created, we don't know the offset/length to provide.  This has to be updated later
#   By keeping the records in memory, it's marginally easier to update the TOC info since you don't have to manage file position
# - While ECC isn't supported now, if it is needed in the future, the entire record will be available in memory for the algoritm
#   If writing to the file was done, the data would have to be read back and sent to the ECC algorithm
#
# The rest of this process is pretty straight forward.  There are some helper functions implemented at the top of the file
# The most difficult piece is tracking the total image size and managing the TOC offset locations so they can be later updated

# Our dictionary of all the records we've created in memory, along with info like TOC offsets
recordInfo = dict()
# Track total image size as the various records are created
imageSize = 0

# The VHDR and VTOC are created by the tool based upon the info in the tvpd
# The rest of the records are derived from the tvpd

################################################
# Create VHDR
recordName = "VHDR"
recordInfo[recordName] = RecordInfo()

# Create the ECC block
recordInfo[recordName].record += bytearray(bytearray.fromhex("0000000000000000000000"))
# Create the Large Resource Tag
recordInfo[recordName].record += bytearray(bytearray.fromhex("84"))
# Create the Record Length
recordInfo[recordName].record += struct.pack('<H', 40) # VHDR is always 40
# Create the RT keyword
recordInfo[recordName].record += packKeyword("RT", 4, recordName, "ascii")
# Create the VD keyword
recordInfo[recordName].record += packKeyword("VD", 2, "01", "hex")
# Create the PT keyword
# Since we are creating a TOC entry here, we'll need to create the RecordInfo for the record it will be pointing to
# This will allow us to store the TOC offsets and update them later when the record gets created
recordInfo["VTOC"] = RecordInfo()
recordInfo["VTOC"].tocName = "VHDR"
# The tocOffset starts where the data in the PT keyword starts
tocOffset = len(recordInfo[recordName].record) + 3 # PT (2) + Length (1)
tocOffset += 6 # Record Name (4) + Record Type (2)
recordInfo["VTOC"].tocRecordOffset = tocOffset
tocOffset += 2
recordInfo["VTOC"].tocRecordLength = tocOffset
tocOffset += 2
recordInfo["VTOC"].tocEccOffset = tocOffset
tocOffset += 2
recordInfo["VTOC"].tocEccLength = tocOffset
tocOffset += 2
recordInfo[recordName].record += packKeyword("PT", 14, "VTOC", "ascii")
# Create the PF keyword
# This PF is fixed at 8 since the VHDR is always 44 long.
recordInfo[recordName].record += packKeyword("PF", 8, "0", "hex")
# Create the Small Resource Tag
recordInfo[recordName].record += bytearray(bytearray.fromhex("78"))

# Update our total image size
imageSize += len(recordInfo[recordName].record)

################################################
# Create VTOC
recordName = "VTOC"
# No need to create the VTOC recordInfo entry since it was done by the VHDR

# Create the Large Resource Tag
recordInfo[recordName].record += bytearray(bytearray.fromhex("84"))
# Create the Record Length
# We will come back and update this at the end
recordInfo[recordName].record += bytearray(bytearray.fromhex("0000"))
# Create the RT keyword
recordInfo[recordName].record += packKeyword("RT", 4, recordName, "ascii")

# Create the PT keyword
# We need to create all the data that will go into the PT keyword.  We'll create a big ascii string by looping over all the records
PTData = ""
# We'll also use the loop to create all our recordInfos and store the TOC offsets
# The tocOffset starts where the data in the PT keyword starts
tocOffset = len(recordInfo[recordName].record) + 3 # PT (2) + Length (1)

# The VTOC has the pointers to all the records described in the tvpd
for record in manifest.iter("record"):
    loopRecordName = record.attrib.get("name")
    PTData += loopRecordName + "\0\0\0\0\0\0\0\0\0\0" # The name, plus 10 empty bytes to be updated later

    # Since we are creating a TOC entry here, we'll need to create the RecordInfo for the records it will be pointing to
    # This will allow us to store the TOC offsets and update them later when the record gets created
    recordInfo[loopRecordName] = RecordInfo()
    recordInfo[loopRecordName].tocName = recordName
    tocOffset += 6 # Record Name (4) + Record Type (2)
    recordInfo[loopRecordName].tocRecordOffset = tocOffset
    tocOffset += 2
    recordInfo[loopRecordName].tocRecordLength = tocOffset
    tocOffset += 2
    recordInfo[loopRecordName].tocEccOffset = tocOffset
    tocOffset += 2
    recordInfo[loopRecordName].tocEccLength = tocOffset
    tocOffset += 2
recordInfo[recordName].record += packKeyword("PT", len(PTData), PTData, "ascii")

# Create the PF keyword
padfillSize = calcPadFill(recordInfo[recordName].record)
recordInfo[recordName].record += packKeyword("PF", padfillSize, "0", "hex")

# Create the Small Resource Tag
recordInfo[recordName].record += bytearray(bytearray.fromhex("78"))

# Update the record length
# Total length minus 4, LR(1), SR(1), Length (2)
recordLength = len(recordInfo[recordName].record) - 4
recordInfo[recordName].record[1:3] = struct.pack('<H', recordLength)

# Go back and update all our TOC info now that the record is created
tocName = recordInfo[recordName].tocName
# Image size hasn't been updated since the end of the last record, so it points to the start of our new record
tocRecordOffset = recordInfo[recordName].tocRecordOffset
recordInfo[tocName].record[tocRecordOffset:(tocRecordOffset + 2)] = struct.pack('>H', imageSize)
# The record is complete, so we can just use the length
tocRecordLength = recordInfo[recordName].tocRecordLength
recordInfo[tocName].record[tocRecordLength:(tocRecordLength + 2)] = struct.pack('>H', len(recordInfo[recordName].record))

# Update our total image size
imageSize += len(recordInfo[recordName].record)

################################################
# Create the remaining records from the tvpd
for record in manifest.iter("record"):
    recordName = record.attrib.get("name")

    # The large resource tag
    recordInfo[recordName].record += bytearray(bytearray.fromhex("84"))

    # The record length, we will come back and update this at the end
    recordInfo[recordName].record += bytearray(bytearray.fromhex("0000"))

    # The keywords
    keywordsLength = 0
    for keyword in record.iter("keyword"):
        keywordPack = packKeyword(keyword.attrib.get("name"), int(keyword.find("kwlen").text), keyword.find("kwvalue").text, keyword.find("kwformat").text)
        recordInfo[recordName].record += keywordPack
        keywordsLength += len(keywordPack)

    # Calculate the padfill required
    padfillSize = calcPadFill(recordInfo[recordName].record)

    # Write the PF keyword
    keywordPack = packKeyword("PF", padfillSize, "0", "hex")
    recordInfo[recordName].record += keywordPack

    # The small resource tag
    recordInfo[recordName].record += bytearray(bytearray.fromhex("78"))

    # Update the record length
    # Total length minus 4, LR(1), SR(1), Length (2)
    recordLength = len(recordInfo[recordName].record) - 4
    recordInfo[recordName].record[1:3] = struct.pack('<H', recordLength)

    # Go back and update all our TOC info now that the record is created
    tocName = recordInfo[recordName].tocName
    # Image size hasn't been updated since the end of the last record, so it points to the start of our new record
    tocRecordOffset = recordInfo[recordName].tocRecordOffset
    recordInfo[tocName].record[tocRecordOffset:(tocRecordOffset + 2)] = struct.pack('>H', imageSize)
    # The record is complete, so we can just use the length
    tocRecordLength = recordInfo[recordName].tocRecordLength
    recordInfo[tocName].record[tocRecordLength:(tocRecordLength + 2)] = struct.pack('>H', len(recordInfo[recordName].record))

    # Update our total image size
    imageSize += len(recordInfo[recordName].record)

################################################
# Create the ECC data areas and update TOC offsets

# VHDR has it's ECC in a special location at the start of the file

recordName = "VTOC"
# Not supported at present, so allocate the space, zero it out
recordInfo[recordName].ecc = bytearray(("\0" * (int(len(recordInfo[recordName].record) / 4))).encode())
# Go back and update all our TOC info now that the ecc is created
tocName = recordInfo[recordName].tocName
# Image size hasn't been updated since the end of the last record, so it points to the start of our new record
tocEccOffset = recordInfo[recordName].tocEccOffset
recordInfo[tocName].record[tocEccOffset:(tocEccOffset + 2)] = struct.pack('>H', imageSize)
# The record is complete, so we can just use the length
tocEccLength = recordInfo[recordName].tocEccLength
recordInfo[tocName].record[tocEccLength:(tocEccLength + 2)] = struct.pack('>H', len(recordInfo[recordName].ecc))

# Update our total image size
imageSize += len(recordInfo[recordName].ecc)

# Create the ECC for the TVPD records
for record in manifest.iter("record"):
    recordName = record.attrib.get("name")
    # Not supported at present, so allocate the space, zero it out
    recordInfo[recordName].ecc = bytearray(("\0" * (int(len(recordInfo[recordName].record) / 4))).encode())
    # Go back and update all our TOC info now that the ecc is created
    tocName = recordInfo[recordName].tocName
    # Image size hasn't been updated since the end of the last record, so it points to the start of our new record
    tocEccOffset = recordInfo[recordName].tocEccOffset
    recordInfo[tocName].record[tocEccOffset:(tocEccOffset + 2)] = struct.pack('>H', imageSize)
    # The record is complete, so we can just use the length
    tocEccLength = recordInfo[recordName].tocEccLength
    recordInfo[tocName].record[tocEccLength:(tocEccLength + 2)] = struct.pack('>H', len(recordInfo[recordName].ecc))

    # Update our total image size
    imageSize += len(recordInfo[recordName].ecc)

################################################
# Write the VPD 
# Everything for the image is now in memory!
# I'm intentionally write the file by doing VHDR, VTOC and then looping over the tvpd records
# The file needs to be written in the order the user gave, looping over the dictionary keys would guarantee that

# Write the top records
writeDataToVPD(vpdFile, recordInfo["VHDR"].record)
writeDataToVPD(vpdFile, recordInfo["VTOC"].record)

# Write all the tvpd records
for record in manifest.iter("record"):
    recordName = record.attrib.get("name")
    writeDataToVPD(vpdFile, recordInfo[recordName].record)

# Write the VTOC ECC
writeDataToVPD(vpdFile, recordInfo["VTOC"].ecc)

# Write all the tvpd record ecc
for record in manifest.iter("record"):
    recordName = record.attrib.get("name")
    writeDataToVPD(vpdFile, recordInfo[recordName].ecc)

# Done with the file
vpdFile.close()
print("  Wrote vpd file: %s" % vpdFileName)
