# -*- coding: utf-8 -*-
import re
import sys

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

from base.spider import Spider as BaseSpider

PY2 = sys.version_info[0] == 2


def _unescape(s):
    if not s:
        return s
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'"),
                 ("&#039;", "'"), ("&nbsp;", " "), ("&#038;", "&"),
                 ("&hellip;", "…"), ("&#8217;", "'"), ("&#8216;", "'"),
                 ("&#8220;", '"'), ("&#8221;", '"')):
        s = s.replace(a, b)
    return s


def _strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "")


class Spider(BaseSpider):

    HOST = "https://gotanynudes.com"
    UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # (type_id, type_name)。type_id 直接是列表路径片段（category/xxx 或 tag/xxx）。
    CATEGORIES = [
        ("category/onlyfans", "🔥 OnlyFans"),
        ("category/porn-x", "💎 Porn-X"),
        ("category/tiktok", "🎵 TikTok"),
        ("category/twitch", "🎮 Twitch"),
        ("category/youtube", "▶️ YouTube"),
        ("tag/dildo", "🍆 Dildo"),
        ("tag/blowjob", "💋 Blowjob"),
        ("tag/booty", "🍑 Booty"),
        ("tag/big-tits", "🍈 Big Tits"),
        ("tag/small-tits", "🍊 Small Tits"),
        ("tag/cute", "🌸 Cute"),
        ("tag/blonde", "👱‍♀️ Blonde"),
        ("tag/lingerie", "👙 Lingerie"),
        ("tag/thicc-xxx", "🔥 Thicc"),
    ]

    # ---------- lifecycle ----------
    def init(self, extend=""):
        self.extend = extend

    def getName(self):
        return "GotAnyNudes"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return (".m3u8" in u) or u.endswith(".mp4") or (".mp4?" in u)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------- helpers ----------
    def _headers(self, referer=None):
        return {
            "User-Agent": self.UA,
            "Referer": referer or (self.HOST + "/"),
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "en-US,en;q=0.9",
            "sec-ch-ua": '"Chromium";v="120", "Not=A?Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "Upgrade-Insecure-Requests": "1",
        }

    def _get(self, url, referer=None):
        try:
            rsp = self.fetch(url, headers=self._headers(referer), timeout=30)
            if rsp is None:
                return ""
            return rsp.text or ""
        except Exception as e:
            self.log("fetch error %s: %s" % (url, e))
            return ""

    def _abs(self, u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.HOST + u
        return u

    def _first_img(self, block):
        """从列表项块里尽量稳健地取封面（支持 src / data-src / srcset）。"""
        m = re.search(r'<img[^>]*?\sdata-no-lazy="1"[^>]*?\ssrc="([^"]+)"', block)
        if m:
            return self._abs(_unescape(m.group(1)))
        m = re.search(r'<img[^>]*?\ssrc="([^"]+)"', block)
        if m and "data:image" not in m.group(1):
            return self._abs(_unescape(m.group(1)))
        for attr in ("data-src", "data-lazy-src", "data-original"):
            m = re.search(r'<img[^>]*?\s%s="([^"]+)"' % attr, block)
            if m:
                return self._abs(_unescape(m.group(1)))
        m = re.search(r'<img[^>]*?\ssrcset="([^"\s]+)', block)
        if m:
            return self._abs(_unescape(m.group(1)))
        return ""

    # ---------- 列表解析 ----------
    def _parse_list(self, html):
        """解析 g1-collection 列表（首页 / 分类 / 标签 / 搜索通用）。"""
        vods = []
        seen = set()
        # 以 <article ...> 为切分点，逐块解析
        blocks = re.split(r'(?=<article class="entry-tpl-grid)', html)
        for b in blocks:
            if 'entry-tpl-grid' not in b[:40]:
                continue
            # 标题 + 详情链接（优先 entry-title 内的 a）
            tm = re.search(
                r'<h\d[^>]*class="[^"]*entry-title[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                b, re.S)
            if not tm:
                # 回退：featured-media 的 a title
                tm = re.search(
                    r'<div class="entry-featured-media[^"]*">\s*<a[^>]*title="([^"]*)"[^>]*href="([^"]+)"',
                    b)
                if not tm:
                    continue
                title = _unescape(tm.group(1)).strip()
                href = tm.group(2)
            else:
                href = tm.group(1)
                title = _unescape(_strip_tags(tm.group(2))).strip()

            href = self._abs(href)
            if not href or href in seen:
                continue
            # 只保留本站详情页
            if "gotanynudes.com" not in href:
                continue
            seen.add(href)

            pic = self._first_img(b)

            remark = ""
            dm = re.search(r'<time class="entry-date"[^>]*>([^<]+)</time>', b)
            if dm:
                remark = _unescape(dm.group(1)).strip()

            vods.append({
                "vod_id": href,
                "vod_name": title or "视频",
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return vods

    def _pagecount(self, html, cur):
        """从 rel=next / load-more / page/N 推断是否还有下一页。"""
        if re.search(r'rel="next"', html):
            return cur + 1
        if re.search(r'data-g1-next-page-url="[^"]*page/(\d+)', html):
            return cur + 1
        nums = re.findall(r'/page/(\d+)/', html)
        if nums:
            mx = max(int(n) for n in nums)
            return mx if mx >= cur else cur
        return cur

    # ---------- home ----------
    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name}
                   for tid, name in self.CATEGORIES]
        result = {"class": classes}
        html = self._get(self.HOST + "/")
        result["list"] = self._parse_list(html)
        return result

    def homeVideoContent(self):
        html = self._get(self.HOST + "/")
        return {"list": self._parse_list(html)}

    # ---------- category ----------
    def _cat_url(self, tid, page):
        base = "%s/%s" % (self.HOST, tid.strip("/"))
        if page <= 1:
            return base + "/"
        return "%s/page/%d/" % (base, page)

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1

        url = self._cat_url(tid, page)
        html = self._get(url)
        vods = self._parse_list(html)

        pagecount = self._pagecount(html, page)
        if not vods:
            pagecount = page
        limit = len(vods) if vods else 24
        return {
            "list": vods,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
        }

    # ---------- detail ----------
    def _extract_mp4(self, html):
        for pat in (
            r'<meta[^>]+property="og:video(?::secure_url)?"[^>]+content="([^"]+\.mp4[^"]*)"',
            r'"contentUrl"\s*:\s*"([^"]+\.mp4[^"]*)"',
            r'<source[^>]+src="([^"]+\.mp4[^"]*)"',
            r'(https?://ares\.gotanynudes\.com/[^"\'\s]+\.mp4[^"\'\s]*)',
        ):
            m = re.search(pat, html)
            if m:
                return self._abs(_unescape(m.group(1).replace("\\/", "/")))
        return ""

    def detailContent(self, ids):
        vid = ids[0]
        url = self._abs(vid)
        html = self._get(url)

        name = ""
        tm = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', html)
        if tm:
            name = _unescape(tm.group(1)).strip()
        if not name:
            h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if h1:
                name = _unescape(_strip_tags(h1.group(1))).strip()

        pic = ""
        pm = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
        if pm:
            pic = self._abs(_unescape(pm.group(1)))

        desc = ""
        dm = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"', html)
        if dm:
            desc = _unescape(dm.group(1)).strip()

        # 分类 / 标签
        cats = re.findall(r'rel="category tag">([^<]+)</a>', html)
        tags = re.findall(r'class="entry-tag entry-tag-\d+">([^<]+)</a>', html)
        remarks = ", ".join(_unescape(x).strip() for x in (cats[:1] + tags[:3]))

        src = self._extract_mp4(html)

        vod = {
            "vod_id": url,
            "vod_name": name or "视频",
            "vod_pic": pic,
            "vod_actor": "",
            "vod_director": "",
            "vod_remarks": remarks,
            "vod_content": desc,
            "vod_play_from": "GotAnyNudes",
            "vod_play_url": "正片$" + (src or url),
        }
        return {"list": [vod]}

    # ---------- search ----------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        kw = quote(key)
        if page <= 1:
            url = "%s/?s=%s" % (self.HOST, kw)
        else:
            url = "%s/page/%d/?s=%s" % (self.HOST, page, kw)
        html = self._get(url)
        vods = self._parse_list(html)
        return {"list": vods, "page": page}

    # ---------- player ----------
    def playerContent(self, flag, id, vipFlags):
        url = self._abs(id or "")
        headers = {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
        }
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": headers,
        }

    def localProxy(self, param):
        return [404, "text/plain", {}, ""]
