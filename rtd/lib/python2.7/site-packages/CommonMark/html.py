from __future__ import absolute_import

import re
import sys
from warnings import warn

from CommonMark.common import escape_xml

# if python3 use html.parser and urllib.parse, else use HTMLParser and urllib
if sys.version_info >= (3, 0):
    import urllib.parse
    if sys.version_info >= (3, 4):
        import html.parser
        HTMLunescape = html.parser.HTMLParser().unescape
    else:
        from .entitytrans import _unescape
        HTMLunescape = _unescape
    HTMLquote = urllib.parse.quote
    HTMLunquote = urllib.parse.unquote
    URLparse = urllib.parse.urlparse
else:
    import urllib
    import urlparse
    from CommonMark import entitytrans
    HTMLunescape = entitytrans._unescape
    HTMLquote = urllib.quote
    HTMLunquote = urllib.unquote
    URLparse = urlparse.urlparse


reHtmlTag = re.compile(r'\<[^>]*\>')
reUnsafeProtocol = re.compile(
    r'^javascript:|vbscript:|file:|data:', re.IGNORECASE)
reSafeDataProtocol = re.compile(
    r'^data:image\/(?:png|gif|jpeg|webp)', re.IGNORECASE)


def tag(name, attrs=[], selfclosing=False):
    """Helper function to produce an HTML tag."""
    result = '<' + name
    for attr in attrs:
        result += ' {}="{}"'.format(attr[0], attr[1])
    if selfclosing:
        result += ' /'

    result += '>'
    return result


def potentially_unsafe(url):
    return re.match(reUnsafeProtocol, url) and not \
        re.match(reSafeDataProtocol, url)


class HTMLRenderer(object):
    blocksep = "\n"
    innersep = "\n"
    softbreak = "\n"
    escape_pairs = (("[&]", '&amp;'),
                    ("[<]", '&lt;'),
                    ("[>]", '&gt;'),
                    ('["]', '&quot;'))

    @staticmethod
    def inTags(tag, attribs, contents, selfclosing=None):
        """ Helper function to produce content in a pair of HTML tags."""
        result = "<" + tag
        if (len(attribs) > 0):
            i = 0
            while (len(attribs) > i) and (not attribs[i] is None):
                attrib = attribs[i]
                result += (" " + attrib[0] + '="' + attrib[1] + '"')
                i += 1
        if (len(contents) > 0):
            result += ('>' + contents + '</' + tag + '>')
        elif (selfclosing):
            result += " />"
        else:
            result += ('></' + tag + '>')
        return result

    def __init__(self):
        pass

    def URLescape(self, s):
        """ Escape href URLs."""
        if not re.search("mailto|MAILTO", s):
            if sys.version_info >= (3, 0):
                return re.sub(
                    "[&](?![#](x[a-f0-9]{1,8}|[0-9]{1,8});" +
                    "|[a-z][a-z0-9]{1,31};)",
                    "&amp;",
                    HTMLquote(
                        HTMLunescape(s),
                        ":/=*%?&)(#"),
                    re.IGNORECASE)
            else:
                return re.sub(
                    "[&](?![#](x[a-f0-9]{1,8}|[0-9]{1,8});" +
                    "|[a-z][a-z0-9]{1,31};)",
                    "&amp;",
                    HTMLquote(
                        HTMLunescape(s).encode("utf-8"),
                        ":/=*%?&)(#"),
                    re.IGNORECASE)
        else:
            return s

    def escape(self, s, preserve_entities=None):
        """ Escape HTML entities."""
        if preserve_entities:
            e = self.escape_pairs[1:]
            s = re.sub(
                "[&](?![#](x[a-f0-9]{1,8}|[0-9]{1,8});|[a-z][a-z0-9]{1,31};)",
                "&amp;", HTMLunescape(s), re.IGNORECASE)
        else:
            e = self.escape_pairs
        for r in e:
            s = re.sub(r[0], r[1], s)
        return s

    def renderInline(self, inline):
        """ Render an inline element as HTML."""
        attrs = None
        if (inline.t == "Str"):
            return self.escape(inline.c)
        elif (inline.t == "Softbreak"):
            return self.softbreak
        elif inline.t == "Hardbreak":
            return self.inTags('br', [], "", True) + "\n"
        elif inline.t == "Emph":
            return self.inTags('em', [], self.renderInlines(inline.c))
        elif inline.t == "Strong":
            return self.inTags("strong", [], self.renderInlines(inline.c))
        elif inline.t == "Html":
            return inline.c
        elif inline.t == "Entity":
            if inline.c == "&nbsp;":
                return " "
            else:
                return self.escape(inline.c, True)
        elif inline.t == "Link":
            attrs = [['href', self.URLescape(inline.destination)]]
            if inline.title:
                attrs.append(['title', self.escape(inline.title, True)])
            return self.inTags('a', attrs, self.renderInlines(inline.label))
        elif inline.t == "Image":
            attrs = [['src', self.escape(inline.destination, True)], [
                     'alt', self.escape(self.renderInlines(inline.label))]]
            if inline.title:
                attrs.append(['title', self.escape(inline.title, True)])
            return self.inTags('img', attrs, "", True)
        elif inline.t == "Code":
            return self.inTags('code', [], self.escape(inline.c))
        else:
            warn("Unknown inline type " + inline.t)
            return ""

    def renderInlines(self, inlines):
        """ Render a list of inlines."""
        result = ''
        for i in range(len(inlines)):
            result += self.renderInline(inlines[i])
        return result

    def renderBlock(self,  block, in_tight_list):
        """ Render a single block element."""
        tag = attr = info_words = None
        if (block.t == "Document"):
            whole_doc = self.renderBlocks(block.children)
            if (whole_doc == ""):
                return ""
            else:
                return (whole_doc + "\n")
        elif (block.t == "Paragraph"):
            if (in_tight_list):
                return self.renderInlines(block.inline_content)
            else:
                return self.inTags('p', [],
                                   self.renderInlines(block.inline_content))
        elif (block.t == "BlockQuote"):
            filling = self.renderBlocks(block.children)
            if (filling == ""):
                a = self.innersep
            else:
                a = self.innersep + \
                    self.renderBlocks(block.children) + self.innersep
            return self.inTags('blockquote', [], a)
        elif (block.t == "Item"):
            return self.inTags("li", [],
                               self.renderBlocks(block.children,
                                                 in_tight_list).strip())
        elif (block.t == "List"):
            if (block.list_data['type'] == "Bullet"):
                tag = "ul"
            else:
                tag = "ol"
            attr = [] if (not block.list_data.get('start')) or block.list_data[
                'start'] == 1 else [['start', str(block.list_data['start'])]]
            return self.inTags(tag, attr,
                               self.innersep +
                               self.renderBlocks(block.children, block.tight) +
                               self.innersep)
        elif ((block.t == "ATXHeader") or (block.t == "SetextHeader")):
            tag = "h" + str(block.level)
            return self.inTags(tag, [],
                               self.renderInlines(block.inline_content))
        elif (block.t == "IndentedCode"):
            return HTMLRenderer.inTags('pre', [], HTMLRenderer.inTags('code',
                                       [], self.escape(block.string_content)))
        elif (block.t == "FencedCode"):
            info_words = []
            if block.info:
                info_words = re.split(r" +", block.info)
            attr = [] if len(info_words) == 0 else [
                ["class", "language-" + self.escape(info_words[0], True)]]
            return self.inTags('pre', [], self.inTags('code',
                               attr, self.escape(block.string_content)))
        elif (block.t == "HtmlBlock"):
            return block.string_content
        elif (block.t == "ReferenceDef"):
            return ""
        elif (block.t == "HorizontalRule"):
            return self.inTags("hr", [], "", True)
        else:
            warn("Unknown block type" + block.t)
            return ""

    def renderBlocks(self, blocks, in_tight_list=None):
        """ Render a list of block elements, separated by this.blocksep."""
        result = []
        for i in range(len(blocks)):
            if not blocks[i].t == "ReferenceDef":
                result.append(self.renderBlock(blocks[i], in_tight_list))
        return self.blocksep.join(result)

    def out(self, s):
        if self.disable_tags > 0:
            self.buf += s.replace(reHtmlTag, '')
        else:
            self.buf += s
        self.last_out = s

    def cr(self):
        if self.last_out != '\n':
            self.buf += '\n'
            self.last_out = '\n'

    def renderNodes(self, block):
        walker = block.walker()
        self.buf = ''
        self.last_out = '\n'
        self.disable_tags = 0

        event = walker.nxt()
        while event is not None:
            attrs = []
            entering = event['entering']
            node = event['node']
            if node.t == 'Text' or node.t == 'Str':
                self.out(escape_xml(node.literal, False))
            elif node.t == 'Softbreak':
                self.out(self.softbreak)
            elif node.t == 'Hardbreak':
                self.out(tag('br', [], True))
                self.cr()
            elif node.t == 'Emph':
                self.out(tag('em' if entering else '/em'))
            elif node.t == 'Strong':
                self.out(tag('strong' if entering else '/strong'))
            elif node.t == 'HtmlInline':
                self.out(node.literal)
            elif node.t == 'Link':
                if entering:
                    if not potentially_unsafe(node.destination):
                        attrs.push([
                            'href', escape_xml(node.destination, True)])
                    if node.title:
                        attrs.push(['title', escape_xml(node.title, True)])
                    self.out(tag('a', attrs))
                else:
                    self.out(tag('/a'))
            elif node.t == 'Code':
                self.out(
                    tag('code') +
                    escape_xml(node.literal, False) +
                    tag('/code'))
            elif node.t == 'Document':
                pass
            elif node.t == 'Paragraph':
                grandparent = node.parent.parent
                if (grandparent is None or grandparent.t != 'List'):
                    if entering:
                        self.cr()
                        self.out(tag('p', attrs))
                    else:
                        self.out(tag('/p'))
                        self.cr()
            elif node.t == 'BlockQuote':
                if entering:
                    self.cr()
                    self.out(tag('blockquote', attrs))
                    self.cr()
                else:
                    self.cr()
                    self.out(tag('/blockquote', attrs))
                    self.cr()
            elif node.t == 'Item':
                if entering:
                    self.out(tag('li', attrs))
                else:
                    self.out(tag('/li'))
                    self.cr()
            elif node.t == 'List':
                if node.list_data['type'] == 'Bullet':
                    tagname = 'ul'
                else:
                    tagname = 'ol'
                if entering:
                    try:
                        start = node.list_data['start']
                    except KeyError:
                        start = None
                    if start is not None and start != 1:
                        attrs.append(['start', str(start)])
                    self.cr()
                    self.out(tag(tagname, attrs))
                    self.cr()
                else:
                    self.cr()
                    self.out(tag('/' + tagname))
                    self.cr()
            elif node.t == 'Heading':
                tagname = 'h' + node.level
                if entering:
                    self.cr()
                    self.out(tag(tagname, attrs))
                else:
                    self.out(tag('/' + tagname))
                    self.cr()
            elif node.t == 'CodeBlock':
                if node.info:
                    info_words = re.split(r'\s+', node.info)
                else:
                    info_words = []
                if len(info_words) > 0 and len(info_words[0]) > 0:
                    attrs.append([
                        'class',
                        'language-' + escape_xml(info_words[0], True)
                    ])
                self.cr()
                self.out(tag('pre') + tag('code', attrs))
                self.out(escape_xml(node.literal, False))
                self.out(tag('/code') + tag('/pre'))
                self.cr()
            elif node.t == 'HtmlBlock':
                self.out(node.literal)
            elif node.t == 'ThematicBreak' or node.t == 'HorizontalRule':
                self.cr()
                self.out(tag('hr', attrs, True))
                self.cr()
            else:
                raise ValueError('Unknown node type {}'.format(node.t))
            event = walker.nxt()
        return self.buf

    render = renderNodes
