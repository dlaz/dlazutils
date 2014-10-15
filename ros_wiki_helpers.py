#!/usr/bin/env python
import ast, symtable
import codegen # pip install codegen
import mimetypes
import sys, os, re
import airspeed

# import clang.cindex
from collections import namedtuple, defaultdict

Extraction = namedtuple('Extraction', ['type', 'pattern'])

PARAM      = 0
SUBSCRIBER = 1
PUBLISHER  = 2

DEFAULT_DESC = 'No description provided'

DOC_TEMPLATE = airspeed.Template('''#macro (dot).#end
  $doc_type {
  #foreach ($info in $infos)
  #set($count = ($velocityCount-1))
  $count#dot()name = $info.name
    $count#dot()type = $info.type
    $count#dot()desc = $info.desc
  #end
}''')


src_types = ('text/x-c', 'text/x-python')

class Walker:
    files = []
    def walk(self, path):
        for root, subfolders, files in os.walk(path):
            if not self.ignore(root):
                self.files.extend([os.path.join(root, f) for f in files if (mimetypes.guess_type(f)[0] in src_types)])
                for folder in subfolders:
                    self.walk(os.path.join(root, folder))

    def ignore(self, s):
        for e in ['build', 'srv', 'srv_gen', 'msg', 'cfg']:
            if e in os.path.split(s): return True
        return False



def output_doc(doc_type, infos):
    return DOC_TEMPLATE.merge(dict(doc_type=doc_type, infos=infos))

class NodeInfo(object):
    def __init__(self):
        self.pubs   = []
        self.subs   = []
        self.params = []

        self.node_name = 'unknown'

    def add_pub(self, name, type, desc):
        self.pubs.append(NodeInfo.DocInfo(name, type, desc))

    def add_sub(self, name, type, desc):
        self.subs.append(NodeInfo.DocInfo(name, type, desc))

    def add_param(self, name, type, desc):
        self.params.append(NodeInfo.DocInfo(name, type, desc))


    def output(self, node_num):
        return '''
node.%(node_num)s {
  name = %(name)s
  desc = %(desc)s
%(subs)s
%(pubs)s
%(params)s
}
''' % dict(
        node_num=node_num,
        name=self.node_name,
        desc=DEFAULT_DESC,
        subs=output_doc('sub', self.subs),
        pubs=output_doc('pub', self.pubs),
        params=output_doc('param', self.params)
    )
    class DocInfo(object):
        template = airspeed.Template('''#macro (dot).#end
    $count#dot()name = $name
    $count#dot()type = $type
    $count#dot()desc = $desc
    ''')
        def __init__(self, name, type, desc):
            self.name = name
            self.type = type
            self.desc = desc

        def output(self, num):
            return self.template.merge(dict(name=self.name, type=self.type, desc=self.desc, count=num))

        def __repr__(self):
            return self.output('x')

def msg_from_type(path):
    return path.replace('.msg.', '/').replace('::', '/')

class PythonWikiVisitor(ast.NodeVisitor):
    class ImportVisitor(ast.NodeVisitor):
        def __init__(self):
            self.imports = {}
            super(PythonWikiVisitor.ImportVisitor, self).__init__()

        def visit_Import(self, node):
            for n in node.names:
                if n.asname:
                    self.imports[n.asname] = n.name
                else:
                    self.imports[n.name] = n.name
            return super(PythonWikiVisitor.ImportVisitor, self).generic_visit(node)

        def visit_ImportFrom(self, node):
            for n in node.names:
                if n.asname:
                    self.imports[n.asname] = '%s.%s' % (node.module, n.name)
                else:
                    self.imports[n.name] = '%s.%s' % (node.module, n.name)

    gen = codegen.SourceGenerator(0)

    def __init__(self, symbols):
        self.symbols = symbols
        self.info = NodeInfo()
        self.imports = dict()
        super(PythonWikiVisitor, self).__init__()

    def visit(self, node):
        if not self.imports:
            iv = PythonWikiVisitor.ImportVisitor()
            iv.visit(node)
            self.imports.update(iv.imports)
        super(PythonWikiVisitor, self).visit(node)
 
    def resolve_name(self, node):
        '''
        If it's a constant, return that.
        If it's a variable which is a constant, look it up in the symbol table.
        Otherwise pretty print the node's code
        '''
        if type(node) == ast.Str:
            return node.s
        if type(node) == ast.Name:
            if node.id in ('True', 'False'):
                return node.id.lower()
            # if self.symbols.lookup(node.id).is_imported():
            if node.id in self.imports:
                return self.imports[node.id]
            else: # TODO: figure out if this is a constant that can be returned
                return node.id
        if type(node) == ast.Call and len(node.args) == 1:
            return self.resolve_name(node.args[0])
        if type(node) == ast.Num:
            return node.n
        self.gen.visit(node)
        return ''.join(self.gen.result)

    def resolve_type(self, val):
        if type(val) == int:
            return 'int'
        if type(val) == float:
            return 'float'
        if val in ('True', 'False'):
            return 'bool'
        return 'string'

    def visit_Call(self, node):
        if hasattr(node.func, 'attr'):
            if node.func.attr == 'init_node':
                name = self.resolve_name(node.args[0])
                self.info.node_name = name
            elif node.func.attr == 'Subscriber':
                name, data_class = [self.resolve_name(a) for a in node.args[:2]]
                self.info.add_sub(name, msg_from_type(data_class), DEFAULT_DESC)
            elif node.func.attr == 'Publisher':
                name, data_class = [self.resolve_name(a) for a in node.args[:2]]
                self.info.add_pub(name, msg_from_type(data_class), DEFAULT_DESC)
            elif node.func.attr == 'get_param':
                args = [self.resolve_name(a) for a in node.args]
                kwargs, kwvals = zip(*[(k.arg, self.resolve_name(k.value)) for k in node.keywords]) if node.keywords else ([],[])
                default = None
                if 'default' in kwargs:
                    default = kwvals[kwargs.index('default')]
                self.info.add_param(args[0], self.resolve_type(default), 'Defaults to %s' % default if default is not None else DEFAULT_DESC)

        return super(PythonWikiVisitor, self).generic_visit(node)

class CWikiVisitor(object):
    exprs = [
        Extraction('params', re.compile(r"param\((?P<name>.+),\s*.+,\s*(?P<default>.+)\)")),
        Extraction('params', re.compile(r"getParam\((?P<name>.+),\s*.+\)")),
        Extraction('pubs',   re.compile(r"advertise<(?P<type>.+)>\((?P<name>.+),\s*.+\)")),
        Extraction('subs',   re.compile(r"Subscriber.*<(?P<type>.+)> ?(?P<var_name>[a-zA-Z0-9_]+)?(\((?P<name>.+),\s*.+,\s*.+\))?")),
    ]
    init_expr = re.compile(r"init\(.+,\s*.+,\s*(.+)\)")
    sub_details_expr = r'%s\(.+,\s*"(?P<name>[a-zA-Z0-9_]+)"\s*,\s*.+\)'

    def __init__(self, filename):
        self.info = NodeInfo()
        with open(filename, 'r') as f:
            self.src = f.read()

    def guess_type(self, data):
        try:
            float(data)
            return 'double'
        except: pass
        try:
            int(data)
            return 'int'
        except: pass
        if data.lower() in ('true', 'false'):
            return 'bool'
        return 'string'

    def visit(self):
        init = self.init_expr.findall(self.src)
        if init:
            self.info.node_name = init[0].strip('"\'')
            for info_type, patt in self.exprs:
                for match in patt.finditer(self.src):
                    gd = match.groupdict()
                    gd['desc'] = 'No description provided'
                    if gd.get('var_name', None) and not gd['name']:
                        gd['name'] = self.find_subscriber_details(gd['var_name'])
                    if not gd['name']: gd['name'] = ''
                    for k,v in gd.iteritems():
                        gd[k] = v.strip('"\'')
                    if 'type' in gd:
                        gd['type'] = msg_from_type(gd['type'])
                    if 'default' in gd:
                        gd['desc'] = 'Defaults to %s' % gd['default']
                        gd['type'] = self.guess_type(gd['default'])

                    if info_type == 'params':
                        self.info.add_param(
                            gd['name'],
                            gd['type'] if 'type' in gd else '',
                            gd['desc']
                        )
                    if info_type == 'subs':
                        self.info.add_sub(
                            gd['name'],
                            gd['type'],
                            gd['desc']
                        )
                    if info_type == 'pubs':
                        self.info.add_pub(
                            gd['name'],
                            gd['type'],
                            gd['desc']
                        )
    def find_subscriber_details(self, var_name):
        expr = re.compile(self.sub_details_expr % var_name)
        matches = expr.findall(self.src)
        if matches:
            return matches[0]
        return ''

if __name__ == '__main__':
    filename = os.path.expanduser(sys.argv[1])
    files = [filename]

    if os.path.isdir(filename):
        walker = Walker()
        walker.walk(filename)
        files = walker.files

    num = 0
    for filename in set(files):
        filetype, _ = mimetypes.guess_type(filename)

        v = None
        if filetype == 'text/x-c':
            v = CWikiVisitor(filename)
            v.visit()
        elif filetype == 'text/x-python':
            with open(filename, 'r') as f:
                src = f.read()
                parsed = ast.parse(src, filename)
                v = PythonWikiVisitor(symtable.symtable(src, filename, 'exec'))
                v.visit(parsed)
        else:
            print >> sys.stderr, 'Unrecognized filetype %s' % filetype
            continue
        if v.info.node_name is not 'unknown':
            print v.info.output(num)
            num += 1
