#!/usr/bin/env python
# Created 01/26/15 by Jason Albert
# Program to create VPD images from input template files

# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# OpenPOWER HostBoot Project
#
# Contributors Listed Below - COPYRIGHT 2010,2014
# [+] International Business Machines Corp.
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG

############################################################
# Imports - Imports - Imports - Imports - Imports - Imports
############################################################
import os
# Get the path the script resides in
scriptPath = os.path.dirname(os.path.realpath(__file__))
import sys
sys.path.insert(0,scriptPath + "/pymod");
import out
import xml.etree.ElementTree as ET
import struct
import re
import argparse
import textwrap
import os

############################################################
# Classes - Classes - Classes - Classes - Classes - Classes
############################################################
# This parser extension is necessary to save comments and write them back out in the final file
# By default, element tree doesn't preserve comments
# http://stackoverflow.com/questions/4474754/how-to-keep-comments-while-parsing-xml-using-python-elementtree
class PCParser(ET.XMLTreeBuilder):
   def __init__(self):
       ET.XMLTreeBuilder.__init__(self)
       # assumes ElementTree 1.2.X
       self._parser.CommentHandler = self.handle_comment

   def handle_comment(self, data):
       self._target.start(ET.Comment, {})
       self._target.data(data)
       self._target.end(ET.Comment)
       
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
# Find file in a given path or paths
# searchPath comes from the --inpath option
def findFile(filename, searchPath):
   found = False
   paths = searchPath.split(os.path.pathsep)
   for path in paths:
       #print("Trying %s" % (os.path.join(path,filename)))
       if os.path.exists(os.path.join(path, filename)):
           found = 1
           break
   if found:
       return os.path.abspath(os.path.join(path, filename))
   else:
       return None

# Function to write out the resultant tvpd xml file
def writeTvpd(manifest, outputFile):
    tree = ET.ElementTree(manifest)
    tree.write(outputFile, encoding="utf-8", xml_declaration=True)
    return None

