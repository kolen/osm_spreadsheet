# Convert .osm file to TSV file containing ids of each node/way/relation, type and all attributes

import sys
from xml.sax import make_parser
from xml.sax.handler import ContentHandler
import sqlite3
import cPickle as pickle
from sys import stdout
from xml.sax.saxutils import quoteattr

SPECIAL_COLUMN_OSM_ID   = 'osm_id'
SPECIAL_COLUMN_OSM_TYPE = 'osm_type'

class OSMObject:
    def __init__(self, type=None, id=None, attributes={}, timestamp=None,
        user=None, uid=None, version=None, changeset=None, visible=None):
        self.type = type
        self.id = id
        self.attributes = attributes
        self.timestamp = timestamp
        self.user = user
        self.uid = uid
        self.version = version
        self.changeset = changeset
        self.visible = visible
        self.lat = None
        self.lon = None

    def __unicode__(self):
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
    def __init__(self, columns):
        print "\t".join([SPECIAL_COLUMN_OSM_TYPE, SPECIAL_COLUMN_OSM_ID]+[c.encode('utf-8') for c in columns])
        self.columns = columns

    def add(self, obj):
        print "\t".join([obj.type, str(obj.id)] + [
            obj.attributes.get(col, '').encode('utf-8')
            for col in self.columns])

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
            self.obj = OSMObject(name, long(attrs['id']), {}, attrs.get('timestamp'),
                attrs.get('user'), attrs.get('uid'), attrs.get('version'),
                attrs.get('changeset'), attrs.get('visible'))
            if name == "node":
                self.obj.lat = attrs['lat']
                self.obj.lon = attrs['lon']
        elif name == "tag":
            self.obj.attributes[attrs['k']] = attrs['v']
        elif name == "nd":
            pass
        elif name == "member":
            pass

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

    def _output_xml_element(self, name, attrs, closed=True, indent=0):
        self.outfile.write((u"%s<%s %s%s>\n" %
            (u" " * indent,
             name,
             u" ".join(u"%s=%s" % (unicode(key), quoteattr(unicode(value)))
                    for key, value in attrs.iteritems() if value is not None),
             u'/' if closed else u''
            )).encode('utf-8'))

    def add(self, obj):
        changed_attrs = self.storage.get(obj.type, obj.id)

        if changed_attrs and changed_attrs != obj.attributes:
            attrs_to_output = changed_attrs
            changed = True
        else:
            attrs_to_output = obj.attributes
            changed = False

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
            }, not obj.attributes, 1) #close if no attributes
        if obj.attributes:
            for key, value in obj.attributes.iteritems():
                self._output_xml_element('tag', {'k': key, 'v': value}, True, 2)
            self.outfile.write(" </%s>\n" % obj.type)

    def finish(self):
        self.outfile.write("</osm>")

def xml_to_spreadsheet(filename):
    """
    Load osm data from xml. Return (nodes, ways, relations) dicts (id->object).
    """

    coldet = ColumnDetector()
    p = make_parser()
    h = Handler(coldet)
    p.setContentHandler(h)
    p.parse(filename)

    outputter = TSVOutputter(list(coldet.columns))
    p = make_parser()
    h = Handler(outputter)
    p.setContentHandler(h)
    p.parse(filename)

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

def load_tsv_into_storage(filename, storage):
    """
    Load TSV file with filename filename into attribute storage storage.
    """
    f = open(filename)
    columns = f.readline().rstrip('\n').decode('utf-8').split("\t")
    for line in f:
        cells = line.rstrip('\n').decode('utf-8').split("\t")
        record = dict(zip(columns, cells))
        osm_type = record.pop(SPECIAL_COLUMN_OSM_TYPE)
        osm_id = record.pop(SPECIAL_COLUMN_OSM_ID)

        storage.add(osm_type, osm_id, record)

#load(sys.argv[1])
s = OSMAttributesStorage()
load_tsv_into_storage(sys.argv[1], s)

outputter=DiffOutputter(s)

p = make_parser()
h = Handler(outputter)
p.setContentHandler(h)
p.parse(sys.argv[2])
