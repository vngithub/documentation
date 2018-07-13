from __future__ import absolute_import

import re
from CommonMark import common
from CommonMark.common import unescape
from CommonMark.node import Node


reLinkTitle = re.compile(
    '^(?:"(' + common.ESCAPED_CHAR + '|[^"\\x00])*"' +
    '|' +
    '\'(' + common.ESCAPED_CHAR + '|[^\'\\x00])*\'' +
    '|' +
    '\\((' + common.ESCAPED_CHAR + '|[^)\\x00])*\\))')
reLinkDestinationBraces = re.compile(
    '^(?:[<](?:[^<>\\n\\\\\\x00]' + '|' + common.ESCAPED_CHAR + '|' +
    '\\\\)*[>])')
reLinkDestination = re.compile(
    '^(?:' + common.REG_CHAR + '+|' + common.ESCAPED_CHAR + '|\\\\|' +
    common.IN_PARENS_NOSP + ')*')
reLinkLabel = re.compile(
    '^\\[(?:[^\\\\\\[\\]]|' + common.ESCAPED_CHAR + '|\\\\){0,1000}\\]')

reEscapable = re.compile('^' + common.ESCAPABLE)
reEntityHere = re.compile('^' + common.ENTITY, re.IGNORECASE)
reTicks = re.compile(r'`+')
reTicksHere = re.compile(r'^`+')
reEmailAutolink = re.compile(
    r"^<([a-zA-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)>")
reAutolink = re.compile(
    r'^<(?:coap|doi|javascript|aaa|aaas|about|acap|cap|cid|crid|data|'
    r'dav|dict|dns|file|ftp|geo|go|gopher|h323|http|https|iax|icap|im|'
    r'imap|info|ipp|iris|iris.beep|iris.xpc|iris.xpcs|iris.lwz|ldap|'
    r'mailto|mid|msrp|msrps|mtqp|mupdate|news|nfs|ni|nih|nntp|'
    r'opaquelocktoken|pop|pres|rtsp|service|session|shttp|sieve|'
    r'sip|sips|sms|snmp|soap.beep|soap.beeps|tag|tel|telnet|tftp|'
    r'thismessage|tn3270|tip|tv|urn|vemmi|ws|wss|xcon|xcon-userid|'
    r'xmlrpc.beep|xmlrpc.beeps|xmpp|z39.50r|z39.50s|adiumxtra|afp|afs|'
    r'aim|apt|attachment|aw|beshare|bitcoin|bolo|callto|chrome|'
    r'chrome-extension|com-eventbrite-attendee|content|cvs|dlna-playsingle|'
    r'dlna-playcontainer|dtn|dvb|ed2k|facetime|feed|finger|fish|gg|git|'
    r'gizmoproject|gtalk|hcp|icon|ipn|irc|irc6|ircs|itms|jar|jms|keyparc|'
    r'lastfm|ldaps|magnet|maps|market|message|mms|ms-help|msnim|mumble|mvn|'
    r'notes|oid|palm|paparazzi|platform|proxy|psyc|query|res|resource|rmi|'
    r'rsync|rtmp|secondlife|sftp|sgn|skype|smb|soldat|spotify|ssh|steam|svn|'
    r'teamspeak|things|udp|unreal|ut2004|ventrilo|view-source|webcal|wtai|'
    r'wyciwyg|xfire|xri|ymsgr):[^<>\x00-\x20]*>',
    re.IGNORECASE)
reSpnl = re.compile(r'^ *(?:\n *)?')
reWhitespace = re.compile(r'\s+')
reFinalSpace = re.compile(r' *$')

# Matches a character with a special meaning in markdown,
# or a string of non-special characters.
reMain = re.compile(r'^(?:[\n`\[\]\\!<&*_]|[^\n`\[\]\\!<&*_]+)', re.MULTILINE)
# Matches a string of non-special characters.
# reMain = re.compile(r'^[^\n`\[\]\\!<&*_\'"]+', re.MULTILINE);


def normalizeReference(s):
    """ Normalize reference label: collapse internal whitespace to
    single space, remove leading/trailing whitespace, case fold."""
    return re.sub(r'\s+', ' ', s.strip()).upper()