# Parses a tvpd file using ET.  That will generate errors for bad xml formatting
# The valid XML is then checked to make sure the required tags are found at each level
def parseTvpd(tvpdFile, topLevel):
    # Accumulate errors and return the total at the end
    # This allows the user to see all mistakes at once instead of iteratively running
    errorsFound = 0

    # Let the user know what file we are reading
    # We could make this optional with a new function param in the future
    out.msg("Parsing tvpd %s" % tvpdFile)

    # Read in the file
    # If there are tag mismatch errors or other general gross format problems, it will get caught here
    # Once we return from this function, then we'll check to make sure only supported tags were given, etc..
    # Invoke the extended PCParser, which will handle preserving comments in the output file
    parser = PCParser()
    tvpdRoot = ET.parse(tvpdFile, parser=parser).getroot()

    # Print the top level tags from the parsing
    if (clDebug):
        out.debug("Top level tag/attrib found")
        for child in tvpdRoot:
            out.debug("%s %s" % (child.tag, child.attrib))

    # Do some basic error checking of what we've read in
    # Make sure the root starts with the vpd tag
    # If it doesn't, it's not worth syntax checking any further
    # This is the only time we'll just bail instead of accumulating
    if (tvpdRoot.tag != "vpd"):
        out.error("%s does not start with a <vpd> tag.  No further checking will be done until fixed!" % tvpdFile)
        return(1, None)

    # We at least have a proper top level vpd tag, so loop thru the rest of the levels and check for any unknown tags
    # This will also be a good place to check for the required tags

    # Define the expected tags at this level
    vpdTags = {"name" : 0, "size" : 0, "VD" : 0, "record" : 0}

    # Go thru the tags at this level
    for vpd in tvpdRoot:
        # Comments aren't basestring tags
        if not isinstance(vpd.tag, basestring):
            continue
            
        # See if this is a tag we even expect
        if vpd.tag not in vpdTags:
            out.error("Unsupported tag <%s> found while parsing the <vpd> level" % vpd.tag)
            errorsFound+=1
            # We continue here because we don't want to parse down this hierarcy path when we don't know what it is
            continue
        # It was a supported tag
        else:
            vpdTags[vpd.tag]+=1

        # Do the record level checks
        if (vpd.tag == "record"):
            # Define the expected tags at this level
            recordTags = {"rdesc" : 0, "keyword" : 0, "rtvpdfile" : 0, "rbinfile" : 0}

            # Make sure the record has a name attrib, save for later use
            recordName = vpd.attrib.get("name")
            if (recordName == None):
                out.error("A <record> tag is missing the name attribute")
                errorsFound+=1
                recordName = "INVALID" # Set the invalid name so the code below can use it without issue

            # Loop thru the tags defined for this record
            for record in vpd:
                # Comments aren't basestring tags
                if not isinstance(record.tag, basestring):
                    continue

                # See if this is a tag we even expect
                if record.tag not in recordTags:
                    out.error("Unsupported tag <%s> found while parsing the <record> level for record %s" % (record.tag, recordName))
                    errorsFound+=1
                    # We continue here because we don't want to parse down this hierarcy path when we don't know what it is
                    continue
                
                # It was a supported tag
                else:
                    recordTags[record.tag]+=1

                # Do the keyword level checks
                if (record.tag == "keyword"):
                    # Define the expected tags at this level
                    keywordTags = {"kwdesc" : 0, "kwformat" : 0, "kwlen" : 0, "kwdata" : 0}

                    # Make sure the keyword has a name attrib, save for later use
                    keywordName = record.attrib.get("name")
                    if (keywordName == None):
                        out.error("<keyword> tag in record %s is missing the name attribute" % (recordName))
                        errorsFound+=1
                        keywordName = "INVALID" # Set the invalid name so the code below can use it without issue

                    # Loop thru the tags defined for this keyword
                    for keyword in record:
                        # Comments aren't basestring tags
                        if not isinstance(keyword.tag, basestring):
                            continue

                        # See if this is a tag we even expect
                        if keyword.tag not in keywordTags:
                            out.error("Unsupported tag <%s> found while parsing the <keyword> level for keyword %s in record %s" % (keyword.tag, keywordName, recordName))
                            errorsFound+=1
                            # We continue here because we don't want to parse down this hierarcy path when we don't know what it is
                            continue
                        # It was a supported tag
                        else:
                            keywordTags[keyword.tag] += 1

                    # We've checked for unknown keyword tags, now make sure we have the right number of each
                    # This is a simple one, we can only have 1 of each
                    for tag in keywordTags:
                        if (keywordTags[tag] != 1):
                            out.error("The tag <%s> was expected to have a count of 1, but was found with a count of %d for keyword %s in record %s" % (tag, keywordTags[tag], keywordName, recordName))
                            errorsFound+=1

            # We've checked for unknown record tags, now make sure we've got the right number, they don't conflict, etc..
            recordTagTotal = bool(recordTags["keyword"]) + bool(recordTags["rbinfile"]) + bool(recordTags["rtvpdfile"])
            # keyword, rbinfile and rtvpdfile are mutually exclusive.  Make sure we have only one
            if (recordTagTotal > 1):
                out.error("For record %s, more than one tag of type keyword, rbinfile or rtvpdfile was given!" % (recordName))
                out.error("Use of only 1 at a time is supported for a given record!")
                errorsFound+=1
            # We checked if we had more than 1, let's make sure we have at least 1
            if (recordTagTotal < 1):
                out.error("For record %s, 0 tags of type keyword, rbinfile or rtvpdfile were given!" % (recordName))
                out.error("1 tag of the 3 must be in use for the record to be valid!")
                errorsFound+=1
            # Make sure the rdesc is available
            if (recordTags["keyword"] and recordTags["rdesc"] != 1):
                out.error("The tag <rdesc> was expected to have a count of 1, but was found with a count of %d for record %s" % (recordTags["rdesc"], recordName))
                errorsFound+=1

    # Do some checking of what we found at the vpd level
    # Top level is the manifest passed in on the command line
    # When false, it's just a record description and doesn't require the high level descriptors
    if (topLevel == True):
        comparer = 1
    else:
        comparer = 0
    # Don't go thru all of them, "record" has special handling below
    for tag in ["name", "size", "VD"]:
        if (vpdTags[tag] != comparer):
            out.error("The tag <%s> was expected to have a count of %d, but was found with a count of %d" % (tag, comparer, vpdTags[tag]))
            errorsFound+=1

    # Make sure at least one record tag was found
    if (vpdTags["record"] == 0):
        out.error("At least one <record> must be defined for the file to be valid!")
        errorsFound+=1

    # If this is an included tvpd, it can only have 1 record in it
    # This check is just by convention.  If a compelling case to change it was provided, it could be done
    if (topLevel == False):
        if (vpdTags["record"] > 1):
            out.error("More than 1 record entry found in %s.  Only 1 record is allowed!" % (tvpdFile))
            errorsFound+=1

    ######
    # All done, vary our return based upon the errorsFound
    if (errorsFound):
        return (errorsFound, None)
    else:
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
    if (keyword[0] == "#"): # Keywords that start with pound have a 2 byte length
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
        # Remove white space and carriage returns from the data before we get to fromhex
        # If we don't, it throws off the ljust logic below to set the field to proper length
        data = data.replace(" ","")
        data = data.replace("\n","")
        # Pad if necessary (* 2 to convert nibble data to byte length)
        data = data.ljust((length * 2), '0')
        # Write it
        keywordPack += bytearray.fromhex(data)
    elif (format == "bin"):
        # Pad if necessary
        data = bytearray(data)
        for i in range (len(data), length):
            data.append(0)
        # Stick the binary data we have right back into the record
        keywordPack += data
    else:
        out.error("Unknown format type %s passed into packKeyword" % format)
        return None

    # The keyword is packed, send it back
    return keywordPack

