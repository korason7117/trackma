# This file is part of Trackma.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import datetime
import json
import socket
import urllib.error
import urllib.parse
import urllib.request

from trackma import utils
from trackma.lib.lib import lib


class libanilist(lib):
    """
    API class to communicate with Anilist

    Website: https://anilist.co

    messenger: Messenger object to send useful messages to
    """
    name = 'libanilist'
    msg = None
    logged_in = False

    api_info = {'name': 'Anilist', 'shortname': 'anilist',
                'version': '2.1', 'merge': False}
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': True,
        'can_date': True,
        'date_next_ep': True,
        'statuses_start': ['CURRENT', 'REPEATING'],
        'statuses_finish': ['COMPLETED'],
        'statuses_library': ['CURRENT', 'REPEATING', 'PAUSED', 'PLANNING'],
        'statuses':  ['CURRENT', 'COMPLETED', 'REPEATING', 'PAUSED', 'DROPPED', 'PLANNING'],
        'statuses_dict': {
            'CURRENT': 'Watching',
            'COMPLETED': 'Completed',
            'REPEATING': 'Rewatching',
            'PAUSED': 'Paused',
            'DROPPED': 'Dropped',
            'PLANNING': 'Plan to Watch'
        },
        'score_max': 100,
        'score_step': 1,
        'search_methods': [utils.SearchMethod.KW, utils.SearchMethod.SEASON],
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_update': True,
        'can_play': False,
        'can_date': True,
        'statuses_start': ['CURRENT', 'REPEATING'],
        'statuses_finish': ['COMPLETED'],
        'statuses':  ['CURRENT', 'COMPLETED', 'REPEATING', 'PAUSED', 'DROPPED', 'PLANNING'],
        'statuses_dict': {
            'CURRENT': 'Reading',
            'COMPLETED': 'Completed',
            'REPEATING': 'Rereading',
            'PAUSED': 'Paused',
            'DROPPED': 'Dropped',
            'PLANNING': 'Plan to Read'
        },
        'score_max': 100,
        'score_step': 1,
        'search_methods': [utils.SearchMethod.KW],
    }
    default_mediatype = 'anime'

    score_types = {
        'POINT_100': (100, 1),
        'POINT_10_DECIMAL': (10, 0.1),
        'POINT_10': (10, 1),
        'POINT_5': (5, 1),
        'POINT_3': (3, 1),
    }

    type_translate = {
        None: utils.Type.UNKNOWN,
        'TV': utils.Type.TV,
        'TV_SHORT': utils.Type.TV_SHORT,
        'MOVIE': utils.Type.MOVIE,
        'SPECIAL': utils.Type.SP,
        'OVA': utils.Type.OVA,
        'ONA': utils.Type.ONA,
        'MUSIC': utils.Type.OTHER,
        'MANGA': utils.Type.OTHER,
        'NOVEL': utils.Type.OTHER,
        'ONE_SHOT': utils.Type.OTHER,
    }

    status_translate = {
        None: utils.Status.UNKNOWN,
        'RELEASING': utils.Status.AIRING,
        'FINISHED': utils.Status.FINISHED,
        'NOT_YET_RELEASED': utils.Status.NOTYET,
        'CANCELLED': utils.Status.CANCELLED,
    }

    season_translate = {
        utils.Season.WINTER: 'WINTER',
        utils.Season.SPRING: 'SPRING',
        utils.Season.SUMMER: 'SUMMER',
        utils.Season.FALL: 'FALL',
    }
    rev_season_translate = {v: k for k, v in season_translate.items()}

    # Supported signals for the data handler
    signals = {'show_info_changed': None, }

    auth_url = "https://anilist.co/api/v2/"
    query_url = "https://graphql.anilist.co"
    client_id = "537"
    _client_secret = "9Hl31gyz2q9xMhhJwLKRA8DAn0pXl9sOHFf6I1YO"
    user_agent = 'Trackma/{}'.format(utils.VERSION)

    def __init__(self, messenger, account, userconfig):
        """Initializes the API"""
        super(libanilist, self).__init__(messenger, account, userconfig)

        self.pin = account['password'].strip()
        self.userid = self._get_userconfig('userid')

        if self.mediatype == 'manga':
            self.total_str = "chapters"
            self.watched_str = "chapters_read"
        else:
            self.total_str = "episodes"
            self.watched_str = "episodes_watched"

        # If we already know the scoreFormat of the cached list, apply it now
        self.scoreformat = self._get_userconfig(
            'scoreformat_' + self.mediatype)
        if self.scoreformat:
            self._apply_scoreformat(self.scoreformat)

        self.custom_lists = self._get_userconfig('custom_lists_' + self.mediatype) or []
        self.advanced_scoring = self._get_userconfig('advanced_scoring_' + self.mediatype) or [
            'Story', 'Characters', 'Visuals', 'Audio', 'Enjoyment'
        ]
        self.advanced_scoring_enabled = self._get_userconfig('advanced_scoring_enabled_' + self.mediatype) or False

        self.opener = urllib.request.build_opener()
        self.opener.addheaders = [('User-agent', self.user_agent)]

    def _raw_request(self, method, url, get=None, post=None, jsonpost=None, auth=False):
        if get:
            url = "{}?{}".format(url, urllib.parse.urlencode(get))
        if post:
            post = urllib.parse.urlencode(post).encode('utf-8')
        if jsonpost:
            post = json.dumps(jsonpost, ensure_ascii=False).encode('utf-8')

        request = urllib.request.Request(url, post)
        request.get_method = lambda: method

        request.add_header('Content-Type', 'application/json')
        request.add_header('Accept', 'application/json')

        if auth:
            request.add_header('Authorization', 'Bearer {}'.format(
                self.pin,
            ))

        try:
            response = self.opener.open(request, timeout=10)
            return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 400:
                raise utils.APIError("Invalid HTTP request: %s" % e.read())
            else:
                raise utils.APIError("HTTP error status: %s" % e.read())
        except urllib.error.URLError as e:
            raise utils.APIError("HTTP connection error: %s" % e.reason)
        except socket.timeout:
            raise utils.APIError("Connection timed out.")

    def _request(self, query, variables=None):
        if variables:
            data = {'query': query, 'variables': variables}
        else:
            data = {'query': query}

        return self._raw_request('POST', self.query_url, jsonpost=data, auth=True)

    def check_credentials(self):
        if len(self.pin) == 40:  # Old pins were 40 digits, new ones seem to be 654 digits
            raise utils.APIFatal("This appears to be a V1 API PIN. You need a V2 API PIN to continue using AniList."
                                 " Please re-authorize or re-create your AniList account.")

        if not self.userid:
            self._refresh_user_info()

        return True

    def _refresh_user_info(self):
        self.msg.info('Refreshing user details...')
        query = '''{Viewer{
  id name avatar{large} options{titleLanguage displayAdultContent}
  mediaListOptions{
    scoreFormat
    animeList { customLists advancedScoring advancedScoringEnabled }
    mangaList { customLists advancedScoring advancedScoringEnabled }
  }
}}'''
        data = self._request(query)['data']['Viewer']

        self._set_userconfig('userid', data['id'])
        self._set_userconfig('username', data['name'])

        m_opts = data.get('mediaListOptions') or {}
        user_opts = m_opts.get('animeList' if self.mediatype == 'anime' else 'mangaList') or {}
        if user_opts.get('customLists'):
            self.custom_lists = list(user_opts['customLists'])
            self._set_userconfig('custom_lists_' + self.mediatype, self.custom_lists)
        if user_opts.get('advancedScoring'):
            self.advanced_scoring = list(user_opts['advancedScoring'])
            self._set_userconfig('advanced_scoring_' + self.mediatype, self.advanced_scoring)
        if 'advancedScoringEnabled' in user_opts:
            self.advanced_scoring_enabled = bool(user_opts['advancedScoringEnabled'])
            self._set_userconfig('advanced_scoring_enabled_' + self.mediatype, self.advanced_scoring_enabled)

        self._emit_signal('userconfig_changed')

        self.userid = data['id']

    def get_custom_lists(self):
        """Return custom lists, fetching from upstream AniList if not cached."""
        if getattr(self, 'custom_lists', None):
            return self.custom_lists

        cached = self._get_userconfig('custom_lists_' + self.mediatype)
        if cached:
            self.custom_lists = list(cached)
            return self.custom_lists

        try:
            self.check_credentials()
            query = '''query {
  Viewer {
    mediaListOptions {
      animeList { customLists advancedScoring advancedScoringEnabled }
      mangaList { customLists advancedScoring advancedScoringEnabled }
    }
  }
}'''
            res = self._request(query)
            opts = res['data']['Viewer']['mediaListOptions']
            user_opts = opts.get('animeList' if self.mediatype == 'anime' else 'mangaList') or {}
            self.custom_lists = list(user_opts.get('customLists') or [])
            self._set_userconfig('custom_lists_' + self.mediatype, self.custom_lists)
            if 'advancedScoring' in user_opts and user_opts['advancedScoring']:
                self.advanced_scoring = list(user_opts['advancedScoring'])
                self._set_userconfig('advanced_scoring_' + self.mediatype, self.advanced_scoring)
            if 'advancedScoringEnabled' in user_opts:
                self.advanced_scoring_enabled = bool(user_opts['advancedScoringEnabled'])
                self._set_userconfig('advanced_scoring_enabled_' + self.mediatype, self.advanced_scoring_enabled)
            return self.custom_lists
        except Exception as e:
            self.msg.warn(f"Could not retrieve AniList custom lists: {e}")
            return getattr(self, 'custom_lists', []) or []

    def fetch_list(self):
        self.check_credentials()
        self.msg.info('Downloading list...')

        query = '''query ($id: Int!, $listType: MediaType) {
  MediaListCollection (userId: $id, type: $listType) {
    lists {
      name
      isCustomList
      status
      entries {
        ... mediaListEntry
      }
    }
    user {
      mediaListOptions {
        scoreFormat
        animeList {
          customLists
          advancedScoring
          advancedScoringEnabled
        }
        mangaList {
          customLists
          advancedScoring
          advancedScoringEnabled
        }
      }
    }
  }
}

fragment mediaListEntry on MediaList {
  id
  score
  notes
  customLists
  advancedScores
  progress
  startedAt { year month day }
  updatedAt
  completedAt { year month day }
  media {
    id
    title { userPreferred romaji english native }
    synonyms
    coverImage { large medium }
    format
    status
    chapters episodes
    nextAiringEpisode { airingAt episode }
    startDate { year month day }
    endDate { year month day }
    siteUrl
  }
}'''
        variables = {'id': self.userid, 'listType': self.mediatype.upper()}
        data = self._request(query, variables)['data']['MediaListCollection']

        showlist = {}

        if not data['lists']:
            # No lists returned so no need to continue
            return showlist

        # Handle different score formats provided by Anilist
        self.scoreformat = data['user']['mediaListOptions']['scoreFormat']
        self._apply_scoreformat(self.scoreformat)

        self._set_userconfig('scoreformat_' + self.mediatype, self.scoreformat)

        user_opts = data['user']['mediaListOptions'].get(
            'animeList' if self.mediatype == 'anime' else 'mangaList') or {}
        lists_set = list(user_opts.get('customLists') or [])
        for remotelist in data.get('lists', []):
            if remotelist.get('isCustomList'):
                name = remotelist.get('name')
                if name and name not in lists_set:
                    lists_set.append(name)
        self.custom_lists = lists_set
        self.advanced_scoring = user_opts.get('advancedScoring') or [
            'Story', 'Characters', 'Visuals', 'Audio', 'Enjoyment'
        ]
        self.advanced_scoring_enabled = user_opts.get('advancedScoringEnabled', False)
        self._set_userconfig('custom_lists_' + self.mediatype, self.custom_lists)
        self._set_userconfig('advanced_scoring_' + self.mediatype, self.advanced_scoring)
        self._set_userconfig('advanced_scoring_enabled_' + self.mediatype, self.advanced_scoring_enabled)

        self._emit_signal('userconfig_changed')

        for remotelist in data['lists']:
            my_status = remotelist['status']

            if my_status not in self.media_info()['statuses']:
                continue
            if remotelist['isCustomList']:
                continue  # Standard status entries processed below
            for item in remotelist['entries']:
                show = utils.show()
                media = item['media']
                showid = media['id']
                showdata = {
                    'my_id': item['id'],
                    'id': showid,
                    'title': media['title']['userPreferred'],
                    'aliases': self._get_aliases(media),
                    'type': self._translate_type(media['format']),
                    'status': self._translate_status(media['status']),
                    'my_progress': self._c(item['progress']),
                    'my_status': my_status,
                    'my_score': self._c(item['score']),
                    'my_notes': item.get('notes') or '',
                    'my_custom_lists': item.get('customLists') or {},
                    'my_advanced_scores': item.get('advancedScores') or {},
                    'total': self._c(media[self.total_str]),
                    'image': media['coverImage']['large'],
                    'image_thumb': media['coverImage']['medium'],
                    'url': media['siteUrl'],
                    'start_date': self._dict2date(media['startDate']),
                    'end_date': self._dict2date(media['endDate']),
                    'my_start_date': self._dict2date(item['startedAt']),
                    'my_finish_date': self._dict2date(item['completedAt']),
                    'my_last_update': self._int2datetime(item['updatedAt']),
                }
                if media['nextAiringEpisode']:
                    showdata['next_ep_number'] = media['nextAiringEpisode']['episode']
                    showdata['next_ep_time'] = self._int2date(
                        media['nextAiringEpisode']['airingAt'])
                for k, v in showdata.items():
                    if v is not None:
                        show[k] = v
                showlist[showid] = show

        # Record memberships in custom lists
        for remotelist in data['lists']:
            if remotelist.get('isCustomList'):
                list_name = remotelist.get('name')
                for item in remotelist.get('entries', []):
                    showid = item['media']['id']
                    if showid in showlist and list_name:
                        if not isinstance(showlist[showid].get('my_custom_lists'), dict):
                            showlist[showid]['my_custom_lists'] = {}
                        showlist[showid]['my_custom_lists'][list_name] = True

        return showlist

    args_SaveMediaListEntry = {
        'id': 'Int',                         # The list entry id, required for updating
        'mediaId': 'Int',                    # The id of the media the entry is of
        'status': 'MediaListStatus',         # The watching/reading status
        'scoreRaw': 'Int',                   # The score of the media in 100 point
        'score': 'Float',                    # Score in user format
        # The amount of episodes/chapters consumed by the user
        'progress': 'Int',
        'startedAt': 'FuzzyDateInput',       # When the entry was started by the user
        'completedAt': 'FuzzyDateInput',     # When the entry was completed by the user
        'notes': 'String',
        'customLists': '[String]',
        'advancedScores': '[Float]',
    }

    def _update_entry(self, item):
        """
        New entries will lack a list entry id, while updates will include one.
        In the case of a new entry, we want to record the new id. In the case of an update, we want to record the new updated date.
        """
        values = {'mediaId': item['id']}
        if 'my_id' in item and item['my_id']:
            values['id'] = item['my_id']
        if 'my_progress' in item:
            values['progress'] = item['my_progress']
        if 'my_status' in item:
            values['status'] = item['my_status']
        if 'my_score' in item:
            values['scoreRaw'] = self._score2raw(item['my_score'])
        if 'my_start_date' in item:
            values['startedAt'] = self._date2dict(item['my_start_date'])
        if 'my_finish_date' in item:
            values['completedAt'] = self._date2dict(item['my_finish_date'])

        if 'my_notes' in item:
            values['notes'] = item['my_notes'] or ''
        elif 'notes' in item:
            values['notes'] = item['notes'] or ''

        if 'my_custom_lists' in item:
            raw_lists = item['my_custom_lists']
            if isinstance(raw_lists, dict):
                values['customLists'] = [k for k, v in raw_lists.items() if v]
            elif isinstance(raw_lists, (list, tuple, set)):
                values['customLists'] = list(raw_lists)
            elif isinstance(raw_lists, str):
                values['customLists'] = [x.strip() for x in raw_lists.split(',') if x.strip()]
        elif 'customLists' in item:
            values['customLists'] = item['customLists']

        if 'my_advanced_scores' in item:
            adv = item['my_advanced_scores']
            if isinstance(adv, dict):
                cats = getattr(self, 'advanced_scoring', None) or [
                    'Story', 'Characters', 'Visuals', 'Audio', 'Enjoyment'
                ]
                values['advancedScores'] = [float(adv.get(c, 0.0) or 0.0) for c in cats]
            elif isinstance(adv, (list, tuple)):
                values['advancedScores'] = [float(x or 0.0) for x in adv]
        elif 'advancedScores' in item:
            values['advancedScores'] = item['advancedScores']

        vars_defn = ', '.join(
            ['${}: {}'.format(k, self.args_SaveMediaListEntry[k]) for k in values.keys()])
        subs_defn = ', '.join(['{0}: ${0}'.format(k) for k in values.keys()])
        query = 'mutation ({0}) {{ SaveMediaListEntry({1}) {{id updatedAt notes customLists advancedScores score}} }}'.format(
            vars_defn, subs_defn)

        data = self._request(query, values)['data']
        return data['SaveMediaListEntry']

    def add_show(self, item):
        self.check_credentials()
        self.msg.info("Adding item %s..." % item['title'])
        return self._update_entry(item)['id']

    def update_show(self, item):
        self.check_credentials()
        self.msg.info("Updating item %s..." % item['title'])
        return self._int2datetime(self._update_entry(item)['updatedAt'])

    def delete_show(self, item):
        self.check_credentials()
        self.msg.info("Deleting item %s..." % item['title'])
        query = 'mutation ($id: Int) {DeleteMediaListEntry(id: $id){deleted} }'
        variables = {'id': item['my_id']}
        self._request(query, variables)

    def search(self, criteria, method):
        self.check_credentials()
        self.msg.info("Searching for {}...".format(criteria))

        if method == utils.SearchMethod.KW:
            query = "query ($query: String, $type: MediaType) { Page { media(search: $query, type: $type) {"
            variables = {'query': str(criteria)}
        elif method == utils.SearchMethod.SEASON:
            season, seasonYear = criteria

            query = "query ($season: MediaSeason, $seasonYear: Int, $type: MediaType) { Page { media(season: $season, seasonYear: $seasonYear, type: $type) {"
            variables = {
                'season': self.season_translate[season], 'seasonYear': seasonYear}

        query += '''
      id
      title { userPreferred romaji english native }
      coverImage { medium large }
      format
      averageScore
      meanScore
      chapters episodes
      status
      startDate { year month day }
      endDate { year month day }
      siteUrl
      description
      genres
      synonyms
      studios(sort: NAME, isMain: true) { nodes { name } }
      seasonYear
      season
    }
  }
}'''
        variables['type'] = self.mediatype.upper()
        data = self._request(query, variables)['data']['Page']['media']

        infolist = []
        for media in data:
            infolist.append(self._parse_info(media))

        self._emit_signal('show_info_changed', infolist)
        return infolist

    def request_info(self, itemlist):
        self.check_credentials()
        infolist = []

        query = '''query ($id: Int!, $type: MediaType) {
  Media(id: $id, type: $type) {
      id
      title { userPreferred romaji english native }
      coverImage { medium large }
      format
      averageScore
      meanScore
      chapters episodes
      status
      startDate { year month day }
      endDate { year month day }
      siteUrl
      description
      genres
      synonyms
      studios(sort: NAME, isMain: true) { nodes { name } }
      seasonYear
      season
  }
}'''

        for show in itemlist:
            variables = {'id': show['id'], 'type': self.mediatype.upper()}
            data = self._request(query, variables)['data']['Media']
            infolist.append(self._parse_info(data))

        self._emit_signal('show_info_changed', infolist)
        return infolist

    def media_info(self):
        """Return information about the currently selected mediatype."""
        info = self.mediatypes[self.mediatype]
        info['can_notes'] = True
        info['can_custom_lists'] = True
        info['can_advanced_scores'] = True
        info['custom_lists'] = getattr(self, 'custom_lists', None) or self._get_userconfig('custom_lists_' + self.mediatype) or []
        info['advanced_scoring'] = getattr(self, 'advanced_scoring', None) or self._get_userconfig('advanced_scoring_' + self.mediatype) or [
            'Story', 'Characters', 'Visuals', 'Audio', 'Enjoyment'
        ]
        info['advanced_scoring_enabled'] = getattr(self, 'advanced_scoring_enabled', None)
        if info['advanced_scoring_enabled'] is None:
            info['advanced_scoring_enabled'] = self._get_userconfig('advanced_scoring_enabled_' + self.mediatype) or False
        return info

    def _parse_info(self, item):
        info = utils.show()
        showid = item['id']
        type_ = self._translate_type(item['format'])
        status = self._translate_status(item['status'])
        season = self.rev_season_translate.get(item.get('season'))
        if season and 'seasonYear' in item:
            season_and_year = f"{season!s} {item['seasonYear']}"
        elif 'seasonYear' in item:
            season_and_year = item['seasonYear']
        else:
            season_and_year = None

        info.update({
            'id': showid,
            'title': item['title']['userPreferred'],
            'total': self._c(item[self.total_str]),
            'aliases': self._get_aliases(item),
            'type': type_,
            'status': status,
            'image': item['coverImage']['large'],
            'image_thumb': item['coverImage']['medium'],
            'url': item['siteUrl'],
            'start_date': self._dict2date(item.get('startDate')),
            'end_date': self._dict2date(item.get('endDate')),
            'extra': [
                ('English',         item['title'].get('english')),
                ('Romaji',          item['title'].get('romaji')),
                ('Japanese',        item['title'].get('native')),
                ('Synonyms',        item.get('synonyms')),
                ('Season',          season_and_year),
                ('Genres',          item.get('genres')),
                ('Studios',         [s['name'] for s in item['studios']['nodes']]),
                ('Synopsis',        item.get('description')),
                ('Type',            type_),
                ('Average score',   item.get('averageScore')),
                ('Mean score',      item.get('meanScore')),
                ('Status',          status),
            ]
        })
        return info

    def _apply_scoreformat(self, fmt):
        media = self.media_info()
        (media['score_max'], media['score_step']) = self.score_types[fmt]

    def _get_aliases(self, item):
        title = item.get('title') or {}
        raw_aliases = []
        if isinstance(title, dict):
            for k in ('romaji', 'english', 'native'):
                val = title.get(k)
                if val and isinstance(val, str):
                    raw_aliases.append(val.strip())
        elif isinstance(title, str):
            raw_aliases.append(title.strip())

        synonyms = item.get('synonyms') or []
        if isinstance(synonyms, list):
            for s in synonyms:
                if s and isinstance(s, str):
                    raw_aliases.append(s.strip())

        # Deduplicate while preserving order
        aliases = []
        for a in raw_aliases:
            if a and a not in aliases:
                aliases.append(a)

        return aliases

    def _translate_type(self, orig_type):
        return self.type_translate.get(orig_type, utils.Type.UNKNOWN)

    def _translate_status(self, orig_status):
        return self.status_translate.get(orig_status, utils.Status.UNKNOWN)

    def _dict2date(self, item):
        if not item:
            return None
        try:
            return datetime.datetime(item['year'], item['month'], item['day'])
        except (TypeError, ValueError):
            return None

    def _date2dict(self, date):
        if not date:
            return {}
        try:
            return {'year': date.year, 'month': date.month, 'day': date.day}
        except (TypeError, ValueError):
            return {}

    def _score2raw(self, score):
        if score == 0:
            return 0

        if self.scoreformat in ['POINT_10', 'POINT_10_DECIMAL']:
            return int(score*10)
        elif self.scoreformat == 'POINT_5':
            return int(score*20)
        elif self.scoreformat == 'POINT_3':
            return int(score*25)
        else:
            return score

    def _int2date(self, item):
        if not item:
            return None
        try:
            return datetime.datetime.utcfromtimestamp(item)
        except ValueError:
            return None

    def _int2datetime(self, item):
        if not item:
            return None
        try:
            return datetime.datetime.fromtimestamp(item, tz=datetime.timezone.utc)
        except ValueError:
            return None

    def _c(self, s):
        if s is None:
            return 0
        else:
            return s
