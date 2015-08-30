#!/usr/bin/env python
import ConfigParser
import argparse
import base64
import datetime
from os.path import expanduser, join
import pickle
import sys
import tempfile
import os
import webbrowser

import markdown2 as markdown

from evernote.api.client import EvernoteClient
from evernote.edam.error.ttypes import EDAMUserException, EDAMSystemException
from evernote.edam.notestore.ttypes import NotesMetadataResultSpec, NoteFilter
import html2text
import evernote.edam.type.ttypes as ttypes

CLEVERNOTE_AUTH_WEB_SERVER = 'https://clevernote-cli.appspot.com/oauth'

# YOU MUST FILL THESE IN! GET ACCESS AT: http://www.evernote.com/about/developer/api/
MY_CONSUMER_KEY = 'dvjohnston-4706'
MY_CONSUMER_SECRET = '74581661d9888234'
# TODO: Add local cahce via sqlite DB.
# TODO: allow 3 different ways of viewing converted html data:
#      1) markdown,
#      2) regular text
#      3) full html text


class CleverNote(object):
    consumerKey = MY_CONSUMER_KEY
    consumerSecret = MY_CONSUMER_SECRET
    API_URL = "https://sandbox.evernote.com"
    userStoreUri = API_URL + "/edam/user"
    noteStoreUriBase = API_URL + "/edam/note/"
    authResult = None
    noteStore = None

    def __init__(self, auth_token, sandbox=False):
        self.listCount = 10
        self.noteName = ""
        self.verbose = False
        self.xml = False
        self.tags = []
        self.text = ""
        self.client = EvernoteClient(token=auth_token, sandbox=sandbox)
        self.userStore = self.client.get_user_store()
        self.noteStore = self.client.get_note_store()

    @staticmethod
    def parse_note_to_markdown(note):
        txt = html2text.html2text(note.decode('us-ascii', 'ignore'))
        return txt.decode('utf-8', 'replace')

    @staticmethod
    def convert_to_html(note):
        note_html = markdown.markdown(note)
        return note_html

    def wrap_note_to_enml(self, note_body):
        text = '<?xml version="1.0" encoding="UTF-8"?>' \
               '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml.dtd">' \
               '<en-note>'
        text += self.convert_to_html(note_body)
        text += "</en-note>"
        return text

    def create_note(self):
        new_text = get_input()
        mytext = self.wrap_note_to_enml(new_text)
        mynote = ttypes.Note()
        mynote.title = self.noteName
        mynote.content = mytext
        self.noteStore.createNote(self.client.token, mynote)

    def append_note(self, note_name=None):
        if note_name is None:
            note_name = self.noteName
        old_note = self.get_note(note_name, True, False)
        print self.parse_note_to_markdown(old_note.content)
        contents = get_input()
        note_content = self.convert_to_html(contents)
        old_note.content = str(old_note.content[:-10] + str(note_content) + "</en-note>")
        return self.noteStore.updateNote(self.client.token, old_note)

    def edit_note(self):
        note = self.get_note(self.noteName, True)
        if not note:
            self.create_note()
            return
        old_note = self.parse_note_to_markdown(note.content)

        (fd, tfn) = tempfile.mkstemp()

        os.write(fd, old_note)
        os.close(fd)
        editor = os.environ.get("editor")
        if not editor:
            editor = os.environ.get("EDITOR")
        if not editor:
            editor = "pico"
        os.system(editor + " " + tfn)
        file_to_open = open(tfn, 'r')
        contents = file_to_open.read()
        try:
            note_content = self.wrap_note_to_enml(contents)
            note.content = str(note_content)
            return self.noteStore.updateNote(self.client.token, note)
        except:
            print "Your XML was malformed. Edit again (Y/N)?"
            answer = ""
            while answer.lower() != 'n' and answer.lower() != 'y':
                answer = get_input()
            if answer.lower() == 'y':
                return self.edit_note()

    def find_most_recent_note(self):
        notelist = self.find_notes(1)
        if not len(notelist.notes):
            return
        notelist.notes[0].content = self.noteStore.getNoteContent(self.client.token,
                                                                  notelist.notes[0].guid)
        return notelist.notes[0]

    def display_note(self):
        if self.noteName:
            note = self.get_note(self.noteName, True)
        else:
            note = self.find_most_recent_note()
        if note is None:
            print "No note found with " + self.noteName
        else:
            print note.title
            print "----------"
            if self.xml:
                print note.content
            else:
                print self.parse_note_to_markdown(note.content)

    def find_notes(self, count=1, keywords=None, notebook_guid=None, tag_guids=None,
                   order=ttypes.NoteSortOrder.CREATED):
        spec = NotesMetadataResultSpec(includeTitle=True,
                                       includeUpdated=True,
                                       includeTagGuids=True)
        note_filter = NoteFilter(words=keywords, order=order, notebookGuid=notebook_guid,
                                 tagGuids=tag_guids)
        return self.noteStore.findNotesMetadata(self.client.token, note_filter, 0, count, spec)

    def get_note_by_guid(self, guid, get_content=True, get_resources=False):
        return self.noteStore.getNote(self.client.token, guid, get_content, get_resources,
                                      False, False)

    def get_note(self, name, full=False, resources=False):
        note_list = self.find_notes(1, name)
        if not len(note_list.notes):
            return None
        note = note_list.notes[0]
        note = self.get_note_by_guid(note.guid, full, resources)
        return note

    def list_notes(self, count=None):
        if count is None:
            count = self.listCount
        notelist = self.find_notes(count, keywords=self.noteName)
        for loopCount, note in enumerate(notelist.notes):
            dt = datetime.datetime.fromtimestamp(note.updated/1000)
            print_string = dt.strftime("%D | ")
            print_string += note.title
            if note.tagGuids:
                # TODO: cache tags
                tags = self.noteStore.getNoteTagNames(self.client.token, note.guid)
                print_string += "  ("
                for t in tags:
                    print_string += t + ", "
                print_string = print_string[:-2] + ")"
            print print_string
            if loopCount == count:
                break


def request_oauth_token(sandbox=False):
    client = EvernoteClient(consumer_key=MY_CONSUMER_KEY,
                            consumer_secret=MY_CONSUMER_SECRET,
                            sandbox=sandbox)
    resp_server = CLEVERNOTE_AUTH_WEB_SERVER
    # resp_server = 'http://localhost:8090/oauth'
    req_token = client.get_request_token(resp_server)
    webbrowser.open_new_tab(client.get_authorize_url(req_token))
    auth_string64 = str(raw_input("Auth String: "))
    auth_string = base64.b64decode(auth_string64)
    auth_dict = pickle.loads(auth_string)
    oauth_token = auth_dict['token']
    verifier = auth_dict['verifier']
    access_token = client.get_access_token(oauth_token, req_token['oauth_token_secret'], verifier)
    return access_token


def args_to_string(args):
    if args:
        full_string = ""
        for a in args:
            full_string += a + " "
        full_string = full_string[:-1]
        return full_string


def process_date_string(date_string):
    try:
        date = datetime.datetime.strptime(date_string, "%d/%m/%y")
    except:
        # if (verbose): print "Cannot parse date " + dateString + ". Ignoring"
        return
    return date


def write_defaults(conf_file):
    config = ConfigParser.SafeConfigParser()
    config.add_section('Auth')
    with open(conf_file, 'wb') as configfile:
        config.write(configfile)


def get_config_file():
    home_dir = expanduser("~")
    return join(home_dir, ".clevernote")


def open_config():
    conf_file = get_config_file()
    config = ConfigParser.SafeConfigParser()
    try:
        config.read(conf_file)
    except IOError:
        write_defaults(conf_file)
        return open_config()
    return config