# Calculate the length of the PF record
def calcPadFill(record):
    pfLength = 0

    # The PF keyword must exist
    # The keyword section of record must be at least 40 bytes long, padfill will be used to achieve that
    # If the keyword section is over over 40, it must be aligned on word boundaries and PF accomplishes that

    # The record passed in at this point is the keywords + 3 other bytes (LR Tag & Record Length)
    # Those 3 bytes happen to match the length of the PF keyword and its length which needs to be in the calculation
    # So we'll just use the length of the record, but it's due to those offsetting lengths of 3
    pfLength = 40 - len(record)
    if (pfLength < 1):
        # It's > 40, so now we just need to fill to nearest word
        pfLength = (4 - (len(record) % 4))

    return pfLength

# Check input hex data for proper formatting
def checkHexDataFormat(kwdata):
    # Remove white space and carriage returns from the kwdata
    kwdata = kwdata.replace(" ","")
    kwdata = kwdata.replace("\n","")
    # Now look to see if there are any characters other than 0-9 & a-f
    match = re.search("([^0-9a-fA-F]+)", kwdata)
    if (match):
        out.error("A non hex character \"%s\" was found at %s in the kwdata" % (match.group(), match.span()))
    return (match, kwdata)


############################################################
# Main - Main - Main - Main - Main - Main - Main - Main
############################################################
rc = 0

################################################
# Command line options
# Create the argparser object
# We disable auto help options here and add them manually below.  This is so we can get all the optional args in 1 group
parser = argparse.ArgumentParser(description='The VPD image creation tool', add_help=False, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=textwrap.dedent('''\
                                 Examples:
                                   ./createVpd.py -m examples/simple/simple.tvpd -o /tmp
                                   ./createVpd.py -m examples/rbinfile/rbinfile.tvpd -i examples/rbinfile -o /tmp
                                 '''))
# Create our group of required command line args
reqgroup = parser.add_argument_group('Required Arguments')
reqgroup.add_argument('-m', '--manifest', help='The input file detailing all the records and keywords to be in the image', required=True)
reqgroup.add_argument('-o', '--outpath', help='The output path for the files created by the tool', required=True)
# Create our group of optional command line args
optgroup = parser.add_argument_group('Optional Arguments')
optgroup.add_argument('-h', '--help', action="help", help="Show this help message and exit")
optgroup.add_argument('-d', '--debug', help="Enables debug printing",action="store_true")
optgroup.add_argument('-r', '--binary-records', help="Create binary files for each record in the template",action="store_true")
optgroup.add_argument('-k', '--binary-keywords', help="Create binary files for each keyword in the template",action="store_true")
optgroup.add_argument('-i', '--inpath', help="The search path to use for the files referenced in the manifest")

# We've got everything we want loaded up, now look for it
args = parser.parse_args()

# Get the manifest file and get this party started
clManifestFile = args.manifest

# Look for output path
clOutputPath = args.outpath
# Make sure the path exists, we aren't going to create it
if (os.path.exists(clOutputPath) != True):
    out.error("The given output path %s does not exist!" % clOutputPath)
    out.error("Please create the output directory and run again")
    exit(1)