def text(s):
    node = Node(t='Str', c=s)
    node.literal = s
    return node


class InlineParser:
    """INLINE PARSER

    These are methods of an InlineParser class, defined below.
    An InlineParser keeps track of a subject (a string to be
    parsed) and a position in that subject.
    """

    def __init__(self):
        self.subject = ""
        self.label_nest_level = 0
        self.pos = 0
        self.refmap = {}

    def match(self, regexString, reCompileFlags=0):
        """
        If regexString matches at current position in the subject, advance
        position in subject and return the match; otherwise return None.
        """
        match = re.search(
            regexString, self.subject[self.pos:], flags=reCompileFlags)
        if match is None:
            return None
        else:
            self.pos += match.end(0)
            return match.group()

    def peek(self):
        """ Returns the character at the current subject position, or None if
        there are no more characters."""
        if self.pos < len(self.subject):
            return self.subject[self.pos]
        else:
            return None

    def spnl(self):
        """ Parse zero or more space characters, including at
        most one newline."""
        self.match(reSpnl)
        return 1

    # All of the parsers below try to match something at the current position
    # in the subject.  If they succeed in matching anything, they
    # push an inline matched, advancing the subject.

    def parseBackticks(self, block):
        """ Attempt to parse backticks, adding either a backtick code span or a
        literal sequence of backticks to the 'inlines' list."""
        ticks = self.match(reTicksHere)
        if ticks is None:
            return False
        afterOpenTicks = self.pos
        matched = self.match(reTicks)
        while matched is not None:
            if (matched == ticks):
                c = self.subject[afterOpenTicks:(self.pos - len(ticks))]
                c = c.strip()
                c = re.subn(reWhitespace, ' ', c)[0]
                block.append_child(Node(t='Code', c=c))
                return True
            matched = self.match(reTicks)
        # If we got here, we didn't match a closing backtick sequence.
        self.pos = afterOpenTicks
        block.append_child(text(ticks))
        return True

    def parseEscaped(self, block):
        """ Parse a backslash-escaped special character, adding either the
        escaped character, a hard line break (if the backslash is followed
        by a newline), or a literal backslash to the 'inlines' list."""
        subj = self.subject
        pos = self.pos
        if (subj[pos] == "\\"):
            if len(subj) > pos + 1 and (subj[pos + 1] == "\n"):
                block.append_child(Node(t="Hardbreak"))
                self.pos += 2
                return 2
            elif (reEscapable.search(subj[pos + 1:pos + 2])):
                block.append_child(text(subj[pos + 1:pos + 2]))
                self.pos += 2
                return 2
            else:
                self.pos += 1
                block.append_child(text("\\"))
                return 1
        else:
            return 0

    def parseAutoLink(self, block):
        """ Attempt to parse an autolink (URL or email in pointy brackets)."""
        m = self.match(reEmailAutolink)
        if m:
            # email
            dest = m[1:-1]
            block.append_child(
                Node(
                    t='Link',
                    title='',
                    label=[text(dest)],
                    destination='mailto:' + dest))
            return len(m)

        m = self.match(reAutolink)
        if m:
            # link
            dest = m[1:-1]
            block.append_child(
                Node(
                    t='Link',
                    title='',
                    label=[text(dest)],
                    destination=dest))
            return len(m)

        return 0

    def parseHtmlTag(self, block):
        """ Attempt to parse a raw HTML tag."""
        m = self.match(common.reHtmlTag)
        if (m):
            block.append_child(Node(t="Html", c=m))
            return len(m)
        else:
            return 0

    def scanDelims(self, c):
        """ Scan a sequence of characters == c, and return information about
        the number of delimiters and whether they are positioned such that
        they can open and/or close emphasis or strong emphasis.  A utility
        function for strong/emph parsing."""
        numdelims = 0
        char_before = char_after = None
        startpos = self.pos

        char_before = '\n' if self.pos == 0 else self.subject[self.pos - 1]

        while (self.peek() == c):
            numdelims += 1
            self.pos += 1

        a = self.peek()
        char_after = a if a else "\\n"

        can_open = (numdelims > 0) and (
            numdelims <= 3) and (not re.match("\s", char_after))
        can_close = (numdelims > 0) and (
            numdelims <= 3) and (not re.match("\s", char_before))

        if (c == "_"):
            can_open = can_open and (
                not re.match("[a-z0-9]", char_before, re.IGNORECASE))
            can_close = can_close and (
                not re.match("[a-z0-9]", char_after, re.IGNORECASE))
        self.pos = startpos
        return {
            "numdelims": numdelims,
            "can_open": can_open,
            "can_close": can_close
        }

    def handleDelim(self, cc, block):
        """Handle a delimiter marker for emphasis or a quote."""
        res = self.scanDelims(cc)
        if not res:
            return False
        numdelims = res['numdelims']
        startpos = self.pos

        self.pos += numdelims
        if cc == "'":
            contents = u'\u2019'
        elif cc == '"':
            contents = u'\u201C'
        else:
            contents = self.subject[startpos:self.pos]
        node = text(contents)
        block.append_child(node)

        # Add entry to stack for this opener
        self.delimiters = {
            'cc': cc,
            'numdelims': numdelims,
            'node': node,
            'previous': self.delimiters,
            'next': None,
            'can_open': res['can_open'],
            'can_close': res['can_close'],
            'active': True,
        }
        if self.delimiters['previous'] is not None:
            self.delimiters['previous']['next'] = self.delimiters
        return True

    def removeDelimiter(self, delim):
        if delim['previous'] is not None:
            delim['previous']['next'] = delim['next']
        if delim['next'] is None:
            # Top of stack
            self.delimiters = delim['previous']
        else:
            delim['next']['previous'] = delim['previous']

    @staticmethod
    def removeDelimitersBetween(bottom, top):
        if bottom['next'] != top:
            bottom['next'] = top
            top['previous'] = bottom

    def processEmphasis(self, stack_bottom):
        openers_bottom = {
            '_': stack_bottom,
            '*': stack_bottom,
            "'": stack_bottom,
            '"': stack_bottom,
        }

        # Find first closer above stack_bottom
        closer = self.delimiters
        while closer is not None and closer['previous'] != stack_bottom:
            closer = closer['previous']

        # Move forward, looking for closers, and handling each
        while closer is not None:
            closercc = closer['cc']
            if not (closer['can_close'] and
                    (closercc == '_' or
                     closercc == '*' or
                     closercc == "'" or
                     closercc == '"')):
                closer = closer['next']
            else:
                opener = closer['previous']
                opener_found = False
                while (opener is not None and opener != stack_bottom and
                       opener != openers_bottom[closercc]):
                    if opener['cc'] == closer['cc'] and opener['can_open']:
                        opener_found = True
                    opener = opener['previous']
                old_closer = closer

                if closercc == '*' or closercc == '_':
                    if not opener_found:
                        closer = closer['next']
                    elif closer is not None and opener is not None:
                        # Calculate actual number of delimiters used from
                        # closer
                        if closer['numdelims'] < 3 or opener['numdelims'] < 3:
                            if closer['numdelims'] <= opener['numdelims']:
                                use_delims = closer['numdelims']
                            else:
                                use_delims = opener['numdelims']

                        opener_inl = opener['node']
                        closer_inl = closer['node']

                        # Remove used delimiters from stack elts and inlines
                        opener['numdelims'] -= use_delims
                        closer['numdelims'] -= use_delims
                        opener_inl.literal = opener_inl.literal[
                            0:len(opener_inl.literal) - use_delims]
                        closer_inl.literal = closer_inl.literal[
                            0:len(closer_inl.literal) - use_delims]

                        # Build contents for new Emph element
                        if use_delims == 1:
                            emph = Node(t='Emph')
                        else:
                            emph = Node(t='Strong')

                        tmp = opener_inl.nxt()
                        while tmp and tmp != closer_inl:
                            nxt = tmp.nxt()
                            tmp.unlink()
                            emph.append_child(tmp)
                            tmp = nxt

                        opener_inl.insert_after(emph)

                        # Remove elts between opener and closer in delimiters
                        # stack
                        self.removeDelimitersBetween(opener, closer)

                        # If opener has 0 delims, remove it and the inline
                        if opener['numdelims'] == 0:
                            opener_inl.unlink()
                            self.removeDelimiter(opener)

                        if closer['numdelims'] == 0:
                            closer_inl.unlink()
                            tempstack = closer.nxt()
                            self.removeDelimiter(closer)
                            closer = tempstack

                elif closercc == "'":
                    closer['node'].literal = u'\u2019'
                    if opener_found:
                        opener['node'].literal = u'\u2018'
                    closer = closer['next']

                elif closercc == '"':
                    closer['node'].literal = u'\u201D'
                    if opener_found:
                        opener['node'].literal = u'\u201C'
                    closer = closer['next']

                if not opener_found:
                    # Set lower bound for future searches for openers:
                    openers_bottom[closercc] = old_closer['previous']
                    if not old_closer['can_open']:
                        # We can remove a closer that can't be an opener,
                        # once we've seen there's no matching opener:
                        self.removeDelimiter(old_closer)

        # Remove all delimiters
        while self.delimiters is not None and self.delimiters != stack_bottom:
            self.removeDelimiter(self.delimiters)

    def parseLinkTitle(self):
        """ Attempt to parse link title (sans quotes), returning the string
        or None if no match."""
        title = self.match(reLinkTitle)
        if title:
            return unescape(title[1:len(title)-1])
        else:
            return None

    def parseLinkDestination(self):
        """ Attempt to parse link destination, returning the string or
        None if no match."""
        res = self.match(reLinkDestinationBraces)
        if res is not None:
            return unescape(res[1:len(res) - 1])
        else:
            res2 = self.match(reLinkDestination)
            if res2 is not None:
                return unescape(res2)
            else:
                return None

    def parseLinkLabel(self):
        """
        Attempt to parse a link label, returning number of
        characters parsed.
        """
        m = self.match(reLinkLabel)
        if m is None or len(m) > 1001:
            return 0
        else:
            return len(m)

    def parseRawLabel(self, s):
        """ Parse raw link label, including surrounding [], and return
        inline contents.  (Note:  this is not a method of InlineParser.)"""
        return InlineParser().parse(s[1:-1])

    def parseLink(self, block):
        """ Attempt to parse a link.  If successful, add the link to
        inlines."""
        startpos = self.pos
        n = self.parseLinkLabel()

        if n == 0:
            return 0

        rawlabel = self.subject[startpos:n+startpos]

        if self.peek() == "(":
            self.pos += 1
            if self.spnl():
                dest = self.parseLinkDestination()
                if dest is not None and self.spnl():
                    if re.match(r"^\s", self.subject[self.pos - 1]):
                        title = self.parseLinkTitle()
                    else:
                        title = ""
                    if self.spnl() and self.match(r"^\)"):
                        block.append_child(
                            Node(
                                t="Link",
                                destination=dest,
                                title=title,
                                label=self.parseRawLabel(rawlabel)))
                        return self.pos - startpos
                    else:
                        self.pos = startpos
                        return 0
                else:
                    self.pos = startpos
                    return 0
            else:
                self.pos = startpos
                return 0

        savepos = self.pos
        self.spnl()
        beforelabel = self.pos
        n = self.parseLinkLabel()
        if n == 2:
            reflabel = rawlabel
        elif n > 0:
            reflabel = self.subject[beforelabel:beforelabel + n]
        else:
            self.pos = savepos
            reflabel = rawlabel
        if normalizeReference(reflabel) in self.refmap:
            link = self.refmap[normalizeReference(reflabel)]
        else:
            link = None
        if link:
            if link.get("title", None):
                title = link['title']
            else:
                title = ""
            if link.get("destination", None):
                destination = link['destination']
            else:
                destination = ""
            block.append_child(
                Node(
                    t="Link",
                    destination=destination,
                    title=title,
                    label=self.parseRawLabel(rawlabel)))
            return self.pos - startpos
        else:
            self.pos = startpos
            return 0
        self.pos = startpos
        return 0

    def parseEntity(self, block):
        """ Attempt to parse an entity, adding to inlines if successful."""
        m = self.match(reEntityHere)
        if m:
            block.append_child(Node(t="Entity", c=m))
            return len(m)
        else:
            return 0

    def parseString(self, block):
        """Parse a run of ordinary characters, or a single character with
        a special meaning in markdown, as a plain string."""
        m = self.match(reMain)
        if m:
            block.append_child(text(m))
            return len(m)
        else:
            return 0

    def parseNewline(self, block):
        """ Parse a newline.  If it was preceded by two spaces, return a hard
        line break; otherwise a soft line break."""
        if (self.peek() == '\n'):
            self.pos += 1
            lastc = block.last_child
            if lastc and lastc.t == 'Str' and lastc.c[-1] == ' ':
                hardbreak = lastc.c[-2] == ' '
                lastc.c = re.sub(reFinalSpace, '', lastc.c)
                if hardbreak:
                    myblock = Node(t='Hardbreak')
                else:
                    myblock = Node(t='Softbreak')
                block.append_child(myblock)
            else:
                block.append_child(Node(t='Softbreak'))
            return True
        else:
            return False

    def parseImage(self, block):
        """ Attempt to parse an image.  If the opening '!' is not followed
        by a link, add a literal '!' to inlines."""
        if (self.match("^!")):
            n = self.parseLink(block)
            if (n == 0):
                block.append_child(text("!"))
                return 1
            elif (block[len(block) - 1] and
                    (block[len(block) - 1].t == "Link")):
                block[len(block) - 1].t = "Image"
                return n + 1
            else:
                raise Exception("Shouldn't happen")
        else:
            return 0

    def parseReference(self, s, refmap):
        """ Attempt to parse a link reference, modifying refmap."""
        self.subject = s
        self.pos = 0
        self.label_nest_level = 0

        startpos = self.pos

        matchChars = self.parseLinkLabel()
        if (matchChars == 0):
            return 0
        else:
            rawlabel = self.subject[:matchChars]

        test = self.peek()
        if (test == ":"):
            self.pos += 1
        else:
            self.pos = startpos
            return 0
        self.spnl()

        dest = self.parseLinkDestination()
        if (dest is None or len(dest) == 0):
            self.pos = startpos
            return 0

        beforetitle = self.pos
        self.spnl()
        title = self.parseLinkTitle()
        if (title is None):
            title = ""
            self.pos = beforetitle

        if (self.match(r"^ *(?:\n|$)") is None):
            self.pos = startpos
            return 0

        normlabel = normalizeReference(rawlabel)
        if (not refmap.get(normlabel, None)):
            refmap[normlabel] = {
                "destination": dest,
                "title": title
            }
        return (self.pos - startpos)

    def parseInline(self, block):
        """ Parse the next inline element in subject, advancing subject position
        and adding the result to 'inlines'."""
        c = self.peek()
        res = None
        if c == -1:
            return False
        if (c == '\n'):
            res = self.parseNewline(block)
        elif (c == '\\'):
            res = self.parseEscaped(block)
        elif (c == '`'):
            res = self.parseBackticks(block)
        elif ((c == '*') or (c == '_')):
            res = self.handleDelim(c, block)
        elif (c == '['):
            res = self.parseLink(block)
        elif (c == '!'):
            res = self.parseImage(block)
        elif (c == '<'):
            res = self.parseAutoLink(block) or self.parseHtmlTag(block)
        elif (c == '&'):
            res = self.parseEntity(block)
        else:
            res = self.parseString(block)

        if not res:
            self.pos += 1
            block.append_child(Node(t='Str', c=c))

        return res

    def parseInlines(self, block):
        """
        Parse string content in block into inline children,
        using refmap to resolve references.
        """
        self.subject = block.string_content.strip()
        self.pos = 0
        self.delimiters = None
        while (self.parseInline(block)):
            pass
        # allow raw string to be garbage collected
        block.string_content = None
        self.processEmphasis(None)

    parse = parseInlines
