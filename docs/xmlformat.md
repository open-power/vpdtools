## Introduction

This file will describe the xml of the vpd template file format used to
describe the contents of a VPD image

## High Level Description

The template VPD format is XML, used to describe the contents of a binary VPD image.  The template file is fed into createVpd.py.  It in turn interprets that XML, error checks it and creates a binary VPD image.

The template consists of 3 levels
* `<vpd>` - information about the overall VPD image
* `<record>` - information about a record in `<vpd>`
* `<keyword>` - information about a keyword contained in a `<record>`

The XML Hierarchy looks like the following:
``` xml
<vpd>
  <record>
    <keyword>
    </keyword>
    <keyword>
    </keyword>
  </record>
  <record>
    <keyword>
    ..
  </record>
  <record>
  ..
</vpd>
```