osm_spreadsheet
===============

**osm_spreadsheet** exports [OpenStreetMap][] data to spreadsheet (.tsv) format
allowing to edit it in spreadsheet software (Excel, [Openoffice][]) or table
data processing software ([Kettle][], [Google Refine][]).

Modifications from edited spreadsheet then can be imported back to OpenStreetMap
using difference files (only [JOSM difference format][] is supported at this
moment).

What data will be in spreadsheet?
---------------------------------

Currently osm_spreadsheet supports only *tags* of OSM objects (points, ways and
relations). So you can only update tags with this program. It is useful for:

* Adding attributes (i.e. population of places) from table data
* Adding internationalized names of objects in multiple languages
* Normalization of typos and different variants of name
* Just looking at multiple objects, how consistent they are tagged
* Exporting of OpenStreetMap data to use in other projects

It creates two special columns: `osm_id` and `osm_type` to link spreadsheet rows
to OSM entities. Other columns are tag keys, and cells store tag values. You can
specify which tag keys to export, for example you can leave only `highway` and
`name`. By default it will create columns for all tag keys found in input file.

[OpenStreetMap]: http://www.openstreetmap.org/
[Openoffice]:    http://www.openoffice.org/
[Kettle]:        http://kettle.pentaho.com/
[Google Refine]: http://code.google.com/p/google-refine/
[JOSM difference format]: http://wiki.openstreetmap.org/wiki/JOSM_file_format

Installation
------------

Currently there is no `setup.py`, so to install, just copy `osm_spreadsheet.py`
somewhere.

It requires *python 3*.

[argparse]: http://code.google.com/p/argparse/

Usage
-----

There are two commands: import and export.

    ./osm_spreadsheet.py export

Exports .osm xml file to .tsv spreadsheet and

    ./osm_spreadsheet.py import

Imports spreadsheet modifications using original .osm file used in export step,
creates difference file in [JOSM format][], that can be uploaded to OSM with
[JOSM][].

See --help for more info.

[JOSM format]: http://wiki.openstreetmap.org/wiki/JOSM_file_format
[JOSM]: http://josm.openstreetmap.de/