# Look for input path
clInputPath = args.inpath
# Make sure the path exists
if (clInputPath != None):
    # Add the CWD onto the path so the local directory is always looked at
    clInputPath +=  os.pathsep + "."
else:
    # Set it the CWD since it will be used throughout the program and having it set to None breaks things
    clInputPath = "."

# Debug printing
clDebug = args.debug

# Create separate binary files for each record
clBinaryRecords = args.binary_records

# Create separate binary files for each keyword
clBinaryKeywords = args.binary_keywords

# We are going to do this in 3 stages
# 1 - Read in the manifest and any other referenced files.  This will create a complete XML description of the VPD
#     We will also check to make sure that all required tags are given and no extra tags exist
# 2 - Parse thru the tvpd description and make sure the data with in the tags is valid.  These are checks like data not greater than length, etc..
# 3 - With the XML and contents verified correct, loop thru it again and write out the VPD data
# Note: Looping thru the XML twice between stage 1 and 2 makes it easier to surface multiple errors to the user at once.
#       If we were trying to both validate the xml and data at once, it would be harder to continue and gather multiple errors like we do now

################################################
# Work with the manifest
out.setIndent(0)
out.msg("==== Stage 1: Parsing tvpd XML")
out.setIndent(2)
errorsFound = 0

# Get the full path to the file given
manifestfile = findFile(clManifestFile, clInputPath)
if (manifestfile == None):
    out.error("The manifest file %s could not be found!  Please check your -m or -i cmdline options for typos" % (clManifestFile))
    exit(1)

# Read in the manifest 
(rc, manifest) = parseTvpd(manifestfile, True)
if (rc):
    out.error("Problem reading in the manifest! - %s" % manifestfile)
    exit(rc)

# Stash away some variables for use later
vpdName = manifest.find("name").text
# If the user passed in the special name of FILENAME, we'll use in the input file name, minus the extension, as the output
if (vpdName == "FILENAME"):
    vpdName = os.path.splitext(os.path.basename(clManifestFile))[0]

# Determining the size given
vpdSize = manifest.find("size").text
# Make a new string with only the number
maxSizeBytes = re.match('[0-9]*', vpdSize).group()
# Check to see if the number is even there
if (maxSizeBytes == ''):
    maxSizeBytes = '0'
    out.error("No number detected in the size string.  Format of string must be number first, then units, e.g. 16KB. Remove any characters or white space from in front of the number.")
    errorsFound+=1
# Make a new string with the number removed
sizeUnits = vpdSize[len(maxSizeBytes):]
# Remove a space, if one was inserted between the number and units
whitespace = re.match(' *', sizeUnits).group()
sizeUnits = sizeUnits[len(whitespace):]
# Check the units to see if they are okay
if (sizeUnits == "kB" or sizeUnits == "kb" or sizeUnits == "Kb" or sizeUnits == "KB"):
    maxSizeBytes = int(maxSizeBytes) * 1024
elif (sizeUnits == "b" or sizeUnits == "B"):
    maxSizeBytes = int(maxSizeBytes)
elif (sizeUnits == "Mb" or sizeUnits == "MB"):
    maxSizeBytes = int(maxSizeBytes) * 1024 * 1024
elif (sizeUnits == ""):
    out.error("Please specify units at the end of the size string. Acceptable units: B; KB; MB.")
    errorsFound+=1
else:
    out.error("Unexpected units in the size string. Expected: B; KB; MB. Yours: %s" % sizeUnits)
    errorsFound+=1

