# coding: utf-8
# DuJAV (d.dujav.com) — 免費線上看日本AV，T3 爬蟲源（繁體站 /tw）
# 架構：Next.js SSR。列表卡片 data-video-id + /tw/{分類}/{slug}；詳情頁內嵌
#      ld+json VideoObject 可直取 metadata。
# 播放鏈：詳情 iframe → /watch/{slug}
#        → GET /api/player/{slug} 回 {"url":"/watch/t/TOKEN"}
# 播放鏈：詳情 iframe → /watch/{slug}
#        → GET /api/player/{slug} 回 {"url":"/watch/t/TOKEN"}
#        → GET 該 url 跟隨 302 落地第三方播放頁（host 會輪替：upload18/ibucket…）
#        → 頁內 window.playerConfig.playlistUrl 即 HLS 直鏈（切片絕對位址，UA 即可）。

import re
import json
from urllib.parse import quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    HOST = "https://d.dujav.com"
    CDN = "https://cdn.dujav.com"
    LANG = "tw"

    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 靜態分類（零網絡，法則16）。type_id 為 /tw/ 之後的分類段。
    CLASSES = [
        ("trending", "熱門"),
        ("popular", "人氣"),
        ("censored", "有碼"),
        ("uncensored", "無碼"),
        ("uncen-leak", "無碼流出"),
        ("chinese-av", "華語AV"),
        ("subtitle", "中文字幕"),
        ("amateur", "素人"),
        ("hentai", "動漫"),
    ]

    # 排序篩選（以 /sort/{值} 路徑段生效）
    SORTS = [
        {"n": "預設", "v": ""},
        {"n": "最新", "v": "updated_at"},
        {"n": "日榜", "v": "today_view"},
        {"n": "週榜", "v": "weekly_view"},
        {"n": "月榜", "v": "monthly_view"},
        {"n": "總榜", "v": "total_view"},
    ]

    # 卡片正則
    RE_CARD = re.compile(
        r'data-video-id="\d+"\s+href="/%s/([a-z0-9-]+/[a-z0-9-]+)"(.*?)</a>' % LANG,
        re.S)
    RE_IMG = re.compile(r'<img\s+src="([^"]+)"\s+alt="([^"]*)"', re.S)
    RE_TITLE = re.compile(r'dj-video-card-title[^>]*>([^<]+)<')
    RE_ACTORS = re.compile(r'dj-video-card-actors[^>]*>([^<]+)<')
    RE_DUR = re.compile(r'(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\s*</span>')
    RE_PAGE = re.compile(r'[?&]page=(\d+)')
    RE_PLAYER_CFG = re.compile(r'window\.player[_]?config\s*=\s*(\{.*?\})\s*;', re.S | re.I)
    RE_LDJSON = re.compile(
        r'<script type="application/ld\+json">(.*?)</script>', re.S)

    # ------------------------------------------------------------- framework
    def getName(self):
        return "DuJAV"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return ""

    def liveContent(self, url):
        return ""

    def action(self, action):
        return ""

    def init(self, extend=""):
        self.extend = extend or ""
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/" + self.LANG,
            "Accept-Language": "zh-TW,zh;q=0.9",
        }
        # 播放請求頭（實測第三方 CDN 切片只需 UA 即可取片）
        self.play_header = {
            "User-Agent": self.UA,
        }

    # ------------------------------------------------------------- helpers
    def _get(self, path):
        url = path if path.startswith("http") else (self.HOST + path)
        try:
            r = self.fetch(url, headers=self.headers, timeout=25)
            if r is None or getattr(r, "status_code", 0) != 200:
                return ""
            return r.text or ""
        except Exception as e:
            self.log("get fail %s: %s" % (url, e))
            return ""

    def _img(self, src):
        if not src:
            return ""
        if src.startswith("http"):
            return src
        if src.startswith("/"):
            return self.CDN + src
        return src

    def _parse_list(self, html, exclude=None):
        """解析列表卡片為 vod 列表。vod_id = 分類/slug。"""
        out = []
        for vid, body in self.RE_CARD.findall(html or ""):
            if exclude and vid == exclude:
                continue
            mt = self.RE_TITLE.search(body)
            mi = self.RE_IMG.search(body)
            name = ""
            pic = ""
            if mi:
                pic = self._img(mi.group(1))
                name = (mi.group(2) or "").strip()
            if mt:
                name = mt.group(1).strip() or name
            if not name:
                name = vid.split("/")[-1]
            md = self.RE_DUR.search(body)
            remark = md.group(1) if md else ""
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
                "style": {"type": "rect", "ratio": 1.5},
            })
        return out

    def _pagecount(self, html, pg):
        nums = [int(x) for x in self.RE_PAGE.findall(html or "")]
        if nums:
            return max(max(nums), pg)
        return pg + 1 if (html or "").count("data-video-id") >= 24 else pg

    def _ldjson_video(self, html):
        """抽詳情頁 ld+json 的 VideoObject。"""
        for block in self.RE_LDJSON.findall(html or ""):
            try:
                data = json.loads(block)
            except Exception:
                continue
            graph = data.get("@graph") if isinstance(data, dict) else None
            cands = graph if isinstance(graph, list) else [data]
            for node in cands:
                if isinstance(node, dict) and node.get("@type") == "VideoObject":
                    return node
        return {}

    @staticmethod
    def _iso_dur(s):
        """PT1H29M49S → 1:29:49。"""
        m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s or "")
        if not m:
            return ""
        h, mi, se = (int(x) if x else 0 for x in m.groups())
        if h:
            return "%d:%02d:%02d" % (h, mi, se)
        return "%d:%02d" % (mi, se)

    @staticmethod
    def _names(val):
        out = []
        if isinstance(val, list):
            for x in val:
                if isinstance(x, dict) and x.get("name"):
                    out.append(x["name"])
                elif isinstance(x, str):
                    out.append(x)
        elif isinstance(val, dict) and val.get("name"):
            out.append(val["name"])
        elif isinstance(val, str):
            out.append(val)
        return out

    # ------------------------------------------------------------- home
    def homeContent(self, filter):
        classes = [{"type_id": p, "type_name": n} for p, n in self.CLASSES]
        filters = {}
        sort_filter = [{
            "key": "sort",
            "name": "排序",
            "value": [{"n": s["n"], "v": s["v"]} for s in self.SORTS],
        }]
        for p, _ in self.CLASSES:
            filters[p] = sort_filter
        return {"class": classes, "filters": filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._get("/%s/trending" % self.LANG)
        return {"list": self._parse_list(html)}

    # ------------------------------------------------------------- category
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        tid = str(tid).strip("/")
        sort = ""
        if isinstance(extend, dict):
            sort = (extend.get("sort") or "").strip()
        path = "/%s/%s" % (self.LANG, tid)
        if sort:
            path += "/sort/%s" % sort
        path += "?page=%d" % pg
        html = self._get(path)
        vods = self._parse_list(html)
        pc = self._pagecount(html, pg)
        return {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": len(vods) or 24,
            "total": (len(vods) or 24) * pc,
        }

    # ------------------------------------------------------------- search
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        html = self._get("/%s/search/%s?page=%d" % (self.LANG, quote(key), pg))
        return {"list": self._parse_list(html), "page": pg}

    def getSearchContent(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ------------------------------------------------------------- detail
    def _norm_ids(self, ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", "replace")
        return str(ids).strip().strip("/")

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        slug = vid.split("/")[-1]
        try:
            html = self._get("/%s/%s" % (self.LANG, vid))
            vo = self._ldjson_video(html)

            name = (vo.get("name") or slug).strip()
            pic = self._img(vo.get("thumbnailUrl") or "")
            desc = (vo.get("description") or "").strip()
            actors = self._names(vo.get("actor"))
            directors = self._names(vo.get("director"))
            genres = self._names(vo.get("genre"))
            dur = self._iso_dur(vo.get("duration") or "")
            date = (vo.get("uploadDate") or "")[:10]
            year = date[:4]
            code = ""
            alt = vo.get("alternateName")
            if isinstance(alt, list) and alt:
                code = alt[0]
            elif isinstance(alt, str):
                code = alt

            parts = []
            if code:
                parts.append("番號：" + code)
            if date:
                parts.append("發行日期：" + date)
            if dur:
                parts.append("時長：" + dur)
            if genres:
                parts.append("類型：" + "、".join(genres))
            if desc:
                parts.append("")
                parts.append(desc)

            vod = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_year": year,
                "vod_area": "日本",
                "vod_remarks": dur or code,
                "vod_content": "\n".join(parts),
                "vod_actor": "、".join(actors),
                "vod_director": "、".join(directors),
                "type_name": "、".join(genres),
                "vod_play_from": "DuJAV",
                "vod_play_url": "正片$%s" % slug,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detail fail %s: %s" % (vid, e))
            return {"list": [{
                "vod_id": vid, "vod_name": slug, "vod_pic": "",
                "vod_remarks": "解析異常", "vod_content": "",
                "vod_play_from": "DuJAV", "vod_play_url": "正片$%s" % slug,
            }]}

    # ------------------------------------------------------------- recommend
    def recommendContent(self, ids=None, pg="1"):
        """FongMi 詳情頁相關推薦：詳情頁底部自帶卡片，直接複用列表解析。"""
        vid = self._norm_ids(ids)
        slug = vid.split("/")[-1] if vid else None
        try:
            if vid:
                html = self._get("/%s/%s" % (self.LANG, vid))
                vods = self._parse_list(html, exclude=vid)
                if vods:
                    return {"list": vods[:18]}
            vods = self._parse_list(self._get("/%s/trending" % self.LANG), exclude=vid)
            return {"list": vods[:18]}
        except Exception as e:
            self.log("recommend fail: %s" % e)
            return {"list": []}

    # ------------------------------------------------------------- player
    def _resolve_m3u8(self, slug):
        """slug → 簽名 m3u8 直鏈（現取現用，token 有時效）。"""
        # 1) 取加密播放頁 token
        api = self.HOST + "/api/player/" + slug
        hdr = dict(self.headers)
        hdr["Referer"] = self.HOST + "/watch/" + slug
        hdr["X-Requested-With"] = "XMLHttpRequest"
        r = self.fetch(api, headers=hdr, timeout=20)
        if r is None or getattr(r, "status_code", 0) != 200:
            return ""
        try:
            inner = (r.json() or {}).get("url", "")
        except Exception:
            m = re.search(r'"url"\s*:\s*"([^"]+)"', r.text or "")
            inner = m.group(1) if m else ""
        if not inner:
            return ""
        # 2) 跟隨 302 落地第三方播放頁
        land = inner if inner.startswith("http") else (self.HOST + inner)
        r2 = self.fetch(land, headers={"User-Agent": self.UA,
                                       "Referer": self.HOST + "/watch/" + slug},
                        timeout=25)
        if r2 is None or getattr(r2, "status_code", 0) != 200:
            return ""
        html = r2.text or ""
        # 3) 取第三方播放頁 window.playerConfig 內的 HLS 直鏈
        #    欄位依站而異：playlistUrl / m3u8 / url / file 皆兜底
        mc = self.RE_PLAYER_CFG.search(html)
        if mc:
            try:
                cfg = json.loads(mc.group(1))
                for k in ("playlistUrl", "m3u8", "url", "file",
                          "alternate1080", "alternate720"):
                    v = cfg.get(k)
                    if v and (".m3u8" in v or ".mp4" in v):
                        return v
            except Exception:
                pass
        m = re.search(r'"(?:playlistUrl|m3u8|file|url)"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if m:
            return m.group(1).replace("\\/", "/").replace("\\u0026", "&")
        return ""

    def playerContent(self, flag, id, vipFlags):
        if id and id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            return {"parse": 0, "url": id, "header": self.play_header}
        try:
            slug = str(id).strip().strip("/").split("/")[-1]
            url = self._resolve_m3u8(slug)
            if url:
                return {"parse": 0, "url": url, "header": self.play_header}
        except Exception as e:
            self.log("player fail %s: %s" % (id, e))
        return {"parse": 0, "url": "", "header": self.play_header}

    def localProxy(self, param):
        return [200, "text/plain", ""]
