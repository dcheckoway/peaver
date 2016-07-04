import sys
sys.path.append('..')
from lib.database import DatabaseClient
from lib.dvr import DVR

import datetime
from pyramid.config import Configurator
from pyramid.renderers import JSON

def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include('pyramid_chameleon')

    config.registry.db = DatabaseClient()
    config.registry.dvr = DVR()
    
    def db(request):
        return config.registry.db

    def dvr(request):
        return config.registry.dvr

    config.add_request_method(db, 'db', reify=True)
    config.add_request_method(dvr, 'dvr', reify=True)
    
    json_renderer = JSON()
    def datetime_adapter(obj, request):
        return obj.isoformat()
    json_renderer.add_adapter(datetime.datetime, datetime_adapter)
    json_renderer.add_adapter(datetime.date, datetime_adapter)
    config.add_renderer('json', json_renderer)
    
    config.add_route('index', '/')
    config.add_route('recordings', 'recordings')
    config.add_route('recording', 'recording/{id}')
    config.add_route('delete_recording', 'delete_recording/{id}')
    config.add_route('skip_recording', 'skip_recording/{id}')
    config.add_route('season_passes', 'season_passes')
    config.add_route('add_season_pass', 'add_season_pass')
    config.add_route('search', 'search')
    config.scan('.views')
    return config.make_wsgi_app()