def write_config(section, var, value):
    config = open_config()
    try:
        config.add_section(section)
    except ConfigParser.DuplicateSectionError:
        pass
    if value is None:
        config.remove_option(section, var)
    else:
        config.set(section, var, value)
    conf_file = get_config_file()
    with open(conf_file, 'wb') as configfile:
        config.write(configfile)


def read_auth_token():
    config = open_config()
    return config.get('Auth', 'auth_token')


def get_input():
    string = ""
    line = sys.stdin.readline()
    while line:
        string += line
        line = sys.stdin.readline()
    return string


def parse_args():
    parser = argparse.ArgumentParser(description="Command line interface to Evernote",
                                     prog="clevernote")
    subparsers = parser.add_subparsers(dest='action',
                                       help="Actions. See 'enote <action> --help' "
                                            "to see detailed help on each command")
    commands = {
        'append': ['add content to the end of an existing note', '+', CleverNote.append_note],
        'create': ['create a new note', '+', CleverNote.create_note],
        'show': ['show the content of an existing note', '*', CleverNote.display_note],
        'edit': ['edit an existing note in interactive editor', '*', CleverNote.edit_note],
        'find': ['find existing notes', '*', CleverNote.find_notes],
        'list': ['show existing notes', '*', CleverNote.list_notes],
        # 'sync': [''],
        'attach': ['add a file to an existing note', '+', None],
        'delete': ['remove a note', '+', None],
    }
    sub_parsers = {}
    for command, extra in commands.iteritems():
        sub_parsers[command] = subparsers.add_parser(command, help=extra[0])
        sub_parsers[command].add_argument('note_keywords',  # dest="noteName",
                                          help='Name of note. Supports partial matching',
                                          nargs=extra[1])
        sub_parsers[command].set_defaults(func=extra[2])
    sub_parsers['find'].add_argument("--startdate", dest="startdate", action="store")
    sub_parsers['find'].add_argument("--enddate", dest="enddate", action="store")

    parser.add_argument("-t", "--tag", dest="tag", action="store")
    parser.add_argument("-x", "--xml", dest="xml", action="store_true")
    parser.add_argument("--no-xml", dest="forcexml", action="store_false")
    parser.add_argument("--force-xml", dest="forcexml", action="store_true")
    parser.add_argument("--count", dest="count", action="store", type=int, default=10)
    args = parser.parse_args()

    return args


def setup_auth(sandbox=False):
    print "No valid auth token found in config file."
    print "Clevernote will now open a web browser to authorize with your Evernote account."
    print "After authentication, paste the token back at this prompt"
    raw_input("<Press Enter to continue>")
    # if invalid or no token, go through oauth dance, and store token
    write_config('Auth', 'auth_token', None)
    auth_token = request_oauth_token(sandbox=sandbox)
    write_config('Auth', 'auth_token', base64.b64encode(auth_token))
    try:
        CleverNote(auth_token, sandbox=sandbox)
    except:
        print("Unknown error logging into Evernote service")
        return -1
    print "Success. Please re-run clevernote."
    return 0


def main():
    # parse command line arguments
    args = parse_args()
    sandbox = True

    # get Oauth token
    try:
        auth_token = base64.b64decode(read_auth_token())
        clevernote = CleverNote(auth_token, sandbox=sandbox)
    except (TypeError, ConfigParser.Error, EDAMUserException, EDAMSystemException):
        setup_auth(sandbox)
        return

    for k, v in args.__dict__.iteritems():
        if k != 'func':
            clevernote.__setattr__(k, v)
    clevernote.__setattr__('noteName', " ".join(args.note_keywords))
    # call appropriate function
    args.func.__get__(clevernote)
    res = args.func(clevernote)
    pass


def junk(clevernote, args):
    clevernote.startDate = process_date_string(args.startdate)
    clevernote.endDate = process_date_string(args.enddate)


if __name__ == "__main__":
    main()
