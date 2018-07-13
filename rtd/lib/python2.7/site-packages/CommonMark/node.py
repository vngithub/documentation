import re


reContainer = re.compile(
    r'(Document|BlockQuote|List|Item|Paragraph|'
    r'Header|Emph|Strong|Link|Image)')


def is_container(node):
    return (re.match(reContainer, node.t) is not None)


class NodeWalker:

    def __init__(self, root):
        self.current = root
        self.root = root
        self.entering = True

    def nxt(self):
        cur = self.current
        entering = self.entering

        if cur is None:
            return None

        container = is_container(cur)

        if entering and container:
            if cur.first_child:
                self.current = cur.first_child
                self.entering = True
            else:
                # stay on node but exit
                self.entering = False
        elif cur == self.root:
            self.current = None
        elif cur.nxt is None:
            self.current = cur.parent
            self.entering = False
        else:
            self.current = cur.nxt
            self.entering = True

        return {
            'entering': entering,
            'node': cur,
        }

    def resumeAt(self, node, entering):
        self.current = node
        self.entering = (entering is True)


class Node:

    @staticmethod
    def makeNode(tag, start_line, start_column):
        return Node(t=tag, start_line=start_line, start_column=start_column)

    def __init__(self, t="", c="", destination="", label="",
                 start_line="", start_column="", title=""):
        self.t = t
        self.c = c
        self.parent = None
        self.first_child = None
        self.last_child = None
        self.prv = None
        self.nxt = None
        self.destination = destination
        self.label = label
        self.is_open = True
        self.last_line_blank = False
        self.start_line = start_line
        self.start_column = start_column
        self.end_line = start_line
        self.string_content = ''
        self.literal = None
        self.strings = []
        self.inline_content = []
        self.list_data = {}
        self.title = title
        self.info = ''
        self.tight = bool()
        self.attributes = {}
        self.is_fenced = False
        self.fence_length = 0
        self.fence_char = None
        self.fence_offset = None
        self.pos = {}
        self.level = None

    def __repr__(self):
        return "Node {t} [{start}:{end}]".format(
            t=self.t,
            start=self.start_line,
            end=self.end_line,
            )

    def pretty(self):
        from pprint import pprint
        pprint(self.__dict__)

    def unlink(self):
        if self.prv:
            self.prv.nxt = self.nxt
        elif self.parent:
            self.parent.first_child = self.nxt

        if self.nxt:
            self.nxt.prv = self.prv
        elif self.parent:
            self.parent.last_child = self.prev

        self.parent = None
        self.nxt = None
        self.prv = None

    def append_child(self, child):
        child.unlink()
        child.parent = self
        if self.last_child:
            self.last_child.nxt = child
            child.prv = self.last_child
            self.last_child = child
        else:
            self.first_child = child
            self.last_child = child

    def prepend_child(self, child):
        child.unlink()
        child.parent = self
        if self.first_child:
            self.first_child.prv = child
            child.nxt = self.first_child
            self.first_child = child
        else:
            self.first_child = child
            self.last_child = child

    def insert_after(self, sibling):
        sibling.unlink()
        sibling.nxt = self.nxt
        if sibling.nxt:
            sibling.nxt.prv = sibling
        sibling.prv = self
        self.nxt = sibling
        sibling.parent = self.parent
        if not sibling.nxt:
            sibling.parent.last_child = sibling

    def insert_before(self, sibling):
        sibling.unlink()
        sibling.prv = self.prv
        if sibling.prv:
            sibling.prv.nxt = sibling
        sibling.nxt = self
        self.prv = sibling
        sibling.parent = self.parent
        if not sibling.prv:
            sibling.parent.first_child = sibling

    def is_container(self):
        return is_container(self)

    def walker(self):
        return NodeWalker(self)
