import logging, sets
import dateutil.parser
from database import DatabaseClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

def parse_date(dstr):
    return dateutil.parser.parse(dstr)

class Updater(DatabaseClient):
    def __init__(self, api, config):
        self.api = api
        DatabaseClient.__init__(self, config)

    def update_schedules(self):
        self.api.ensure_online()
        self.load_lineups()
        self.reconcile_schedules()

    def load_lineups(self):
        logger.info('Loading lineups')
        for l in self.api.get('lineups').lineups:
            self.load_lineup(l.lineup)

    def load_lineup(self, lineup_id):
        logger.info('Loading lineup: {0}'.format(lineup_id))
        lineup = self.api.get('lineups/{0}'.format(lineup_id))
        self.execute('SELECT 1 FROM lineup WHERE id = %s', [lineup_id])
        if self.fetchone():
            self.execute('UPDATE lineup SET transport = %s, modified = %s WHERE id = %s',
                           [lineup.metadata.transport, parse_date(lineup.metadata.modified), lineup_id])
        else:
            self.execute('INSERT INTO lineup (id, transport, modified) VALUES (%s, %s, %s)',
                           [lineup_id, lineup.metadata.transport, parse_date(lineup.metadata.modified)])

        logger.info('Reconciling stations for lineup {0}'.format(lineup_id))
        for s in lineup.stations:
            station_id = s.stationID
            (city, state) = (s.broadcaster.city, s.broadcaster.state) if 'broadcaster' in s else (None, None)
            (logo_url, logo_width, logo_height) = (s.logo.URL, s.logo.width, s.logo.height) if 'logo' in s else (None, None, None)
            self.execute('SELECT 1 FROM station WHERE id = %s', [station_id])
            if self.fetchone():
                self.execute('UPDATE station SET name = %s, callsign = %s, affiliate = %s, city = %s, state = %s, logo_url = %s, logo_width = %s, logo_height = %s WHERE id = %s', [s.name, s.callsign, s.get('affiliate'), city, state, logo_url, logo_width, logo_height, station_id])
            else:
                self.execute('INSERT INTO station (id, active, name, callsign, affiliate, city, state, logo_url, logo_width, logo_height) VALUES (%s, FALSE, %s, %s, %s, %s, %s, %s, %s, %s)', [station_id, s.name, s.callsign, s.get('affiliate'), city, state, logo_url, logo_width, logo_height])

        logger.info('Reconciling lineup_station entries for {0}'.format(lineup_id))
        for m in lineup.map:
            station_id = m.stationID
            channel = m.uhfVhf
            if 'atscMajor' in m:
                atsc = '{0}.{1}'.format(m.atscMajor, m.atscMinor) if 'atscMinor' in m else str(m.atscMajor)
            else:
                atsc = None
            self.execute('SELECT 1 FROM lineup_station WHERE lineup_id = %s AND station_id = %s', [lineup_id, station_id])
            if self.fetchone():
                self.execute('UPDATE lineup_station SET channel = %s, atsc = %s WHERE lineup_id = %s AND station_id = %s', [channel, atsc, lineup_id, station_id])
            else:
                logger.info('Adding station {0} (channel={1}, {2}) to lineup {3}'.format(station_id, channel, atsc, lineup_id))
                self.execute('INSERT INTO lineup_station (lineup_id, station_id, channel, atsc) VALUES (%s, %s, %s, %s)', [lineup_id, station_id, channel, atsc])

    def reconcile_schedules(self):
        logger.info('Reconciling schedule data for all stations')
        self.execute('SELECT id FROM station')
        station_ids = sorted([r.id for r in self.fetchall()])
        for idx, station_id in enumerate(station_ids):
            logger.info('Loading schedule for station {0} ({1}/{2})'.format(station_id, idx + 1, len(station_ids)))
            dates_to_update = []
            for start_date_utc, metadata in sorted(self.api.post('schedules/md5', [{"stationID": station_id}])[station_id].items()):
                if metadata.md5 != self.get_station_schedule_md5(station_id, start_date_utc):
                    dates_to_update.append(start_date_utc)
            if len(dates_to_update) > 0:
                self.update_station_schedules(station_id, dates_to_update)

    def save_program(self, p):
        program_id = p.programID
        md5 = p.md5
        title = p.titles[0].title120
        episode_title = p.get('episodeTitle150')
        description = long_description = None
        if 'descriptions' in p:
            d = p.descriptions
            if 'description100' in d:
                description = d.description100[0].description
            if 'description1000' in d:
                long_description = d.description1000[0].description
        original_air_date = parse_date(p.originalAirDate) if 'originalAirDate' in p else None
        season = episode = None
        if 'metadata' in p:
            md = p.metadata[0]
            if 'Gracenote' in md:
                season = md.Gracenote.season
                episode = md.Gracenote.episode
        genres = ','.join(p.genres) if 'genres' in p else None
        venue = teams = game_date = None
        if 'eventDetails' in p:
            if 'venue100' in p.eventDetails:
                venue = p.eventDetails.venue100
            if 'teams' in p.eventDetails and len(p.eventDetails.teams) == 2:
                team1 = p.eventDetails.teams[0]
                team2 = p.eventDetails.teams[1]
                teams = '{0} vs. {1}'.format(team1.name, team2.name) if 'isHome' in team1 else '{0} at {1}'.format(team1.name, team2.name)
            if 'gameDate' in p.eventDetails:
                game_date = parse_date(p.eventDetails.gameDate)
        entity_type = p.entityType
        show_type = p.get('showType')
        movie_release_year = int(p.movie.year) if 'movie' in p else None
        duration = p.get('duration')
        cast_list = ', '.join([c0.name for c0 in p.cast]) if 'cast' in p else None
        self.execute('SELECT 1 FROM program WHERE id = %s', [program_id])
        if self.fetchone():
            logger.info('Updating program {0}'.format(program_id))
            self.execute('UPDATE program SET md5 = %s, title = %s, episode_title = %s, description = %s, long_description = %s, original_air_date = %s, season = %s, episode = %s, genres = %s, venue = %s, teams = %s, game_date = %s, entity_type = %s, show_type = %s, movie_release_year = %s, duration = %s, cast_list = %s WHERE id = %s', [md5, title, episode_title, description, long_description, original_air_date, season, episode, genres, venue, teams, game_date, entity_type, show_type, movie_release_year, duration, cast_list, program_id])
        else:
            self.execute('INSERT INTO program (id, md5, title, episode_title, description, long_description, original_air_date, season, episode, genres, venue, teams, game_date, entity_type, show_type, movie_release_year, duration, cast_list) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)', [program_id, md5, title, episode_title, description, long_description, original_air_date, season, episode, genres, venue, teams, game_date, entity_type, show_type, movie_release_year, duration, cast_list])

    def load_programs(self, program_ids):
        logger.info('Loading {0} program(s)'.format(len(program_ids)))
        for p in self.api.post('programs', program_ids):
            self.save_program(p)

    def get_program_md5(self, program_id):
        self.execute('SELECT md5 FROM program WHERE id = %s', [program_id])
        row = self.fetchone()
        return row.md5 if row else None

    def get_station_schedule_md5(self, station_id, start_date_utc):
        self.execute('SELECT md5 FROM station_schedule WHERE station_id = %s AND start_date_utc = %s', [station_id, start_date_utc])
        row = self.fetchone()
        return row.md5 if row else None

    def update_station_schedules(self, station_id, dates):
        logger.info('Updating schedule data for station {0} on {1}'.format(station_id, dates))
        schedules = self.api.post('schedules', [{'stationID': station_id, 'date': dates}])
        # It's way more efficient if we batch load programs
        program_ids_to_load = sets.Set()
        for schedule in schedules:
            for sp in schedule.programs:
                program_id = sp.programID
                if not program_id in program_ids_to_load and self.get_program_md5(program_id) != sp.md5:
                    program_ids_to_load.add(program_id)
        if len(program_ids_to_load) > 0:
            self.load_programs(list(program_ids_to_load))
        # Now do the actual schedule updates
        for schedule in schedules:
            start_date_utc = schedule.metadata.startDate # NOTE: This date is in UTC
            schedule_md5 = schedule.metadata.md5
            for sp in schedule.programs:
                program_id = sp.programID
                air_date_time = parse_date(sp.airDateTime)
                duration = sp.duration
                new = sp.new if 'new' in sp else False
                self.execute('SELECT id, program_id, duration, new FROM station_program WHERE station_id = %s AND start_date_utc = %s AND air_date_time = %s',
                               [station_id, start_date_utc, air_date_time])
                row = self.fetchone()
                if row:
                    sp_id = row.id
                    old_program_id = row.program_id
                    old_duration = row.duration
                    old_new = row.new
                    if old_program_id == program_id:
                        if old_duration != duration or old_new != new:
                            logger.info('Updating station_program details for station {0} at {1}, before=(duration:{2}, new:{3}), after=(duration:{4}, new:{5})'.format(station_id, air_date_time, old_duration, old_new, duration, new))
                            self.execute('UPDATE station_program SET duration = %s, new = %s, md5 = %s WHERE id = %s',
                                           [duration, new, schedule_md5, sp_id])
                        else:
                            # Nothing changed, just bump the md5
                            self.execute('UPDATE station_program SET md5 = %s WHERE id = %s',
                                           [schedule_md5, sp_id])
                    else:
                        logger.info('PROGRAM CHANGE: station {0} at {1} was formerly program {2}, is now {3}, duration:{4}, new:{5}'.format(station_id, air_date_time, old_program_id, program_id, duration, new))
                        self.execute('UPDATE station_program SET program_id = %s, duration = %s, new = %s, md5 = %s WHERE id = %s',
                                       [program_id, duration, new, schedule_md5, sp_id])
                else:
                    logger.debug('New station_program, station {0} at {1} program {2}, duration:{3}, new:{4}'.format(station_id, air_date_time, program_id, duration, new))
                    self.execute('INSERT INTO station_program (station_id, start_date_utc, air_date_time, program_id, duration, new, md5) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                                   [station_id, start_date_utc, air_date_time, program_id, duration, new, schedule_md5])
            self.execute('SELECT 1 FROM station_schedule WHERE station_id = %s AND start_date_utc = %s', [station_id, start_date_utc])
            if self.fetchone():
                self.execute('UPDATE station_schedule SET md5 = %s WHERE station_id = %s AND start_date_utc = %s', [schedule_md5, station_id, start_date_utc])
            else:
                self.execute('INSERT INTO station_schedule (station_id, start_date_utc, md5) VALUES (%s, %s, %s)', [station_id, start_date_utc, schedule_md5])

            # Clean up anything that's no longer scheduled (by virtue of an older md5)
            self.execute('DELETE FROM station_schedule WHERE station_id = %s AND start_date_utc = %s AND md5 != %s', [station_id, start_date_utc, schedule_md5])