# Look for rtvpdfile lines
for record in manifest.iter("record"):
    recordName = record.attrib.get("name")

    # See if a rtvpdfile was given and if so, load it in
    rtvpdfile = record.find("rtvpdfile")
    if (rtvpdfile != None):
        # Get the full path to the file given
        fileName = findFile(rtvpdfile.text, clInputPath)
        if (fileName == None):
            out.error("The rtvpdfile %s could not be found!  Please check your tvpd or input path" % (rtvpdfile.text))
            errorsFound+=1
            break

        # Read in the rtvpdfile since it exists
        (rc, recordTvpd) = parseTvpd(fileName, False)
        if (rc):
            out.error("Error occurred reading in %s" % fileName)
            errorsFound+=1
            break

        # Merge the new record into the main manifest
        # ET doesn't have a replace function.  You can do an extend/remove, but that changes the order of the file
        # The goal is to preserve record & keyword order, so that method doesn't work
        # The below code will insert the rtvpdfile record in the list above the current matching record definition
        # Then remove the original record definition, preserving order

        # Since the referenced file also starts with <vpd> tag, you need to get one level down and find the start of the record element, hence the find
        # We know this will contain a record because the parse validates that.  No need to check for find errors.
        subRecord = recordTvpd.find("record")

        # --------
        # Make sure the record found in rtvpdfile is the same as the record in the manifiest
        # We have to do this error check here because the recordName doesn't exist in parseTvpd
        subRecordName = subRecord.attrib.get("name")
        if (subRecordName != recordName):
            out.error("The record (%s) found in %s doesn't match the record name in the manifest (%s)" % (subRecordName, rtvpd.text, recordName))
            errorsFound+=1
            break

        # Everything looks good, insert/remove
        manifest.insert(list(manifest).index(record), subRecord)
        manifest.remove(record)

# All done with error checks, bailout if we hit something
if (errorsFound):
    out.msg("")
    out.error("%d error%s found in the tvpd xml.  Please review the above errors and correct them." % (errorsFound, "s" if (errorsFound > 1) else ""))
    exit(errorsFound)

################################################
# Verify the tvpd XML
# read thru the complete tvpd and verify/check actual tag contents
out.setIndent(0)
out.msg("==== Stage 2: Verifying tvpd syntax")
out.setIndent(2)
errorsFound = 0
# Keep a dictionary of the record names we come across, will let us find duplicates
recordNames = dict()

