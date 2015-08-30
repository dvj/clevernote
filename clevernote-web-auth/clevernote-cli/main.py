#!/usr/bin/env python

import base64
import pickle
import webapp2
import cgi


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('')


class OAuthHandler(webapp2.RequestHandler):
    def get(self):
        token = self.request.get('oauth_token')
        verifier = self.request.get('oauth_verifier')
        auth_dict = {'token': token, 'verifier': verifier}
        data = pickle.dumps(auth_dict)
        data64 = base64.b64encode(data)
        self.response.write('<html><body>Paste into command line:<br>')
        self.response.write('<textArea rows="5" cols="80">')
        self.response.write(cgi.escape(data64))
        self.response.write('</textArea></body></html>')

    def post(self):
        self.response.write('<html><body>Paste the following Auth String into the prompt in the '
                            'command line of clevernote:<pre>')
        self.response.write(cgi.escape(self.request.get('oauth_token')))
        self.response.write('</pre></body></html>')

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/oauth', OAuthHandler)
], debug=True)
