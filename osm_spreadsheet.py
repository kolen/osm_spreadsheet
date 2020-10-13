#!/usr/bin/env python3
# Convert .osm file to TSV file containing ids of each node/way/relation, type and all attributes

import sys
from xml.sax import make_parser
from xml.sax.handler import ContentHandler
from xml.sax.saxutils import quoteattr
import sqlite3
import pickle as pickle
from sys import stdout
import argparse

SPECIAL_COLUMN_OSM_ID   = 'osm_id'
SPECIAL_COLUMN_OSM_TYPE = 'osm_type'

class OSMObject:
    def __init__(self, type=None, id=None, attributes={}, timestamp=None,
        user=None, uid=None, version=None, changeset=None, visible=None,
        action=None):
        self.type = type
        self.id = id
        self.attributes = attributes
        self.timestamp = timestamp
        self.user = user
        self.uid = uid
        self.version = version
        self.changeset = changeset
        self.visible = visible
        self.action = action
        self.lat = None
        self.lon = None
        self.nodes=[]
        self.members=[]

    def __str__(self):
        return "<osm object %s %d %s>" % (self.type, self.id, self.attributes)

class Outputter:
    pass

class OSMAttributesStorage:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.text_factory = str # we use only blobs and byte strings for osm_type
        c = self.conn.cursor()
        c.execute("""
            create table attributes (
                osm_type text,
                osm_id integer,
                attributes blob,
                UNIQUE(osm_type, osm_id)
            )
            """)

    def add(self, osm_type, osm_id, attributes):
        c = self.conn.cursor()
        c.execute("insert into attributes (osm_type, osm_id, attributes) values (?, ?, ?)",
            (osm_type, osm_id, pickle.dumps(attributes)))

    def get(self, osm_type, osm_id):
        c = self.conn.cursor()
        c.execute("select attributes from attributes where osm_type=? and osm_id=?", (osm_type, osm_id))
        row = c.fetchone()
        if row:
            return pickle.loads(row[0])

class ColumnDetector(Outputter):
    def __init__(self):
        self.columns = set()

    def add(self, object):
        self.columns |= set(object.attributes.keys())

class TSVOutputter(Outputter):
    def __init__(self, columns, file):
        file.write("\t".join(
            [SPECIAL_COLUMN_OSM_TYPE, SPECIAL_COLUMN_OSM_ID]
            +[c for c in columns]) + "\n")
        self.columns = columns
        self.file = file
        self.types_allowed = set(('node', 'way', 'relation'))
        self.skip_empty = False

    def set_types_allowed(self, types):
        self.types_allowed = set(types)

    def set_skip_empty(self, skip_empty=True):
        self.skip_empty = skip_empty

    def add(self, obj):
        if obj.type not in self.types_allowed:
            return

        columns = [ obj.attributes.get(col, '') for col in self.columns ]

        if self.skip_empty and not any(columns):
            return

        self.file.write(("\t".join([obj.type, str(obj.id)] + columns) + "\n"))

class OSMAttributesStorageOutputter(Outputter):
    def __init__(self, storage):
        self.storage = storage

    def add(self, obj):
        self.storage.add(obj.type, obj.id, obj.attributes)

class Handler(ContentHandler):
    object_nodes = set(['node', 'way', 'relation'])

    def __init__(self, outputter):
        self.outputter = outputter
        self.obj = None

    def startElement(self, name, attrs):
        if name in self.object_nodes:
            self.obj = OSMObject(name, int(attrs['id']), {}, attrs.get('timestamp'),
                attrs.get('user'), attrs.get('uid'), attrs.get('version'),
                attrs.get('changeset'), attrs.get('visible'), attrs.get('action'))
            if name == "node":
                self.obj.lat = attrs['lat']
                self.obj.lon = attrs['lon']
        elif name == "tag":
            self.obj.attributes[attrs['k']] = attrs['v']
        elif name == "nd":
            self.obj.nodes.append(attrs['ref'])
        elif name == "member":
            self.obj.members.append((attrs['type'], attrs['ref'], attrs['role']))

    def endElement(self, name):
        if name in self.object_nodes:
            self.outputter.add(self.obj)

class DiffOutputter(Outputter):
    """
    Outputter that outputs change file in josm format
    (http://wiki.openstreetmap.org/wiki/JOSM_file_format)
    based on attribute storage
    """
    def __init__(self, storage, outfile=stdout):
        self.storage = storage
        self.outfile = outfile
        self.outfile.write("<?xml version='1.0' encoding='UTF-8'?>\n"
            "<osm version='0.6' upload='true' generator='osm2table.py'>\n")
        self.column_ignore_prefix = None

    def setColumnIgnorePrefix(self, prefix):
        self.column_ignore_prefix = prefix

    def _output_xml_element(self, name, attrs, closed=True, indent=0):
        self.outfile.write(("%s<%s %s%s>\n" %
            (" " * indent,
             name,
             " ".join("%s=%s" % (str(key), quoteattr(str(value)))
                    for key, value in attrs.items() if value is not None),
             ' /' if closed else ''
            )))

    def _apply_changes(self, attributes, spreadsheet_record):
        new = dict(attributes)
        if self.column_ignore_prefix:
            spreadsheet_record = dict((k,v) for k,v in spreadsheet_record.items()
                if not k.startswith(self.column_ignore_prefix))
        new.update(spreadsheet_record)
        return dict((k,v) for k,v in new.items() if v.strip() != '')

    def add(self, obj):
        attrs_to_output = obj.attributes
        changed = False
        spreadsheet_record = self.storage.get(obj.type, obj.id)
        if spreadsheet_record:
            changed_attrs = self._apply_changes(obj.attributes, spreadsheet_record)
            if changed_attrs != obj.attributes:
                attrs_to_output = changed_attrs
                changed = True

        simple_tag = (not attrs_to_output) and (not obj.nodes) and (not obj.members)
        self._output_xml_element(obj.type, {
                'id': obj.id,
                'timestamp': obj.timestamp,
                'uid': obj.uid,
                'user': obj.user,
                'visible': obj.visible,
                'version': obj.version,
                'changeset': obj.changeset,
                'lat': obj.lat,
                'lon': obj.lon,
                'action': 'modify' if changed else obj.action
            }, simple_tag, 1)

        for node in obj.nodes:
            self._output_xml_element('nd', {'ref': node}, True, 2)
        for m_type, m_id, m_role in obj.members:
            self._output_xml_element('member', {
                'type': m_type,
                'ref': m_id,
                'role': m_role
            })
        for key, value in attrs_to_output.items():
            self._output_xml_element('tag', {'k': key, 'v': value}, True, 2)

        if not simple_tag:
            self.outfile.write(" </%s>\n" % obj.type)

    def finish(self):
        self.outfile.write("</osm>")