# Loop thru our records and then thru the keywords in each record
for record in manifest.iter("record"):
    # Pull the record name out for use throughout
    recordName = record.attrib.get("name")

    out.msg("Checking record %s" % recordName)
    out.setIndent(4)
    
    # --------
    # Make sure we aren't finding a record we haven't already seen
    if (recordName in recordNames):
        out.error("The record \"%s\" has previously been defined in the tvpd" % recordName)
        errorsFound+=1
    else:
        recordNames[recordName] = 1

    # --------
    # Make sure the record name is 4 charaters long
    if (len(recordName) != 4):
        out.error("The record name entry \"%s\" is not 4 characters long" % recordName)
        errorsFound+=1

    # --------
    # Do very basic checking on the rbinfile if found
    # It is assumed that this file was generated by this tool at an earlier date, so it should be format correct
    # We'll simply ensure it is actually a record that goes with this record name
    if (record.find("rbinfile") != None):
        # Get the name
        rbinfile = record.find("rbinfile").text

        # Get the full path to the file given
        rbinfile = findFile(rbinfile, clInputPath)
        if (rbinfile == None):
            out.error("The rbinfile %s could not be found!  Please check your tvpd or input path" % (rbinfile))
            errorsFound+=1
            break

        # It does, read it in so we can check the record name
        out.msg("Reading rbinfile %s" % (rbinfile))
        rbinfileContents = open(rbinfile, mode='rb').read()

        # --------
        # Check the record name
        # This is just the hard coded offset into any record where the contents of the RT keyword would be found
        if (recordName != rbinfileContents[6:10].decode()):
            out.error("The record name found %s in %s, does not match the name of the record %s in the tvpd" % (rbinfileContents[6:10].decode(), rbinfile, recordName))
            clErrors+=1

    # --------
    # For the keyword tags we'll do much more extensive checking
    if (record.find("keyword") != None):
        # Track the keywords we come across so we can find duplicate
        keywordNames = dict()
        # Loop through the keywords and verify them
        for keyword in record.iter("keyword"):
            # Pull the keyword name out for use throughout
            keywordName = keyword.attrib.get("name")

            # Setup a dictionary of the supported tags
            kwTags = {"keyword" : False, "kwdesc" : False, "kwformat" : False, "kwlen" : False, "kwdata" : False}
            # Setup a dictionary of the supported tags in the kwdata tag
            kwdTags = {"ascii" : False, "hex" : False}

            # --------
            # Make sure we aren't finding a record we haven't already seen
            if (keywordName in keywordNames):
                out.error("The keyword \"%s\" has previously been defined in record %s" % (keywordName, recordName))
                errorsFound+=1
            else:
                keywordNames[keywordName] = 1

            # --------
            # We'll loop through all the tags found in this keyword and check for all required and any extra ones
            for kw in keyword.iter():
                # Comments aren't basestring tags
                if not isinstance(kw.tag, basestring):
                    continue

                if kw.tag in kwTags:
                    # Mark that we found a required tag
                    kwTags[kw.tag] = True
                    # Save the values we'll need into variables for ease of use
                    if (kw.tag == "kwformat"):
                        kwformat = kw.text.lower() # lower() for ease of compare
                        
                    if (kw.tag == "kwlen"):
                        kwlen = int(kw.text)
                        
                    if (kw.tag == "kwdata"):
                        # If it's mixed format, we want kwdata to actually hold all the xml tags contained in this kwdata
                        # Otherwise, grab the plain text so we can treat it like data later
                        if (kwformat == "mixed"):
                            kwdata = kw
                        else:
                            kwdata = kw.text

                elif kw.tag in kwdTags:
                    # Ignore the kwdTags for now, we'll check them later
                    next
                    
                else:
                    # Flag that we found an unsupported tag.  This may help catch typos, etc..
                    out.error("The unsupported tag \"<%s>\" was found in keyword %s in record %s" % (kw.tag, keywordName, recordName))
                    errorsFound+=1
                
            # --------
            # Make sure all the required kwTags were found
            for kw in kwTags:
                if (kwTags[kw] == False):
                    out.error("Required tag \"<%s>\" was not found in keyword %s in record %s" % (kw, keywordName, recordName))
                    errorsFound+=1

            # Now we know the basics of the template are correct, now do more indepth checking of length, etc..

            # --------
            # Make sure the keyword is two characters long
            if (len(keywordName) != 2):
                out.error("The length of the keyword %s in record %s is not 2 characters long" % (keywordName, recordName))
                errorsFound+=1

            # --------
            # A check to make sure the RT keyword kwdata matches the name of the record we are in
            if ((keywordName == "RT") and (recordName != kwdata)):
                out.error("The value of the RT keyword \"%s\" does not match the record name \"%s\"" % (kwdata, recordName))
                errorsFound+=1

            # --------
            # Check that the length specified isn't longer than the keyword supports
            # Keywords that start with # are 2 bytes, others are 1 byte
            if (keywordName[0] == "#"):
                maxlen = 65535
            else:
                maxlen = 255
            if (kwlen > maxlen):
                out.error("The specified length %d is bigger than the max length %d for keyword %s in record %s" % (kwlen, maxlen, keywordName, recordName))
                errorsFound+=1

            # --------
            # If the input format is bin, make sure the file exists and then read in the data
            if (kwformat == "bin"):
                # Get the full path to the file given
                databinfile = findFile(kwdata, clInputPath)
                if (databinfile == None):
                    out.error("The databinfile %s could not be found!  Please check your tvpd or input path" % (kwdata))
                    errorsFound+=1
                    break

                # It does, read it in so we can check the record name
                # We'll replace the kwdata with the actual data instead of the file name for the rest of the checks
                kwdata = open(databinfile, mode='rb').read()

            # --------
            # If the input format is hex, make sure the input data is hex only
            if (kwformat == "hex"):
                (rc, kwdata) = checkHexDataFormat(kwdata)
                if (rc):
                    out.error("checkHexDataFormat return an error for for keyword %s in record %s" % (keywordName, recordName))
                    errorsFound+=1

            # --------
            # If the input format is mixed, loop over the kwdata and verify it is formatted properly
            if (kwformat == "mixed"):
               # We can't use the length check code below for the mixed case, so track it here and check below
               kwdatalen = 0
               # We need to verify the format and length of the ascii or hex keywords embedded in here
               for kwd in kwdata.iter():
                  # Comments aren't basestring tags
                  if not isinstance(kwd.tag, basestring):
                     continue

                  # Make sure it only contains the two keywords we expect
                  if kwd.tag.lower() in kwdTags:
                     if (kwd.tag.lower() == "ascii"):
                        kwdatalen += len(kwd.text)
                        
                     if (kwd.tag.lower() == "hex"):
                        (rc, kwdata) = checkHexDataFormat(kwd.text)
                        if (rc):
                           out.error("checkHexDataFormat return an error for for keyword %s in record %s" % (keywordName, recordName))
                           errorsFound+=1
                        # Nibbles to bytes
                        kwdatalen += (len(kwdata)/2)

                  elif (kwd.tag.lower() == "kwdata"):
                     next # Ignore this tag at this level
                        
                  else:
                     # Flag that we found an unsupported tag.  This may help catch typos, etc..
                     out.error("The unsupported tag \"<%s>\" was found in kwdata for keyword %s in record %s" % (kwd.tag, keywordName, recordName))
                     errorsFound+=1

               # Done looping through the tags we found, now check that the length isn't too long
               if (kwdatalen > kwlen):
                  out.error("The total length of the mixed data is longer than the given <kwlen> for keyword %s in record %s" % (keywordName, recordName))
                  errorsFound+=1

            # --------
            # Verify that the data isn't longer than the length given
            # Future checks could include making sure bin data is hex
            if (kwformat == "ascii" or kwformat == "bin"):
                if (len(kwdata) > kwlen):
                    out.error("The length of the value is longer than the given <kwlen> for keyword %s in record %s" % (keywordName, recordName))
                    errorsFound+=1
            elif (kwformat == "hex"):
                # Convert hex nibbles to bytes for len compare
                if ((len(kwdata)/2) > kwlen):
                    out.error("The length of the value is longer than the given <kwlen> for keyword %s in record %s" % (keywordName, recordName))
                    errorsFound+=1
            elif (kwformat == "mixed"):
                # The mixed tag length checking was handled above
                next
            else:
                out.error("Unknown keyword format \"%s\" given for keyword %s in record %s" % (kwformat, keywordName, recordName))
                errorsFound+=1

    # Done with the record, reset the output
    out.setIndent(2)

