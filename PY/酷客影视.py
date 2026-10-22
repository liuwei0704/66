# -*- coding: utf-8 -*-
import re
import sys
import json
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        pass

    def getName(self):
        return "酷客影院"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    host = 'http://www.dy2055.com'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def _normalize_url(self, url):
        if not url:
            return ''
        url = str(url).strip()
        if url.startswith('//'):
            return 'http:' + url
        if url.startswith('/'):
            return self.host + url
        if not url.startswith('http'):
            return 'http://' + url
        return url

    def _extract_video_basic(self, item, html_segment=None):
        """从列表项提取视频基本信息 - 使用正则作为后备"""
        try:
            # 获取链接
            link = item('a').attr('href')
            if not link:
                return None
            link = self._normalize_url(link)
            
            # 标题
            title = item('a').attr('title')
            if not title:
                title = item('h4 a').text()
            if not title:
                title = item('a').text()
            title = title.strip() or '未知标题'
            
            # 图片 - 方法1：PyQuery
            img = ''
            img_elem = item('img')
            if img_elem:
                img = img_elem.attr('data-original')
                if not img:
                    img = img_elem.attr('src')
            
            # 图片 - 方法2：如果PyQuery没拿到，用正则从HTML提取
            if not img and html_segment:
                # 匹配 data-original="xxx"
                match = re.search(r'data-original="([^"]+)"', html_segment)
                if match:
                    img = match.group(1)
                else:
                    # 匹配 src="xxx"
                    match = re.search(r'src="([^"]+)"', html_segment)
                    if match:
                        img = match.group(1)
            
            # 图片 - 方法3：从style提取背景图
            if not img:
                style = item('a').attr('style')
                if style:
                    match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
                    if match:
                        img = match.group(1)
            
            if img:
                img = self._normalize_url(img)
            
            remarks = item('.pic-text').text().strip()
            if not remarks:
                remarks = item('.text-right').text().strip()
            
            return {
                'vod_id': link,
                'vod_name': title,
                'vod_pic': img or '',
                'vod_remarks': remarks or '',
                'vod_year': ''
            }
        except:
            return None

    def getpq(self, text):
        try:
            return pq(text)
        except:
            try:
                return pq(text.encode('utf-8'))
            except:
                return pq('')

    def homeContent(self, filter):
        try:
            response = self.fetch(self.host, headers=self.headers)
            if not response or not response.text:
                return self._get_default_home()
            
            html_content = response.text
            data = self.getpq(html_content)
            classes = []
            
            nav = data('.stui-header__menu li')
            for item in nav.items():
                link = item('a').attr('href')
                name = item('a').text().strip()
                if link and name and '/list/' in link:
                    classes.append({
                        'type_name': name,
                        'type_id': self._normalize_url(link)
                    })
            
            videos = []
            items = data('.stui-vodlist.clearfix li')
            
            for item in items.items():
                item_html = item.__str__() if hasattr(item, '__str__') else None
                v = self._extract_video_basic(item, item_html)
                if v:
                    videos.append(v)
                    if len(videos) >= 30:
                        break
            
            return {'class': classes, 'list': videos}
        except:
            return self._get_default_home()

    def _get_default_home(self):
        classes = [
            {'type_name': '电影', 'type_id': self.host + '/list/1.html'},
            {'type_name': '电视剧', 'type_id': self.host + '/list/2.html'},
            {'type_name': '动漫', 'type_id': self.host + '/list/3.html'},
            {'type_name': '综艺', 'type_id': self.host + '/list/4.html'},
            {'type_name': '伦理', 'type_id': self.host + '/list/67.html'},
        ]
        return {'class': classes, 'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            if pg == '1':
                url = tid
            else:
                if tid.endswith('.html'):
                    base = tid.replace('.html', '')
                    url = base + '_' + pg + '.html'
                else:
                    url = tid + '?page=' + pg
            
            response = self.fetch(url, headers=self.headers)
            if not response or not response.text:
                return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 30, 'total': 0}
            
            html_content = response.text
            data = self.getpq(html_content)
            videos = []
            items = data('.stui-vodlist.clearfix li')
            
            for item in items.items():
                item_html = item.__str__() if hasattr(item, '__str__') else None
                v = self._extract_video_basic(item, item_html)
                if v:
                    videos.append(v)
            
            pagecount = 825
            page_info = data('.stui-page .num').text()
            if page_info:
                match = re.search(r'/(\d+)', page_info)
                if match:
                    pagecount = int(match.group(1))
            
            return {
                'list': videos,
                'page': int(pg),
                'pagecount': pagecount,
                'limit': 30,
                'total': pagecount * 30
            }
        except:
            return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 30, 'total': 0}

    def detailContent(self, ids):
        """
        详情页：提取视频详情、多个播放线路和集数
        """
        try:
            first_id = ids if isinstance(ids, str) else next(iter(ids))
            
            response = self.fetch(first_id, headers=self.headers)
            if not response or not response.text:
                return {'list': []}
            
            data = self.getpq(response.text)
            
            # 1. 提取标题
            name = data('.stui-content__detail .title').text().strip()
            if not name:
                name = data('h1').text().strip()
            
            # 2. 提取图片
            pic = ''
            img_elem = data('.stui-content__thumb img')
            if img_elem:
                pic = img_elem.attr('data-original')
                if not pic:
                    pic = img_elem.attr('src')
            pic = self._normalize_url(pic) if pic else ''
            
            # 3. 提取简介
            content = data('.stui-content__desc').text().strip() or ''
            
            # 4. 提取详细信息
            vod_year = ''
            vod_area = ''
            vod_remarks = ''
            vod_actor = ''
            vod_director = ''
            
            detail_items = data('.stui-content__detail p, .stui-content__detail .data')
            for item in detail_items.items():
                text = item.text().strip()
                if '地区：' in text:
                    vod_area = text.replace('地区：', '').strip()
                elif '年份：' in text:
                    vod_year = text.replace('年份：', '').strip()
                elif '主演：' in text:
                    vod_actor = text.replace('主演：', '').strip()
                elif '导演：' in text:
                    vod_director = text.replace('导演：', '').strip()
                elif '更新：' in text:
                    vod_remarks = text.replace('更新：', '').strip()
            
            # 5. 提取播放线路和集数
            play_from_list = []
            play_url_list = []
            
            nav_tabs = data('.nav-tabs li')
            if nav_tabs and len(nav_tabs) > 0:
                for tab in nav_tabs.items():
                    from_name = tab.text().strip()
                    if from_name and from_name not in ['', '播放地址']:
                        play_from_list.append(from_name)
                
                tab_panes = data('.tab-pane')
                for pane in tab_panes.items():
                    play_links = []
                    links = pane('.stui-content__playlist a')
                    for link in links.items():
                        episode_name = link.text().strip()
                        episode_url = link.attr('href')
                        if episode_url and episode_name and episode_name != '观看更多视频':
                            full_url = self._normalize_url(episode_url)
                            play_links.append(f"{episode_name}${full_url}")
                    
                    if play_links:
                        play_url_list.append('#'.join(play_links))
            
            if not play_from_list or not play_url_list:
                play_links = []
                links = data('.stui-content__playlist a')
                for link in links.items():
                    episode_name = link.text().strip()
                    episode_url = link.attr('href')
                    if episode_url and episode_name and episode_name != '观看更多视频':
                        full_url = self._normalize_url(episode_url)
                        play_links.append(f"{episode_name}${full_url}")
                
                if play_links:
                    play_from_list = ['默认线路']
                    play_url_list = ['#'.join(play_links)]
            
            vod = {
                'vod_id': first_id,
                'vod_name': name or '未知',
                'vod_pic': pic,
                'vod_content': content,
                'vod_year': vod_year,
                'vod_area': vod_area,
                'vod_remarks': vod_remarks,
                'vod_actor': vod_actor,
                'vod_director': vod_director,
                'vod_play_from': '$$$'.join(play_from_list) if play_from_list else '酷客云',
                'vod_play_url': '$$$'.join(play_url_list) if play_url_list else f'播放${first_id}'
            }
            
            return {'list': [vod]}
            
        except Exception as e:
            return {'list': []}

    # 搜索功能 - 直接返回空列表，避免报错
    def searchContent(self, key, quick, pg="1"):
        return {'list': [], 'page': int(pg)}

    def playerContent(self, flag, id, vipFlags):
        return {'parse': 1, 'url': id, 'header': self.headers}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass
