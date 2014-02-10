"""
Stub implementation of LTI Provider.

What is supported:
------------------

1.) This LTI Provider can service only one Tool Consumer at the same time. It is
not possible to have this LTI multiple times on a single page in LMS.

"""

from uuid import uuid4
import textwrap
import urllib
from oauthlib.oauth1.rfc5849 import signature
import oauthlib.oauth1
import hashlib
import base64
import mock
import requests
from http import StubHttpRequestHandler, StubHttpService

class StubLtiHandler(StubHttpRequestHandler):
    """
    A handler for LTI POST and GET requests.
    """
    DEFAULT_CLIENT_KEY = 'test_client_key'
    DEFAULT_CLIENT_SECRET = 'test_client_secret'
    DEFAULT_LTI_ENDPOINT = 'correct_lti_endpoint'
    DEFAULT_LTI_ADDRESS = 'http://127.0.0.1:{port}/'

    def do_GET(self):
        """
        Handle a GET request from the client and sends response back.

        Used for checking LTI Provider started correctly.
        """
        self.send_response(200, 'This is LTI Provider.', {'Content-type': 'text/plain'})

    def do_POST(self):
        """
        Handle a POST request from the client and sends response back.
        """
        if 'grade' in self.path and self._send_graded_result().status_code == 200:
            status_message = 'LTI consumer (edX) responded with XML content:<br>' + self.server.grade_data['TC answer']
            content = self._create_content(status_message)
            self.send_response(200, content)

        # Respond to request with correct lti endpoint
        elif self._is_correct_lti_request():
            params = {k: v for k, v in self.post_dict.items() if k != 'oauth_signature'}

            if self._check_oauth_signature(params, self.post_dict.get('oauth_signature', "")):
                status_message = "This is LTI tool. Success."

                # Set data for grades what need to be stored as server data
                if 'lis_outcome_service_url' in self.post_dict:
                    self.server.grade_data = {
                        'callback_url': self.post_dict.get('lis_outcome_service_url'),
                        'sourcedId': self.post_dict.get('lis_result_sourcedid')
                    }

                submit_url = '//{}:{}'.format(*self.server.server_address)
                content = self._create_content(status_message, submit_url)
                self.send_response(200, content)

            else:
                content = self._create_content("Wrong LTI signature")
                self.send_response(200, content)
        else:
            content = self._create_content("Invalid request URL")
            self.send_response(500, content)

    def _send_graded_result(self):
        """
        Send grade request.
        """
        values = {
            'textString': 0.5,
            'sourcedId': self.server.grade_data['sourcedId'],
            'imsx_messageIdentifier': uuid4().hex,
        }
        payload = textwrap.dedent("""
            <?xml version = "1.0" encoding = "UTF-8"?>
                <imsx_POXEnvelopeRequest  xmlns="http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0">
                  <imsx_POXHeader>
                    <imsx_POXRequestHeaderInfo>
                      <imsx_version>V1.0</imsx_version>
                      <imsx_messageIdentifier>{imsx_messageIdentifier}</imsx_messageIdentifier> /
                    </imsx_POXRequestHeaderInfo>
                  </imsx_POXHeader>
                  <imsx_POXBody>
                    <replaceResultRequest>
                      <resultRecord>
                        <sourcedGUID>
                          <sourcedId>{sourcedId}</sourcedId>
                        </sourcedGUID>
                        <result>
                          <resultScore>
                            <language>en-us</language>
                            <textString>{textString}</textString>
                          </resultScore>
                        </result>
                      </resultRecord>
                    </replaceResultRequest>
                  </imsx_POXBody>
                </imsx_POXEnvelopeRequest>
        """)

        data = payload.format(**values)
        url = self.server.grade_data['callback_url']
        headers = {
            'Content-Type': 'application/xml',
            'X-Requested-With': 'XMLHttpRequest',
            'Authorization': self._oauth_sign(url, data)
            }

        # Send request ignoring verifirecation of SSL certificate
        response = requests.post(url, data=data, headers=headers, verify=False)

        self.server.grade_data['TC answer'] = response.content
        return response

    def _create_content(self, response_text, submit_url=None):
        """
        Return content (str) either for launch, send grade or get result from TC.
        """
        if submit_url:
            submit_form = textwrap.dedent("""
                <form action="{}/grade" method="post">
                    <input type="submit" name="submit-button" value="Submit">
                </form>
            """).format(submit_url)
        else:
            submit_form = ''

        # Show roles only for LTI launch.
        if self.post_dict.get('roles'):
            role = '<h5>Role: {}</h5>'.format(self.post_dict['roles'])
        else:
            role = ''

        response_str = textwrap.dedent("""
                <html>
                    <head>
                        <title>TEST TITLE</title>
                    </head>
                    <body>
                        <div>
                            <h2>IFrame loaded</h2>
                            <h3>Server response is:</h3>
                            <h3 class="result">{response}</h3>
                            {role}
                        </div>
                        {submit_form}
                    </body>
                </html>
            """).format(response=response_text, role=role, submit_form=submit_form)

        return urllib.unquote(response_str)

    def _is_correct_lti_request(self):
        """
        Return a boolean indicating whether the URL path is a valid LTI end-point.
        """
        lti_endpoint = self.server.config.get('lti_endpoint', self.DEFAULT_LTI_ENDPOINT)
        return lti_endpoint in self.path

    def _oauth_sign(self, url, body):
        """
        Signs request and returns signed body and headers.
        """
        client_key = self.server.config.get('client_key', self.DEFAULT_CLIENT_KEY)
        client_secret = self.server.config.get('client_secret', self.DEFAULT_CLIENT_SECRET)
        client = oauthlib.oauth1.Client(
            client_key=unicode(client_key),
            client_secret=unicode(client_secret)
        )
        headers = {
            # This is needed for body encoding:
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # Calculate and encode body hash. See http://oauth.googlecode.com/svn/spec/ext/body_hash/1.0/oauth-bodyhash.html
        sha1 = hashlib.sha1()
        sha1.update(body)
        oauth_body_hash = base64.b64encode(sha1.digest())
        __, headers, __ = client.sign(
            unicode(url.strip()),
            http_method=u'POST',
            body={u'oauth_body_hash': oauth_body_hash},
            headers=headers
        )
        headers = headers['Authorization'] + ', oauth_body_hash="{}"'.format(oauth_body_hash)
        return headers

    def _check_oauth_signature(self, params, client_signature):
        """
        Checks oauth signature from client.

        `params` are params from post request except signature,
        `client_signature` is signature from request.

        Builds mocked request and verifies hmac-sha1 signing::
            1. builds string to sign from `params`, `url` and `http_method`.
            2. signs it with `client_secret` which comes from server settings.
            3. obtains signature after sign and then compares it with request.signature
            (request signature comes form client in request)

        Returns `True` if signatures are correct, otherwise `False`.

        """
        client_secret = unicode(self.server.config.get('client_secret', self.DEFAULT_CLIENT_SECRET))

        port = self.server.server_address[1]
        lti_base = self.DEFAULT_LTI_ADDRESS.format(port=port)
        lti_endpoint = self.server.config.get('lti_endpoint', self.DEFAULT_LTI_ENDPOINT)
        url = lti_base + lti_endpoint

        request = mock.Mock()
        request.params = [(unicode(k), unicode(v)) for k, v in params.items()]
        request.uri = unicode(url)
        request.http_method = u'POST'
        request.signature = unicode(client_signature)
        return signature.verify_hmac_sha1(request, client_secret)


class StubLtiService(StubHttpService):
    """
    A stub LTI provider server that responds
    to POST and GET requests to localhost.
    """

    HANDLER_CLASS = StubLtiHandler