# All done with error checks, bailout if we hit something
if (errorsFound):
    out.msg("")
    out.error("%d error%s found in the tvpd data.  Please review the above errors and correct them." % (errorsFound, "s" if (errorsFound > 1) else ""))
    tvpdFileName = clOutputPath + "/" + vpdName + "-err.tvpd"
    writeTvpd(manifest, tvpdFileName)
    out.msg("Wrote tvpd file to help in debug: %s" % tvpdFileName)
    exit(errorsFound)

# We now have a correct tvpd, use it to create a binary VPD image
out.setIndent(0)
out.msg("==== Stage 3: Creating binary VPD image")
out.setIndent(2)
# Create our output file names 
tvpdFileName = clOutputPath + "/" + vpdName + ".tvpd"
vpdFileName = clOutputPath + "/" + vpdName + ".vpd"

# This is our easy one, write the XML back out
# Write out the full template vpd representing the data contained in our image
writeTvpd(manifest, tvpdFileName)
out.msg("Wrote tvpd file: %s" % tvpdFileName)

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
version = manifest.find("VD").text
recordInfo[recordName].record += packKeyword("VD", 2, version, "hex")

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
recordInfo[tocName].record[tocRecordOffset:(tocRecordOffset + 2)] = struct.pack('<H', imageSize)
# The record is complete, so we can just use the length
tocRecordLength = recordInfo[recordName].tocRecordLength
recordInfo[tocName].record[tocRecordLength:(tocRecordLength + 2)] = struct.pack('<H', len(recordInfo[recordName].record))

# Update our total image size
imageSize += len(recordInfo[recordName].record)

