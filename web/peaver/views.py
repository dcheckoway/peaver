from pyramid.view import view_config

@view_config(route_name='index', renderer='index.pt')
def index(request):
    return {}

@view_config(route_name='recordings', renderer='json')
def recordings(request):
    request.db.execute('select recording.id as recording_id, recording.status as recording_status, recording.season_pass_id, station_program.air_date_time, station_program.duration, station_program.new, program.title, program.episode_title, program.description, program.long_description, program.cast_list, program.original_air_date, program.season, program.episode, station.name as station_name, station.affiliate, lineup_station.atsc from recording join station_program on station_program.id = recording.station_program_id join program on program.id = station_program.program_id join station on station.id = station_program.station_id join lineup_station on lineup_station.station_id = station.id order by station_program.air_date_time')
    return [{
        'id': row.recording_id,
        'status': row.recording_status,
        'season_pass_id': row.season_pass_id,
        'air_date_time': row.air_date_time,
        'duration': row.duration,
        'new': row.new,
        'program': {
            'title': row.title,
            'season': row.season,
            'episode': row.episode,
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
    } for row in request.db.fetchall()]
