import datetime
from pyramid.view import view_config

@view_config(route_name='index', renderer='index.pt')
def index(request):
    return {}

@view_config(route_name='recordings', renderer='json')
def recordings(request):
    request.db.execute('SELECT recording.id AS recording_id, recording.status AS recording_status, recording.season_pass_id, station_program.air_date_time, station_program.duration, station_program.new, program.id as program_id, program.title, program.episode_title, program.description, program.long_description, program.cast_list, program.original_air_date, program.season, program.episode, station.name AS station_name, station.affiliate, lineup_station.atsc FROM recording JOIN station_program ON station_program.id = recording.station_program_id JOIN program ON program.id = station_program.program_id JOIN station ON station.id = station_program.station_id JOIN lineup_station ON lineup_station.station_id = station.id WHERE station.active ORDER BY station_program.air_date_time')
    return [recording_data(row) for row in request.db.fetchall()]

@view_config(route_name='delete_recording', renderer='json')
def delete_recording(request):
    id = request.matchdict['id']
    try:
        request.dvr.delete_recording(id)
        return {'deleted': id}
    except Exception as e:
        return {'error': str(e)}

@view_config(route_name='skip_recording', renderer='json')
def skip_recording(request):
    id = request.matchdict['id']
    try:
        request.dvr.skip_recording(id)
        return {'skipped': id}
    except Exception as e:
        return {'error': str(e)}

@view_config(route_name='enable_recording', renderer='json')
def enable_recording(request):
    id = request.matchdict['id']
    try:
        request.dvr.enable_recording(id)
        return {'enabled': id}
    except Exception as e:
        return {'error': str(e)}

@view_config(route_name='recording', renderer='recording.pt')
def recording(request):
    recording_id = request.matchdict['id']
    request.db.execute('SELECT recording.id AS recording_id, recording.status AS recording_status, recording.season_pass_id, station_program.air_date_time, station_program.duration, station_program.new, program.id as program_id, program.title, program.episode_title, program.description, program.long_description, program.cast_list, program.original_air_date, program.season, program.episode, station.name AS station_name, station.affiliate, lineup_station.atsc FROM recording JOIN station_program ON station_program.id = recording.station_program_id JOIN program ON program.id = station_program.program_id JOIN station ON station.id = station_program.station_id JOIN lineup_station ON lineup_station.station_id = station.id WHERE recording.id = %s', [recording_id])
    row = request.db.fetchone()
    return recording_data(row) if row else {'error': 'Recording {0} not found'.format(recording_id)}

def season_episode(season, episode):
    if season and episode:
        return 'S{0:02d}E{1:02d}'.format(season, episode)
    else:
        return None

def recording_data(row):
    return {
        'recording': {
            'id': row.recording_id,
            'status': row.recording_status,
            'season_pass_id': row.season_pass_id,
            'air_date_time': row.air_date_time,
            'duration': row.duration,
            'duration_as_string': str(datetime.timedelta(seconds = row.duration)),
            'new': row.new
        },
        'program': {
            'id': row.program_id,
            'title': row.title,
            'season': row.season,
            'episode': row.episode,
            'season_episode': season_episode(row.season, row.episode),
            'episode_title': row.episode_title,
            'description': row.description,
            'long_description': row.long_description,
            'cast_list': row.cast_list,
            'original_air_date': row.original_air_date
        },
        'station': {
            'name': row.station_name,
            'affiliate': row.affiliate,
            'atsc': row.atsc
        }
    }

@view_config(route_name='season_passes', renderer='json')
def season_passes(request):
    request.db.execute('SELECT * FROM season_pass ORDER BY priority ASC, created_at ASC')
    return request.db.fetchall()

@view_config(route_name='add_season_pass', renderer='json')
def add_season_pass(request):
    title = request.GET['title']
    new_only = request.GET['new_only'] if 'new_only' in request.GET else True
    return request.dvr.add_season_pass(title, new_only)

@view_config(route_name='search', renderer='json')
def search(request):
    term = request.GET['term']
    request.db.execute('SELECT DISTINCT program.title FROM program JOIN station_program ON station_program.program_id = program.id JOIN station ON station.id = station_program.station_id WHERE station.active AND plainto_tsquery(\'english\', %s) @@ program.tsv ORDER BY program.title', [term])
    return request.db.fetchall()