################################################
# Create the remaining records from the tvpd
for record in manifest.iter("record"):
    recordName = record.attrib.get("name")

    # Figure out if we need to create an image from keywords, or just stick a record binary in place
    # We already did all the checks to make sure only a rbinfile or keyword(s) tag was given
    # Don't error check those cases here again.  If rbinfile is found, just go and else the keyword case
    if (record.find("rbinfile") != None):
        # Get the name
        rbinfile = findFile(record.find("rbinfile").text, clInputPath)

        # Open the file and stick it into the record
        recordInfo[recordName].record = open(rbinfile, mode='rb').read()

    # Create the record image from the xml description
    else:

        # The large resource tag
        recordInfo[recordName].record += bytearray(bytearray.fromhex("84"))

        # The record length, we will come back and update this at the end
        recordInfo[recordName].record += bytearray(bytearray.fromhex("0000"))

        # The keywords
        for keyword in record.iter("keyword"):
            keywordName = keyword.attrib.get("name")
            kwlen = int(keyword.find("kwlen").text)
            kwdata = keyword.find("kwdata").text
            kwformat = keyword.find("kwformat").text
            # If the input format is bin, we need to pull the data in from the file
            # We know the file exists from the check in step 2
            if (kwformat == "bin"):
                # Get the full path to the file given, error checked before
                databinfile = findFile(kwdata, clInputPath)
                kwdata = open(databinfile, mode='rb').read()
            # If the input format is mixed, we need to concat the data together before packing
            # We'll force all the data to hex and tell it to pack as hex
            if (kwformat == "mixed"):
                kwdata = "" # Reset
                for kwd in keyword.find("kwdata"):
                    if (kwd.tag == "hex"):
                        kwdata += kwd.text
                    if (kwd.tag == "ascii"):
                        kwdata += kwd.text.encode("hex")
                kwformat = "hex"

            keywordPack = packKeyword(keywordName,  kwlen, kwdata, kwformat)
            recordInfo[recordName].record += keywordPack
            # If the user wanted discrete binary files for each keyword writen out, we'll do it here
            if (clBinaryKeywords):
                kvpdFileName = clOutputPath + "/" + vpdName + "-" + recordName + "-" + keywordName + ".kvpd"
                out.msg("Wrote record %s keyword %s kvpd file: %s" % (recordName, keywordName, kvpdFileName))
                kvpdFile = open(kvpdFileName, "wb")
                kvpdFile.write(keywordPack)
                kvpdFile.close()

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
    recordInfo[tocName].record[tocRecordOffset:(tocRecordOffset + 2)] = struct.pack('<H', imageSize)
    # The record is complete, so we can just use the length
    tocRecordLength = recordInfo[recordName].tocRecordLength
    recordInfo[tocName].record[tocRecordLength:(tocRecordLength + 2)] = struct.pack('<H', len(recordInfo[recordName].record))

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
recordInfo[tocName].record[tocEccOffset:(tocEccOffset + 2)] = struct.pack('<H', imageSize)
# The record is complete, so we can just use the length
tocEccLength = recordInfo[recordName].tocEccLength
recordInfo[tocName].record[tocEccLength:(tocEccLength + 2)] = struct.pack('<H', len(recordInfo[recordName].ecc))

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
    recordInfo[tocName].record[tocEccOffset:(tocEccOffset + 2)] = struct.pack('<H', imageSize)
    # The record is complete, so we can just use the length
    tocEccLength = recordInfo[recordName].tocEccLength
    recordInfo[tocName].record[tocEccLength:(tocEccLength + 2)] = struct.pack('<H', len(recordInfo[recordName].ecc))

    # Update our total image size
    imageSize += len(recordInfo[recordName].ecc)


################################################
# Write the VPD 
# Everything for the image is now in memory!
# I'm intentionally writing the file by doing VHDR, VTOC and then looping over the tvpd records
# The file needs to be written in the order the user gave, looping over the dictionary keys would not guarantee that

# Write the top records
writeDataToVPD(vpdFile, recordInfo["VHDR"].record)
writeDataToVPD(vpdFile, recordInfo["VTOC"].record)

# Write all the tvpd records
for record in manifest.iter("record"):
    recordName = record.attrib.get("name")
    writeDataToVPD(vpdFile, recordInfo[recordName].record)
    # If the user wanted discrete binary files for each record writen out, we'll do it here
    if (clBinaryRecords):
        rvpdFileName = clOutputPath + "/" + vpdName + "-" + recordName + ".rvpd"
        out.msg("Wrote %s record rvpd file: %s" % (recordName, rvpdFileName))
        rvpdFile = open(rvpdFileName, "wb")
        rvpdFile.write(recordInfo[recordName].record)
        rvpdFile.close()

# Write the VTOC ECC
writeDataToVPD(vpdFile, recordInfo["VTOC"].ecc)

# Write all the tvpd record ecc
for record in manifest.iter("record"):
    recordName = record.attrib.get("name")
    writeDataToVPD(vpdFile, recordInfo[recordName].ecc)

# Done with the file
vpdFile.close()
out.msg("Wrote vpd file: %s" % vpdFileName)

# Check if the image size is larger than the maxSizeBytes
if (imageSize > maxSizeBytes):
    out.error("The generated binary image (%s) is too large for the size given (%s)"%(imageSize, maxSizeBytes))
    errorsFound += 1
    
# Catch the errors
if (errorsFound):
    out.msg("")
    out.error("%d error%s found while creating the binary image.  Please review the above errors and correct them." % (errorsFound, "s" if (errorsFound > 1) else ""))
    
# Return the number of errors found as the return code
exit (errorsFound)
