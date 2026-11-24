# -*- coding: utf-8 -*-
# 小蜜蜂影院
import html
import json
import re
import sys
from urllib.parse import quote, urlencode

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    CATEGORIES = (
        ('电视剧', '1'),
        ('电影', '2'),
        ('动漫', '3'),
        ('综艺', '4'),
        ('短剧', '5'),
    )

    TYPE_FILTERS = {
        '1': (
            ('剧情', '7'), ('古装', '9'), ('战争', '10'), ('谍战', '11'),
            ('爱情', '12'), ('罪案', '13'), ('悬疑', '14'), ('家庭', '15'),
            ('军旅', '16'), ('喜剧', '17'), ('都市', '18'), ('武侠', '19'),
            ('言情', '20'), ('偶像', '21'), ('青春', '22'), ('农村', '23'),
            ('穿越', '24'), ('奇幻', '25'), ('历史', '26'), ('年代', '27'),
            ('科幻', '28'), ('生活', '29'), ('励志', '31'), ('婚姻', '32'),
            ('警匪', '33'), ('犯罪', '34'), ('推理', '35'), ('商战', '36'),
            ('宫廷', '37'), ('仙侠', '38'), ('神话', '39'), ('动作', '40'),
            ('复仇', '41'), ('惊悚', '42'),
        ),
        '2': (
            ('动作', '43'), ('喜剧', '44'), ('爱情', '45'), ('科幻', '46'),
            ('恐怖', '47'), ('剧情', '48'), ('战争', '49'), ('犯罪', '50'),
            ('惊悚', '51'), ('冒险', '52'), ('悬疑', '53'), ('动画', '54'),
            ('武侠', '55'), ('古装', '56'), ('历史', '57'), ('传记', '58'),
            ('纪录片', '59'),
        ),
        '3': (
            ('热血', '60'), ('恋爱', '61'), ('校园', '62'), ('搞笑', '63'),
            ('机甲', '64'), ('神魔', '65'), ('竞技', '66'), ('冒险', '67'),
            ('治愈', '68'), ('百合', '69'), ('萝莉', '70'), ('后宫', '71'),
            ('励志', '72'), ('泡面番', '73'), ('国产动漫', '74'),
            ('日本动漫', '75'), ('欧美动漫', '76'),
        ),
        '4': (
            ('选秀', '77'), ('情感', '78'), ('访谈', '79'), ('播报', '80'),
            ('旅游', '81'), ('音乐', '82'), ('美食', '83'), ('纪实', '84'),
            ('曲艺', '85'), ('游戏', '86'), ('亲子', '87'), ('职场', '88'),
            ('脱口秀', '89'), ('真人秀', '90'), ('晚会', '91'),
        ),
    }

    AREAS = (
        '大陆', '香港', '台湾', '韩国', '日本', '美国', '泰国',
        '法国', '英国', '德国', '印度', '其他',
    )

    YEARS = (
        ('2026', '2026'), ('2025', '2025'), ('2024', '2024'),
        ('2023', '2023'), ('2022', '2022'), ('2021', '2021'),
        ('2020', '2020'), ('2019', '2019'), ('2018', '2018'),
        ('其他', '-1'),
    )

    SORTS = (
        ('热度', 'hot'),
        ('最新', 'time'),
        ('评分', 'score'),
    )

    def init(self, extend=""):
        self.host = 'https://www.xmfyy.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host + '/',
        }

    def getName(self):
        return '小蜜蜂影院'

    def isVideoFormat(self, url):
        return '.m3u8' in (url or '') or '.mp4' in (url or '')

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeContent(self, filter):
        result = {
            'class': [
                {'type_name': name, 'type_id': tid}
                for name, tid in self.CATEGORIES
            ],
            'filters': self.get_filters(),
            'list': [],
        }
        try:
            html_text = self.fetch(self.host + '/', headers=self.headers).text
            result['list'] = self.get_vod_list(html_text)
        except Exception as e:
            print(f'homeContent 错误: {e}')
        return result

    def homeVideoContent(self):
        try:
            html_text = self.fetch(self.host + '/', headers=self.headers).text
            return self.get_vod_list(html_text)
        except:
            return []

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg))
        except (TypeError, ValueError):
            page = 1

        result = {
            'list': [],
            'page': page,
            'pagecount': 1,
            'limit': 12,
            'total': 0,
        }
        try:
            extend = extend or {}
            params = {
                'channel': str(tid),
                'area': extend.get('area', ''),
                'year': extend.get('year', ''),
                'sort': extend.get('sort', 'hot'),
                'page': str(page),
            }
            if extend.get('type'):
                params['type'] = str(extend.get('type'))
            url = self.host + '/filter?' + urlencode(params)
            html_text = self.fetch(url, headers=self.headers).text
            result['list'] = self.get_vod_list(html_text)
            result['pagecount'] = self.get_pagecount(html_text)
            result['total'] = result['pagecount'] * 12
        except Exception as e:
            print(f'categoryContent 错误: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        try:
            page = max(1, int(pg))
        except (TypeError, ValueError):
            page = 1

        result = {
            'list': [],
            'page': page,
            'pagecount': 1,
            'limit': 20,
            'total': 0,
        }
        try:
            params = {
                'keyword': key,
                'field': 'all',
                'sort': 'hits',
                'page': str(page),
            }
            url = self.host + '/search?' + urlencode(params)
            html_text = self.fetch(url, headers=self.headers).text
            result['list'] = self.get_search_list(html_text)
            result['pagecount'] = self.get_pagecount(html_text)
            result['total'] = result['pagecount'] * 20
        except Exception as e:
            print(f'searchContent 错误: {e}')
        return result

    def detailContent(self, ids):
        result = {'list': []}
        try:
            vod_id = self.get_vod_id(ids[0])
            if not vod_id:
                return result

            url = f'{self.host}/detail/{vod_id}.html'
            html_text = self.fetch(url, headers=self.headers).text

            vod = {
                'vod_id': vod_id,
                'vod_name': self.get_first(
                    html_text,
                    r'<h1[^>]*class="detail-title"[^>]*>(.*?)</h1>'
                ),
                'vod_pic': self.get_first(
                    html_text,
                    r'<div[^>]*class="detail-poster-wrapper"[^>]*>.*?'
                    r'<img[^>]+src="([^"]+)"',
                    re.DOTALL
                ),
                'vod_actor': self.get_meta(html_text, '主演'),
                'vod_director': self.get_meta(html_text, '导演'),
                'vod_area': self.get_meta(html_text, '地区'),
                'vod_year': self.get_meta(html_text, '年份'),
                'vod_remarks': self.get_meta(html_text, '备注'),
                'vod_content': self.get_first(
                    html_text,
                    r'<div[^>]*class="synopsis-content"[^>]*>(.*?)</div>',
                    re.DOTALL
                ),
                'type_name': ','.join(re.findall(
                    r'<span[^>]*class="tag-pill"[^>]*>(.*?)</span>',
                    html_text,
                    re.DOTALL
                )),
            }
            vod['vod_name'] = self.clean_text(vod['vod_name'])
            vod['vod_content'] = self.clean_text(vod['vod_content'])
            vod['type_name'] = self.clean_text(vod['type_name'])

            play_from, play_url = self.get_play_groups(html_text)
            vod['vod_play_from'] = '$$$'.join(play_from)
            vod['vod_play_url'] = '$$$'.join(play_url)
            result['list'].append(vod)
        except Exception as e:
            print(f'detailContent 错误: {e}')
        return result

    def playerContent(self, flag, id, vipFlags):
        play_page = ''
        try:
            play_page = id if str(id).startswith('http') else self.host + str(id)
            match = re.search(r'/vodplay/(\d+)-([^/]+)-(\d+)\.html', play_page)
            if not match:
                return {'parse': 0, 'url': play_page, 'header': self.headers}

            params = {
                'vodId': match.group(1),
                'playFrom': match.group(2),
                'index': match.group(3),
            }
            api_url = self.host + '/api/play-url?' + urlencode(params)
            headers = dict(self.headers)
            headers['Referer'] = play_page
            data = self.fetch(api_url, headers=headers).json()

            play_url = data.get('url') or ''
            if int(data.get('code') or 0) != 200 or not play_url:
                raise ValueError(data.get('msg') or '播放地址解析失败')

            response_headers = data.get('headers')
            if not isinstance(response_headers, dict):
                response_headers = {}
            response_headers.setdefault('User-Agent', self.headers['User-Agent'])
            response_headers.setdefault('Referer', play_page)

            return {
                'parse': 1 if data.get('mode') == 'iframe' else 0,
                'url': play_url,
                'header': response_headers,
            }
        except Exception as e:
            print(f'playerContent 错误: {e}')
            if play_page:
                return {
                    'parse': 1,
                    'url': play_page,
                    'header': self.headers,
                }
            return {'parse': 0, 'url': id or '', 'header': self.headers}

    def get_filters(self):
        result = {}
        for _, tid in self.CATEGORIES:
            filters = []
            type_values = [{'n': '全部', 'v': ''}]
            type_values.extend(
                {'n': name, 'v': value}
                for name, value in self.TYPE_FILTERS.get(str(tid), ())
            )
            if len(type_values) > 1:
                filters.append({
                    'key': 'type',
                    'name': '类型',
                    'value': type_values,
                })

            area_values = [{'n': '全部', 'v': ''}]
            area_values.extend({'n': name, 'v': name} for name in self.AREAS)
            filters.append({
                'key': 'area',
                'name': '地区',
                'value': area_values,
            })

            year_values = [{'n': '全部', 'v': ''}]
            year_values.extend(
                {'n': name, 'v': value}
                for name, value in self.YEARS
            )
            filters.append({
                'key': 'year',
                'name': '年份',
                'value': year_values,
            })

            filters.append({
                'key': 'sort',
                'name': '排序',
                'value': [
                    {'n': name, 'v': value}
                    for name, value in self.SORTS
                ],
                'init': 'hot',
            })
            result[str(tid)] = filters
        return result

    def get_vod_list(self, html_text):
        videos = []
        seen = set()
        for match in re.finditer(
            r'<a\s+href="/detail/(\d+)\.html"[^>]*>(.*?)</a>',
            html_text,
            re.DOTALL
        ):
            vod_id, body = match.group(1), match.group(2)
            if vod_id in seen:
                continue

            title = self.get_first(
                body,
                r'<p[^>]*class="vod-title[^"]*"[^>]*>(.*?)</p>',
                re.DOTALL
            )
            if not title:
                continue

            pic = self.get_first(
                body,
                r'<img[^>]+src="([^"]+)"',
                re.DOTALL
            )
            remark = self.get_first(
                body,
                r'<p[^>]*class="vod-subtitle[^"]*"[^>]*>(.*?)</p>',
                re.DOTALL
            )
            seen.add(vod_id)
            videos.append({
                'vod_id': vod_id,
                'vod_name': self.clean_text(title),
                'vod_pic': html.unescape(pic),
                'vod_remarks': self.clean_text(remark),
            })
        return videos

    def get_search_list(self, html_text):
        videos = []
        seen = set()
        for block in html_text.split('<div class="search-item">')[1:]:
            href = self.get_first(
                block,
                r'<a[^>]+href="/detail/(\d+)\.html"',
                re.DOTALL
            )
            if not href or href in seen:
                continue

            title = self.get_first(
                block,
                r'<a[^>]*class="search-item-title[^"]*"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            if not title:
                continue

            pic = self.get_first(
                block,
                r'<img[^>]+src="([^"]+)"',
                re.DOTALL
            )
            type_name = self.get_first(
                block,
                r'<span[^>]*class="search-item-type"[^>]*>(.*?)</span>',
                re.DOTALL
            )
            seen.add(href)
            videos.append({
                'vod_id': href,
                'vod_name': self.clean_text(title),
                'vod_pic': html.unescape(pic),
                'vod_remarks': self.clean_text(type_name),
            })
        return videos

    def get_play_groups(self, html_text):
        source_names = {}
        for target, name in re.findall(
            r'<button[^>]*class="source-tab[^"]*"[^>]*'
            r'data-target="([^"]+)"[^>]*>(.*?)</button>',
            html_text,
            re.DOTALL
        ):
            source_names[target] = self.clean_text(name)

        panels = re.findall(
            r'<div[^>]*class="source-panel"[^>]*id="([^"]+)"[^>]*'
            r'>(.*?)(?=<div[^>]*class="source-panel"|\Z)',
            html_text,
            re.DOTALL
        )

        play_from = []
        play_url = []
        for index, (panel_id, body) in enumerate(panels):
            episodes = []
            seen = set()
            for attrs, label in re.findall(
                r'<a\b([^>]*)>(.*?)</a>',
                body,
                re.DOTALL
            ):
                if 'episode-btn' not in attrs:
                    continue
                href = self.get_first(attrs, r'href="([^"]+)"')
                if not href or href in seen:
                    continue
                seen.add(href)
                episodes.append(
                    f'{self.clean_text(label)}${self.host}{href}'
                )
            if not episodes:
                continue
            play_from.append(source_names.get(panel_id) or f'线路{index + 1}')
            play_url.append('#'.join(episodes))
        return play_from, play_url

    def get_pagecount(self, html_text):
        total = self.get_first(html_text, r'data-totalpages="(\d+)"')
        if total:
            return max(1, int(total))
        pages = re.findall(r'data-page="(\d+)"', html_text)
        return max([int(page) for page in pages] or [1])

    def get_meta(self, html_text, label):
        return self.clean_text(self.get_first(
            html_text,
            r'<span[^>]*class="meta-label"[^>]*>'
            + re.escape(label)
            + r'：?</span>\s*<span[^>]*class="meta-value"[^>]*>(.*?)</span>',
            re.DOTALL
        ))

    def get_first(self, text, pattern, flags=0):
        match = re.search(pattern, text or '', flags)
        return match.group(1).strip() if match else ''

    def get_vod_id(self, value):
        match = re.search(r'/detail/(\d+)\.html', str(value or ''))
        if match:
            return match.group(1)
        match = re.search(r'^\s*(\d+)\s*$', str(value or ''))
        return match.group(1) if match else ''

    def clean_text(self, text):
        text = re.sub(r'<[^>]+>', '', text or '')
        return re.sub(r'\s+', ' ', html.unescape(text)).strip()

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass
