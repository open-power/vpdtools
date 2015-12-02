#!/usr/bin/env python
# Created by David Nickel August 19, 2015

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

#########################################
# Imports - Imports - Imports - Imports #
#########################################
import os
import xlrd
import binascii
import argparse
import subprocess

#########################################
# Classes - Classes - Classes - Classes #
#########################################

# This class is for easy storage of all the information gathered from TOOLGUIDE
class sheetInfo:
    def __init__(self,sheetName,hexColumn,rowStart,rowEnd):
        self.sheetName = sheetName
        self.hexColumn = hexColumn
        self.rowStart = rowStart
        self.rowEnd = rowEnd

#####################################
# Functions - Functions - Functions #
#####################################

###########################################
# Main - Main - Main - Main - Main - Main #
###########################################

clErrors = 0

parser = argparse.ArgumentParser(add_help = False)
reqgroup = parser.add_argument_group('Required Arguments')
reqgroup.add_argument("-d", "--document", help="The input .ods or .xls file", required=True)
reqgroup.add_argument("-o", "--outpath", help="The output path- the directory where the output files will be recorded", required=True)
optgroup = parser.add_argument_group('Optional Arguments')
optgroup.add_argument("-h", "--help", help="Show this help message and exit", action="help")
args = parser.parse_args()

# If the input document is not a .xls file, use unoconv to make it a .xls file, and keep track of whether that happened with addedXls, so we can delete the temp file later.
addedXls = False
clDocument = args.document
if ".xls" not in clDocument:
    documentBase = clDocument.rsplit(".",1)[0]
    # If an xls formatted file with the same name as the input document exists, we don't want to delete or change it, so an error will be thrown.
    if os.path.exists(documentBase + ".xls"):
        print "%s already exists, so %s cannot be converted to .xls format" % (documentBase+".xls", clDocument)
        clErrors += 1
    else:
        rc = subprocess.call(["unoconv","-f","xls",clDocument])
        if (rc):
            print "An error occured while converting %s to .xls format" % clDocument
            exit(rc)
        clDocument = documentBase + ".xls"
        addedXls = True    

clOutputPath = args.outpath
# If the path doesn't already exist, we are not making it.
if (os.path.exists(clOutputPath) != True):
    print "The given output path %s does not exist!" % clOutputPath
    print "Please create the output directory and run again"
    clErrors += 1

# If there are command line errors, exit and inform the user.
if (clErrors):
    print "ERROR: Missing/incorrect command line args! Please review the output above to determine which ones."
    # Don't forget to remove the temp file if it was created
    if (addedXls):
        os.remove(clDocument)
    exit(clErrors)

# Now the process starts.  We open up the inputted document, and open up the page titled "TOOLGUIDE", where the information regarding the other sheets names (column A), the column letter the binary info we want is in (column B), the row the info starts (column C), and the row the info ends (column D)
# Note that if the column letter in column B is two letters, e.g. AA, the code won't work properly.  Please make the column the hex values are in only one letter.

workbook = xlrd.open_workbook(clDocument)

toolguide = workbook.sheet_by_name("TOOLGUIDE")
sheetInfos = []

for row in range(0, toolguide.nrows):    # Iterate through the rows
    # The column arrays take numbers, not letters, so the letter needs to be turned into its corresponding number.  Does not work for two or more letters at once.
    sheetInfos += [sheetInfo(toolguide.cell(row,0).value,ord(toolguide.cell(row,1).value.lower()) - 97,int(toolguide.cell(row,2).value),int(toolguide.cell(row,3).value))]

# Now that we have all the information on where to locate the hex values we want, we start grabbing them

# Create an array to catch the output, so we can put it all into a file at once.
output = []
for sheet in sheetInfos:
    currentSheet = workbook.sheet_by_name(sheet.sheetName)
    # Iterate through the given hex column from the starting row to the ending row
    for x in range(sheet.rowStart-1, sheet.rowEnd):
        # The parser has a tendency to get all numbers as floating point, so if it happens to be a float, change it to a integer first, to get rid of the .0, then to a string.
        if isinstance(currentSheet.col(sheet.hexColumn)[x].value,float):
            output += [str(int(currentSheet.col(sheet.hexColumn)[x].value)).rjust(2,"0")]
        # If the value is not a float, we can just turn it straight into a string.
        else:
            output += [str(currentSheet.col(sheet.hexColumn)[x].value).rjust(2,"0")]
    print "Creating files for %s" % sheet.sheetName
    fileName = clOutputPath + "/" + sheet.sheetName + ".bin"
    f = open(fileName, 'w')
    # Convert the hex string to a binary output, then write it to file.
    for line in output:
        binaryLine = binascii.a2b_hex(line)
        f.write(binaryLine)
    f.close()
    # Create a .xml snippet that matches the bin file.  For use with the createVpd tool
    fileName = clOutputPath + "/" + sheet.sheetName + ".xml"
    f = open(fileName, 'w')
    f.write("<keyword name=\"%s\">\n" % sheet.sheetName)
    f.write("\t<kwdesc>The %s keyword</kwdesc>\n" % sheet.sheetName)
    f.write("\t<kwformat>bin</kwformat>\n")
    f.write("\t<kwlen>%d</kwlen>\n" % (sheet.rowEnd - sheet.rowStart + 1))
    f.write("\t<kwdata>%s.bin</kwdata>\n" % sheet.sheetName)
    f.write("</keyword>")
    f.close()
    # Clear the output array for the next loop
    output = []

# Also create a .xml snippet that is just all of the snippets combined
print "Combining all .xml files into allSheets.xml"
fileName = clOutputPath + "/" + "allSheets" + ".xml"
f = open(fileName, 'w')
for sheet in sheetInfos:
    fileName2 = clOutputPath + "/" + sheet.sheetName + ".xml"
    f2 = open(fileName2, 'r')
    for line in f2:
        f.write(line)
    f.write("\n")
    f2.close()
f.close()


# Remeber to delete the temp file, if it exists
if (addedXls):
    os.remove(clDocument)
