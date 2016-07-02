# Peaver

https://en.wikipedia.org/wiki/Personal_video_recorder

## Prerequisites

- HDHomeRun Tuner (tested with HDHomeRun EXTEND HDTC-2US)
- Plex Media Server (https://www.plex.tv)
- Python
- PostgreSQL
- Mac OS X (or Linux, in theory)
- Account on Schedules Direct (http://www.schedulesdirect.org)

## Installation

- Ensure HDHomeRun is up and running
- Ensure Plex Media Server is running
- `/usr/bin/env python2 -c 'print "Python2 is installed"' 2>/dev/null || brew install python`
- `psql -c "select 'PostgreSQL is installed'" 2>/dev/null || brew install postgresql`
- `createdb peaver`
- `psql peaver < schema.sql`
- `pip install requests`
- `pip install dateutils`
- `pip install psycopg2`
- `./setup`
