# Convert .osm file to TSV file containing ids of each node/way/relation, type and all attributes

import sys
from xml.sax import make_parser
from xml.sax.handler import ContentHandler

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

class Outputter:
    def __init__(self, columns):
        print "\t".join(["osm_id", "osm_type"]+[c.encode('utf-8') for c in columns])
        self.columns = columns

    def add_object(self, attrs, id, type):
        print "\t".join([str(id), type] + [attrs.get(col, '').encode('utf-8') for col in self.columns])

    def add_node(self, id, attrs, lat, lon):
        self.add_object(attrs, id, 'node')

    def add_way(self, id, attrs, nodes):
        self.add_object(attrs, id, 'way')

    def add_relation(self, id, attrs, members):
        self.add_object(attrs, id, 'relation')

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

load(sys.argv[1])
