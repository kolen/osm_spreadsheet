# Convert .osm file to TSV file containing ids of each node/way/relation, type and all attributes

import sys
from xml.sax import make_parser
from xml.sax.handler import ContentHandler
import sqlite3
import cPickle as pickle

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
        row = cur.fetchone()
        if row:
            return pickle.loads(row[0])

class ColumnDetector:
    def __init__(self):
        self.columns = set()

    def add_object(self, attrs):
        self.columns |= set(attrs.keys())

    def add_node(self, id, attrs, lat, lon):
        self.add_object(attrs)

    def add_way(self, id, attrs, nodes):
        self.add_object(attrs)

    def add_relation(self, id, attrs, members):
        self.add_object(attrs)

class GenericOutputter:
    def add_node(self, id, attrs, lat, lon):
        self.add_object(attrs, id, 'node')

    def add_way(self, id, attrs, nodes):
        self.add_object(attrs, id, 'way')

    def add_relation(self, id, attrs, members):
        self.add_object(attrs, id, 'relation')

class Outputter(GenericOutputter):
    def __init__(self, columns):
        print "\t".join(["osm_id", "osm_type"]+[c.encode('utf-8') for c in columns])
        self.columns = columns

    def add_object(self, attrs, id, type):
        print "\t".join([str(id), type] + [attrs.get(col, '').encode('utf-8') for col in self.columns])

class OSMAttributesStorageOutputter(GenericOutputter):
    def __init__(self, storage):
        self.storage = storage

    def add_object(self, attrs, id, type):
        self.storage.add(type, id, attrs)

class Handler(ContentHandler):
    def __init__(self, store):
        self.store = store
        self.obj = None

    def startElement(self, name, attrs):
        if name == "node":
            self.obj = (long(attrs['id']), {}, attrs['lat'], attrs['lon'])
        elif name == "way":
            self.obj = (long(attrs['id']), {}, [])
        elif name == "relation":
            self.obj = (long(attrs['id']), {}, [])
        elif name == "tag":
            self.obj[1][attrs['k']] = attrs['v']
        elif name == "nd":
            self.obj[2].append(long(attrs['ref']))
        elif name == "member":
            self.obj[2].append((long(attrs['ref']), attrs['type'], attrs['role']))

    def endElement(self, name):
        if name == "node":
            self.store.add_node(*self.obj)
        if name == "way":
            self.store.add_way(*self.obj)
        if name == "relation":
            self.store.add_relation(*self.obj)

def load(filename):
    """
    Load osm data from xml. Return (nodes, ways, relations) dicts (id->object).
    """

    coldet = ColumnDetector()
    p = make_parser()
    h = Handler(coldet)
    p.setContentHandler(h)
    p.parse(filename)

    outputter = Outputter(list(coldet.columns))
    p = make_parser()
    h = Handler(outputter)
    p.setContentHandler(h)
    p.parse(filename)

def load_into_storage(filename, storage):
    p = make_parser()
    outputter = OSMAttributesStorageOutputter(storage)
    h = Handler(outputter)
    p.setContentHandler(h)
    p.parse(filename)

#load(sys.argv[1])
s = OSMAttributesStorage()
load_into_storage(sys.argv[1], s)