def load_xml_into_storage(filename, storage):
    """
    Load attributes of all OSM objects in .osm xml file with filename filename
    into attribute storage storage.
    """
    p = make_parser()
    outputter = OSMAttributesStorageOutputter(storage)
    h = Handler(outputter)
    p.setContentHandler(h)
    p.parse(filename)

def load_tsv_into_storage(file, storage):
    """
    Load TSV file into attribute storage storage.
    """
    columns = file.readline().rstrip('\n').split("\t")
    for line in file:
        cells = line.rstrip('\n').split("\t")
        record = dict(list(zip(columns, cells)))
        osm_type = record.pop(SPECIAL_COLUMN_OSM_TYPE)
        osm_id = int(record.pop(SPECIAL_COLUMN_OSM_ID))

        storage.add(osm_type, osm_id, record)

def main_export(args):
    if args.columns is None:
        coldet = ColumnDetector()
        p = make_parser()
        h = Handler(coldet)
        p.setContentHandler(h)
        p.parse(args.osm_file.name)
        columns = coldet.columns
        args.osm_file.seek(0)
    else:
        columns = args.columns

    outputter = TSVOutputter(list(columns), args.output)

    if args.types:
        outputter.set_types_allowed(args.types)

    if args.skip_empty:
        outputter.set_skip_empty()

    p = make_parser()
    h = Handler(outputter)
    p.setContentHandler(h)
    p.parse(args.osm_file)

def main_import(args):
    s = OSMAttributesStorage()
    load_tsv_into_storage(args.tsv_file, s)

    outputter=DiffOutputter(s, args.output)

    if args.ignore_prefix:
        outputter.setColumnIgnorePrefix(args.ignore_prefix)

    p = make_parser()
    h = Handler(outputter)
    p.setContentHandler(h)
    p.parse(args.osm_file)
    outputter.finish()

def main():
    parser = argparse.ArgumentParser(description='Tool to modify tags of'
        'openstreetmap objects using spreadsheet files')
    subparsers = parser.add_subparsers(help='sub-command help', dest='action')

    parser_export = subparsers.add_parser('export',
        help='export osm xml file to .tsv spreadsheet',
        description="Export tags of objects in openstreetmap osm xml file to "
        ".tsv spreadsheet")
    parser_export.add_argument("osm_file", help="osm xml input file",
        type=argparse.FileType('r'))
    parser_export.add_argument("--output", "-o", metavar='TSV_FILE',
        help="output .tsv file (stdout by default)",
        type=argparse.FileType('w'), default=stdout)
    parser_export.add_argument("--columns", "-c", nargs='*', metavar='COLUMN',
        help="Tag keys to output as columns (by default all tag keys found in "
            "osm file will be outputted)\n"
            "Note that if this option is not specified and all columns is "
            "outputted, input file should be seekable (i.e. not stdin)")
    parser_export.add_argument("--skip-empty", "-e", action="store_true",
        help="Do not output records that have all columns except osm id and "
        "osm type empty")
    parser_export.add_argument("--types", "-t", action='append',
        choices=['node', 'way', 'relation'],
        help="Output only specified types of openstreetmap objects. Specify "
        "this parameter multiple times to include multiple types of objects, "
        "i.e. -t way -t relation")

    parser_import = subparsers.add_parser('import',
        help='import .tsv spreadsheet data to osm xml file',
        description="Create changefile in josm format "
        "(http://wiki.openstreetmap.org/wiki/JOSM_file_format) "
        "from original osm dataset and tags imported from .tsv spreadsheet file"
        )
    parser_import.add_argument("osm_file", type=argparse.FileType('r'),
        help="osm xml input file (original to apply changes)")
    parser_import.add_argument("tsv_file", type=argparse.FileType('r'),
        help=".tsv file with tag changes to apply")
    parser_import.add_argument("--output", "-o", metavar='OSM_FILE',
        help="output osm xml file - josm file format (stdout by default) - see "
        "http://wiki.openstreetmap.org/wiki/JOSM_file_format",
        type=argparse.FileType('w'), default=stdout)
    parser_import.add_argument("--ignore-prefix", "-p", metavar='COL_PREFIX',
        help="ignore columns with prefix COL_PREFIX")

    args = parser.parse_args()

    if args.action == 'import':
        return main_import(args)
    elif args.action == 'export':
        return main_export(args)

if __name__ == "__main__":
    main()
