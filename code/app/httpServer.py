#!/usr/bin/env python2.7

import logging
import ConfigParser
import argparse
import json
import os
from twisted.internet import reactor
from twisted.web import static
from twisted.web.resource import Resource
from twisted.web.server import Site, NOT_DONE_YET
from paxoscore.proposer import Proposer

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
logging.basicConfig(filename="/server.log", level=logging.DEBUG, format='%(message)s')


class MainPage(Resource):
    def getChild(self, name, request):
        if name == '':
            return self
        else:
            print name, request
            return Resource.getChild(self, name, request)

    def render_GET(self, request):
        f = open('%s/web/index.html' % THIS_DIR, 'r')
        return f.read()


class WebServer(Resource):
    isLeaf = True

    def __init__(self, proposer):
        Resource.__init__(self)
        self.proposer = proposer

    def _waitResponse(self, result, request):
        try:
            logging.info("Sending response [{}]".format(result))
            result = result.rstrip('\t\r\n\0')
            request.write(result)
            request.finish()
        except Exception as ex:
            logging.error("Error sending response [{}] => [{}]".format(result, ex))

    def render_GET(self, request):
        print request
        request.args['action'] = 'get'
        data = json.dumps(request.args)

        logging.info("Received get request with [{}]".format(data))

        d = self.proposer.submit(data)
        d.addCallback(self._waitResponse, request)
        return NOT_DONE_YET

    def render_POST(self, request):
        print request
        request.args['action'] = 'put'
        data = json.dumps(request.args)

        logging.info("Received post request with [{}]".format(data))

        d = self.proposer.submit(data)
        d.addCallback(self._waitResponse, request)
        return NOT_DONE_YET


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Paxos Proposer.')
    parser.add_argument('--cfg', required=True)
    args = parser.parse_args()
    config = ConfigParser.ConfigParser()
    config.read(args.cfg)
    proposer = Proposer(config, 0)
    
    logging.info("Starting http server")

    try:
        reactor.listenUDP(config.getint('proposer', 'port'), proposer)
    except Exception as ex:
        logging.error("Error listening UDP [{}]".format(ex))

    logging.info("Starting server on port 8080")

    root = MainPage()
    server = WebServer(proposer)
    root.putChild('jquery.min.js', static.File('%s/web/jquery.min.js' % THIS_DIR))
    root.putChild('get', server)
    root.putChild('put', server)
    factory = Site(root)

    try:
        reactor.listenTCP(8080, factory)
        reactor.run()
    except Exception as ex:
        logging.error("Error listening tcp: [{}]".format(ex))
