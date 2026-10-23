# coding=utf-8
# A123TV 爬虫 - TVBox/FongMi
# 站点: https://a123tv.com
# 类型: 影视站 (HTML解析)
# 特性: 多线路、多分类、分页

import sys
import os
import re
import json
import urllib.parse
from base.spider import Spider
from bs4 import BeautifulSoup

class Spider(Spider):
    def getName(self):
        return "A123TV"
    
    def __init__(self):
        """初始化分类、筛选和基础配置"""
        self.classes = [
            {"type_name": "电影", "type_id": "10"},
            {"type_name": "连续剧", "type_id": "11"},
            {"type_name": "综艺", "type_id": "12"},
            {"type_name": "动漫", "type_id": "13"},
            {"type_name": "福利", "type_id": "15"},
        ]
        self.filters = {
            "10": [],
            "11": [],
            "12": [],
            "13": [],
            "15": [],
        }
        # 在 __init__ 中初始化 host 和 headers，避免依赖 init()
        self.host = "https://a123tv.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    def init(self, extend=""):
        self.host = "https://a123tv.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    
    def _fetch_html(self, url):
        """获取页面HTML，返回BeautifulSoup对象"""
        try:
            rsp = self.fetch(url, headers=self.headers)
            # spider_runner 环境下 fetch 可能返回字符串或 Response 对象
            if isinstance(rsp, str):
                html = rsp
            elif hasattr(rsp, 'text'):
                html = rsp.text
            elif hasattr(rsp, 'content'):
                html = rsp.content.decode('utf-8', errors='ignore')
            elif isinstance(rsp, dict) and 'body' in rsp:
                html = rsp['body']
            else:
                html = str(rsp)
            return BeautifulSoup(html, 'html.parser')
        except Exception as e:
            print(f"[A123TV] fetch_html error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def homeContent(self, filter=False):
        """返回分类列表"""
        return {"class": self.classes}
    
    def getHomeContent(self):
        """兼容别名"""
        return self.homeContent(False)
    
    def homeVideoContent(self):
        """首页推荐视频"""
        try:
            root = self._fetch_html(self.host)
            if not root:
                return {"list": []}
            
            videos = []
            items = root.select('.w4-item-wrap')
            
            for item in items[:30]:
                try:
                    a = item.find('a', class_='w4-item')
                    if not a:
                        continue
                    
                    href = a.get('href', '')
                    if not href:
                        continue
                    vod_id = href if href.startswith('http') else self.host + href
                    
                    title_div = a.find('div', class_='t')
                    vod_name = ""
                    if title_div:
                        vod_name = title_div.get('title', '') or title_div.text.strip()
                    if not vod_name:
                        vod_name = a.get('title', '')
                    
                    vod_pic = ""
                    img = a.find('img')
                    if img:
                        vod_pic = img.get('data-src') or img.get('src', '')
                        if vod_pic and vod_pic.startswith('//'):
                            vod_pic = 'https:' + vod_pic
                        elif vod_pic and not vod_pic.startswith('http'):
                            vod_pic = self.host + vod_pic if vod_pic.startswith('/') else vod_pic
                    
                    vod_remarks = ""
                    r_elem = a.find('div', class_='r')
                    if r_elem:
                        vod_remarks = r_elem.text.strip()
                    
                    s_elem = a.find('div', class_='s')
                    if s_elem:
                        lines_text = s_elem.text.strip()
                        if vod_remarks:
                            vod_remarks += " | " + lines_text
                        else:
                            vod_remarks = lines_text
                    
                    i_elem = a.find('div', class_='i')
                    if i_elem:
                        info_text = i_elem.text.strip()
                        if vod_remarks:
                            vod_remarks += " | " + info_text
                        else:
                            vod_remarks = info_text
                    
                    if vod_name and vod_id:
                        videos.append({
                            "vod_id": vod_id,
                            "vod_name": vod_name,
                            "vod_pic": vod_pic,
                            "vod_remarks": vod_remarks
                        })
                except Exception as e:
                    print(f"[A123TV] homeVideoContent item error: {e}")
                    continue
            
            return {"list": videos}
        except Exception as e:
            print(f"[A123TV] homeVideoContent error: {e}")
            import traceback
            traceback.print_exc()
            return {"list": []}
    
    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        """分类列表"""
        try:
            pg = int(pg) if pg else 1
            
            if pg > 1:
                url = f"{self.host}/t/{tid}/p{pg}.html"
            else:
                url = f"{self.host}/t/{tid}.html"
            
            print(f"[A123TV] categoryContent URL: {url}")
            root = self._fetch_html(url)
            if not root:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}
            
            videos = []
            items = root.select('.w4-item-wrap')
            
            for item in items:
                try:
                    a = item.find('a', class_='w4-item')
                    if not a:
                        continue
                    
                    href = a.get('href', '')
                    if not href:
                        continue
                    vod_id = href if href.startswith('http') else self.host + href
                    
                    title_div = a.find('div', class_='t')
                    vod_name = ""
                    if title_div:
                        vod_name = title_div.get('title', '') or title_div.text.strip()
                    if not vod_name:
                        vod_name = a.get('title', '')
                    if not vod_name:
                        continue
                    
                    vod_pic = ""
                    img = a.find('img')
                    if img:
                        vod_pic = img.get('data-src') or img.get('src', '')
                        if vod_pic and vod_pic.startswith('//'):
                            vod_pic = 'https:' + vod_pic
                        elif vod_pic and not vod_pic.startswith('http'):
                            vod_pic = self.host + vod_pic if vod_pic.startswith('/') else vod_pic
                    
                    vod_remarks = ""
                    r_elem = a.find('div', class_='r')
                    if r_elem:
                        vod_remarks = r_elem.text.strip()
                    
                    s_elem = a.find('div', class_='s')
                    if s_elem:
                        lines_text = s_elem.text.strip()
                        if vod_remarks:
                            vod_remarks += " | " + lines_text
                        else:
                            vod_remarks = lines_text
                    
                    i_elem = a.find('div', class_='i')
                    if i_elem:
                        info_text = i_elem.text.strip()
                        if vod_remarks:
                            vod_remarks += " | " + info_text
                        else:
                            vod_remarks = info_text
                    
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
                except Exception as e:
                    print(f"[A123TV] categoryContent item error: {e}")
                    continue
            
            # 分页解析
            pagecount = pg
            pagination = root.find('div', class_='w4-page')
            if pagination:
                page_links = pagination.find_all('a', href=True)
                page_numbers = []
                for link in page_links:
                    href = link.get('href', '')
                    match = re.search(r'/p(\d+)\.html', href)
                    if match:
                        try:
                            page_numbers.append(int(match.group(1)))
                        except:
                            pass
                if page_numbers:
                    pagecount = max(page_numbers)
            
            print(f"[A123TV] categoryContent: pg={pg}, pagecount={pagecount}, count={len(videos)}")
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": 30,
                "total": len(videos) * pagecount
            }
        except Exception as e:
            print(f"[A123TV] categoryContent error: {e}")
            import traceback
            traceback.print_exc()
            return {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}
    
    def detailContent(self, ids):
        """详情页"""
        try:
            vod_id = ids[0] if ids else ""
            if not vod_id:
                return {"list": []}
            
            if not vod_id.startswith('http'):
                url = self.host + vod_id if vod_id.startswith('/') else self.host + '/' + vod_id
            else:
                url = vod_id
            
            print(f"[A123TV] detailContent URL: {url}")
            root = self._fetch_html(url)
            if not root:
                return {"list": []}
            
            # 视频标题
            vod_name = ""
            h1 = root.find('h1')
            if h1:
                vod_name = h1.text.strip()
            if not vod_name:
                title_tag = root.find('title')
                if title_tag:
                    vod_name = title_tag.text.strip().replace(' - A123TV', '').replace('《', '').replace('》', '')
            
            # 封面图
            vod_pic = ""
            og_image = root.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                vod_pic = og_image['content']
                if vod_pic.startswith('//'):
                    vod_pic = 'https:' + vod_pic
            
            if not vod_pic:
                cover_img = root.find('img', class_=re.compile(r'cover|poster|thumb'))
                if cover_img:
                    vod_pic = cover_img.get('data-src') or cover_img.get('src', '')
                    if vod_pic and vod_pic.startswith('//'):
                        vod_pic = 'https:' + vod_pic
            
            # 描述
            vod_content = ""
            meta_desc = root.find('meta', {'name': 'description'})
            if meta_desc:
                desc = meta_desc.get('content', '')
                plot_match = re.search(r'剧情：(.+)', desc)
                if plot_match:
                    vod_content = plot_match.group(1)
                else:
                    vod_content = desc
            
            # 从meta提取信息
            vod_year = ""
            vod_actor = ""
            vod_director = ""
            vod_area = ""
            
            if meta_desc:
                desc = meta_desc.get('content', '')
                year_match = re.search(r'(\d{4})年', desc)
                if year_match:
                    vod_year = year_match.group(1)
                actor_match = re.search(r'演员：(.+?)。', desc)
                if actor_match:
                    vod_actor = actor_match.group(1)
                director_match = re.search(r'导演：(.+?)。', desc)
                if director_match:
                    vod_director = director_match.group(1)
                area_match = re.search(r'地区：(.+?)。', desc)
                if area_match:
                    vod_area = area_match.group(1)
            
            # 解析 var pp 数据
            play_from_list = []
            play_url_list = []
            seen_urls = set()
            seen_names = set()  # 记录已使用的线路名
            
            scripts = root.find_all('script')
            pp_data = None
            
            for script in scripts:
                if script.string and 'var pp=' in script.string:
                    match = re.search(r'var pp=(\{.*?\});', script.string, re.DOTALL)
                    if match:
                        try:
                            pp_data = json.loads(match.group(1))
                            break
                        except:
                            try:
                                json_str = match.group(1)
                                json_str = re.sub(r',\s*}', '}', json_str)
                                json_str = re.sub(r',\s*]', ']', json_str)
                                pp_data = json.loads(json_str)
                                break
                            except:
                                pass
            
            if pp_data and 'la' in pp_data:
                for line in pp_data['la']:
                    if len(line) >= 5:
                        line_name = line[1]
                        m3u8_url = line[4]
                        
                        if not m3u8_url:
                            continue
                        
                        # 去重：同一个线路名只保留一次
                        if line_name in seen_names:
                            continue
                        
                        # 去重：同一个 m3u8 URL 只保留一次
                        if m3u8_url in seen_urls:
                            continue
                        
                        seen_names.add(line_name)
                        seen_urls.add(m3u8_url)
                        
                        episodes = [f"正片${m3u8_url}"]
                        play_from_list.append(line_name)
                        play_url_list.append("#".join(episodes))
            
            # 如果没从pp解析到，尝试从播放器data-src提取
            if not play_from_list:
                player_div = root.find('div', id='awp1')
                if player_div:
                    m3u8_url = player_div.get('data-src', '')
                    if m3u8_url:
                        play_from_list.append("默认线路")
                        play_url_list.append(f"正片${m3u8_url}")
            
            # 如果还没有，尝试从视频标签提取
            if not play_from_list:
                video_tag = root.find('video')
                if video_tag:
                    video_src = video_tag.get('src') or video_tag.get('data-src', '')
                    if video_src:
                        play_from_list.append("默认线路")
                        play_url_list.append(f"正片${video_src}")
            
            # 最终兜底
            if not play_from_list:
                play_from_list.append("默认线路")
                play_url_list.append(f"第1集${url}")
            
            video = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_content": vod_content,
                "vod_year": vod_year,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_area": vod_area,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list)
            }
            
            return {"list": [video]}
        except Exception as e:
            print(f"[A123TV] detailContent error: {e}")
            import traceback
            traceback.print_exc()
            return {"list": []}
    def searchContent(self, key, quick=False, pg=1):
        """搜索"""
        try:
            encoded_key = urllib.parse.quote(key)
            pg = int(pg) if pg else 1
            
            if pg > 1:
                search_url = f"{self.host}/s/{encoded_key}/p{pg}.html"
            else:
                search_url = f"{self.host}/s/{encoded_key}.html"
            
            print(f"[A123TV] searchContent URL: {search_url}")
            root = self._fetch_html(search_url)
            if not root:
                return {"list": []}
            
            videos = []
            items = root.select('.w4-item-wrap')
            
            for item in items:
                try:
                    a = item.find('a', class_='w4-item')
                    if not a:
                        continue
                    
                    href = a.get('href', '')
                    if not href:
                        continue
                    vod_id = href if href.startswith('http') else self.host + href
                    
                    title_div = a.find('div', class_='t')
                    vod_name = ""
                    if title_div:
                        vod_name = title_div.get('title', '') or title_div.text.strip()
                    if not vod_name:
                        vod_name = a.get('title', '')
                    if not vod_name:
                        continue
                    
                    vod_pic = ""
                    img = a.find('img')
                    if img:
                        vod_pic = img.get('data-src') or img.get('src', '')
                        if vod_pic and vod_pic.startswith('//'):
                            vod_pic = 'https:' + vod_pic
                        elif vod_pic and not vod_pic.startswith('http'):
                            vod_pic = self.host + vod_pic if vod_pic.startswith('/') else vod_pic
                    
                    vod_remarks = ""
                    r_elem = a.find('div', class_='r')
                    if r_elem:
                        vod_remarks = r_elem.text.strip()
                    
                    s_elem = a.find('div', class_='s')
                    if s_elem:
                        lines_text = s_elem.text.strip()
                        if vod_remarks:
                            vod_remarks += " | " + lines_text
                        else:
                            vod_remarks = lines_text
                    
                    i_elem = a.find('div', class_='i')
                    if i_elem:
                        info_text = i_elem.text.strip()
                        if vod_remarks:
                            vod_remarks += " | " + info_text
                        else:
                            vod_remarks = info_text
                    
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
                except Exception as e:
                    print(f"[A123TV] searchContent item error: {e}")
                    continue
            
            pagecount = pg
            pagination = root.find('div', class_='w4-page')
            if pagination:
                page_links = pagination.find_all('a', href=True)
                page_numbers = []
                for link in page_links:
                    href = link.get('href', '')
                    match = re.search(r'/p(\d+)\.html', href)
                    if match:
                        try:
                            page_numbers.append(int(match.group(1)))
                        except:
                            pass
                if page_numbers:
                    pagecount = max(page_numbers)
            
            print(f"[A123TV] searchContent: found {len(videos)} results")
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": 30,
                "total": len(videos) * pagecount
            }
        except Exception as e:
            print(f"[A123TV] searchContent error: {e}")
            import traceback
            traceback.print_exc()
            return {"list": []}
    
    def playerContent(self, flag, id, vipFlags=0):
        """解析播放地址"""
        result = {"parse": 1, "url": id, "header": self.headers}
        
        try:
            # 如果id已经是m3u8链接，直接返回
            if id and ('.m3u8' in id or '.mp4' in id):
                result["parse"] = 0
                result["url"] = id
                result["header"] = {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.host,
                    'Origin': 'https://a123tv.com'
                }
                return result
            
            # 否则访问播放页提取地址
            if not id.startswith('http'):
                play_url = self.host + id if id.startswith('/') else self.host + '/' + id
            else:
                play_url = id
            
            print(f"[A123TV] playerContent URL: {play_url}")
            root = self._fetch_html(play_url)
            if root:
                # 方法1: 从 #awp1 data-src 提取
                player_div = root.find('div', id='awp1')
                if player_div:
                    m3u8_url = player_div.get('data-src', '')
                    if m3u8_url:
                        result["parse"] = 0
                        result["url"] = m3u8_url
                        result["header"] = {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': play_url,
                            'Origin': 'https://a123tv.com'
                        }
                        return result
                
                # 方法2: 从 var pp 提取
                scripts = root.find_all('script')
                for script in scripts:
                    if script.string and 'var pp=' in script.string:
                        match = re.search(r'var pp=(\{.*?\});', script.string, re.DOTALL)
                        if match:
                            try:
                                pp_data = json.loads(match.group(1))
                                if pp_data and 'la' in pp_data and pp_data['la']:
                                    # 找当前线路或第一个线路
                                    for line in pp_data['la']:
                                        if len(line) >= 5 and line[4]:
                                            m3u8_url = line[4]
                                            if m3u8_url:
                                                result["parse"] = 0
                                                result["url"] = m3u8_url
                                                result["header"] = {
                                                    'User-Agent': self.headers['User-Agent'],
                                                    'Referer': play_url,
                                                    'Origin': 'https://a123tv.com'
                                                }
                                                return result
                            except:
                                pass
                
                # 方法3: 从 video 标签提取
                video_tag = root.find('video')
                if video_tag:
                    video_src = video_tag.get('src') or video_tag.get('data-src', '')
                    if video_src:
                        result["parse"] = 0
                        result["url"] = video_src
                        result["header"] = {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': play_url,
                            'Origin': 'https://a123tv.com'
                        }
                        return result
            
            # 没找到直接播放地址，降级让TVBox解析
            result["parse"] = 1
            result["url"] = play_url
            result["header"] = self.headers
        except Exception as e:
            print(f"[A123TV] playerContent error: {e}")
            result["parse"] = 1
            result["url"] = id
            result["header"] = self.headers
        
        return result
    
    def localProxy(self, params):
        """本地代理"""
        return [200, "video/MP2T", ""]
    
    def recommendContent(self, ids, pg=1):
        """相关推荐"""
        try:
            vod_id = ids[0] if ids else ""
            if not vod_id:
                return {"list": []}
            
            if not vod_id.startswith('http'):
                url = self.host + vod_id if vod_id.startswith('/') else self.host + '/' + vod_id
            else:
                url = vod_id
            
            root = self._fetch_html(url)
            if not root:
                return {"list": []}
            
            videos = []
            items = root.select('.w4-list .w4-item-wrap')
            
            for item in items[:12]:
                try:
                    a = item.find('a', class_='w4-item')
                    if not a:
                        continue
                    
                    href = a.get('href', '')
                    if not href:
                        continue
                    vid = href if href.startswith('http') else self.host + href
                    
                    title_div = a.find('div', class_='t')
                    vod_name = ""
                    if title_div:
                        vod_name = title_div.get('title', '') or title_div.text.strip()
                    if not vod_name:
                        vod_name = a.get('title', '')
                    
                    vod_pic = ""
                    img = a.find('img')
                    if img:
                        vod_pic = img.get('data-src') or img.get('src', '')
                        if vod_pic and vod_pic.startswith('//'):
                            vod_pic = 'https:' + vod_pic
                    
                    vod_remarks = ""
                    i_elem = a.find('div', class_='i')
                    if i_elem:
                        vod_remarks = i_elem.text.strip()
                    
                    if vod_name and vid:
                        videos.append({
                            "vod_id": vid,
                            "vod_name": vod_name,
                            "vod_pic": vod_pic,
                            "vod_remarks": vod_remarks
                        })
                except Exception as e:
                    continue
            
            return {"list": videos}
        except Exception as e:
            print(f"[A123TV] recommendContent error: {e}")
            return {"list": []}
    
    def debug_homeVideoContent(self):
        """调试首页推荐 - 输出详细信息"""
        import json
        debug_info = {}
        try:
            rsp = self.fetch(self.host, headers=self.headers)
            debug_info['rsp_type'] = str(type(rsp))
            debug_info['rsp_str'] = str(rsp)[:200]
            
            if isinstance(rsp, str):
                html = rsp
                debug_info['source'] = 'string'
            elif hasattr(rsp, 'text'):
                html = rsp.text
                debug_info['source'] = 'text'
                debug_info['text_len'] = len(html)
            elif hasattr(rsp, 'content'):
                html = rsp.content.decode('utf-8', errors='ignore')
                debug_info['source'] = 'content'
                debug_info['content_len'] = len(html)
            else:
                html = str(rsp)
                debug_info['source'] = 'str_fallback'
            
            debug_info['html_len'] = len(html)
            debug_info['html_preview'] = html[:500]
            
            root = BeautifulSoup(html, 'html.parser')
            items = root.select('.w4-item-wrap')
            debug_info['item_count'] = len(items)
            
            if items:
                debug_info['first_item'] = str(items[0])[:300]
            
            # 返回调试信息
            return debug_info
        except Exception as e:
            import traceback
            debug_info['error'] = str(e)
            debug_info['traceback'] = traceback.format_exc()
            return debug_info