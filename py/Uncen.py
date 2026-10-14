# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：Uncen (uncen.co)  https://www.uncen.co/tw
类型：JAV 无码洩漏类成人影视站 —— Next.js SSR + Cloudflare CDN，纯 HTML 解析 + HLS(m3u8) 直链
说明（结构要点，换站只改开头站点信息）：
  - 列表首页：/tw ，翻页 /tw?page={N}（totalPages≈4000）
  - 分类清单：/tw/topics（totalPages≈23）；单一主题 /tw/topics/{topic}?page={N}
  - 搜索：/tw/search/{keyword}
  - 详情页：/tw/{slug}-uncen（如 /tw/hnds-021-uncen）；路由 /tw/[...slug]
  - 列表卡片：<a class="group block..." data-video-id="N" href="/tw/{slug}-uncen">
                <article>...<img src="/images/xx/xx/{stem}.webp" alt="标题">...
                <span ...>HH:MM:SS</span>（时长）...<p class="dj-video-card-title">标题</p>
  - 封面/CDN 文件名 stem：一般番号 {slug}-uncensored-leak，KBJ/FC2 类用 {slug}
  - 详情页 JSON-LD VideoObject：name/thumbnailUrl/duration(ISO8601)/embedUrl/genre[]/description
  - 播放链路（已破解 parse:0 直连，2026-10-02 验证）：
      1) 捷径（一般番号）：直拼 https://uncenxcdn.com/{stem}/playlist.m3u8（200，CORS *，无需 UA/Referer）
      2) 完整链路（KBJ/FC2 等捷径 404 时）：
         GET /api/player/{stem}（必带 Referer: https://www.uncen.co/watch/{slug}-uncen，否则 403）
         -> {"url":"/play/v/{JWT}"} -> GET /play/v/{JWT}(禁跟随) -> 302 ibucket.org/embed/...
         -> ibucket 页 window.playerConfig.playlistUrl = uncenxcdn.com/{stem}/playlist.m3u8
      master 含 //uncenxcdn.com/{mediaId}/video.m3u8，分片为伪装 .jpeg 的 TS。
最后验证：2026-10-02
"""
import sys
import json
import re
import base64
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        def init(self, extend=""):
            pass


class Spider(Spider):
    # ============ 站点信息（换站只改这里）============
    siteName = "Uncen"
    HOST = "https://www.uncen.co"
    CDN_HOST = "https://uncenxcdn.com"        # master m3u8 域
    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
    LIMIT = 48

    # ---------- 生命周期 ----------
    def init(self, extend=""):
        self.extend = extend or ""
        return

    def getName(self):
        return self.siteName

    def isVideoFormat(self, url):
        u = url or ""
        return any(x in u for x in (".m3u8", ".mp4", ".ts", ".flv", ".mkv"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def getDependence(self):
        return []

    # ================= HTTP =================
    def _headers(self, referer=None):
        return {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Referer": referer or (self.HOST + "/tw"),
        }

    def _get(self, url, referer=None):
        try:
            r = self.fetch(url, headers=self._headers(referer))
        except Exception:
            return ""
        if not r:
            return ""
        return getattr(r, "text", "") or ""

    @staticmethod
    def _unescape(s):
        if not s:
            return s
        for a, b in (("&amp;", "&"), ("&#039;", "'"), ("&#39;", "'"),
                     ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">"),
                     ("&hellip;", "…"), ("&nbsp;", " ")):
            s = s.replace(a, b)
        return s.strip()

    # ================= 卡片解析 =================
    # 锚点开头：<a class="group block..." data-video-id="N" href="/tw/{slug}-uncen">
    _A_RE = re.compile(
        r'<a\b[^>]*\bdata-video-id="(\d+)"[^>]*\bhref="(/tw/[^"]+)"', re.S)

    def _cards_from_html(self, html):
        out, seen = [], set()
        if not html:
            return out
        anchors = list(self._A_RE.finditer(html))
        for i, m in enumerate(anchors):
            vid_num = m.group(1)
            href = m.group(2)
            # 以 /tw/ 后段作 vod_id（如 hnds-021-uncen）
            vod_id = href.split("?")[0].split("#")[0].strip("/")
            if vod_id.startswith("tw/"):
                vod_id = vod_id[3:]
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)
            # 该卡片 HTML 片段：从本锚点到下一个锚点之间
            start = m.start()
            end = anchors[i + 1].start() if i + 1 < len(anchors) else min(len(html), start + 2000)
            block = html[start:end]
            # 封面与标题（img src + alt）
            pic, title = "", ""
            mi = re.search(r'<img[^>]*\bsrc="(/images/[^"]+)"[^>]*\balt="([^"]*)"', block)
            if not mi:
                mi = re.search(r'<img[^>]*\balt="([^"]*)"[^>]*\bsrc="(/images/[^"]+)"', block)
                if mi:
                    title, pic = mi.group(1), mi.group(2)
            else:
                pic, title = mi.group(1), mi.group(2)
            if pic.startswith("/"):
                pic = self.HOST + pic
            # 时长 HH:MM:SS 或 MM:SS
            md = re.search(r'>(\d{1,2}:\d{2}(?::\d{2})?)<', block)
            remark = md.group(1) if md else ""
            # 标题兜底
            if not title:
                mt = re.search(r'class="dj-video-card-title"[^>]*>([^<]+)<', block)
                title = mt.group(1).strip() if mt else vod_id
            out.append({
                "vod_id": vod_id,
                "vod_name": self._unescape(title),
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    def _pagecount(self, html, page):
        m = re.search(r'totalPages\\*"?\s*:\s*(\d+)', html or "")
        if not m:
            # 兜底：扫 ?page=N 最大值
            pages = re.findall(r'[?&]page=(\d+)', html or "")
            if pages:
                try:
                    return max(max(int(p) for p in pages), page)
                except Exception:
                    pass
            return page
        try:
            pc = int(m.group(1))
        except Exception:
            pc = page
        return max(pc, page)

    # ================= 首页分类（静态硬编码，零网络，法则16）=================
    _CLASSES = [
        ("无码洩漏", "uncensored-leak"),
        ("无码", "uncensored"),
        ("中出", "creampie"),
        ("人妻", "wife"),
        ("熟女", "mature-woman"),
        ("美少女", "pretty-girl"),
        ("巨乳", "big-breasts"),
        ("美乳", "beautiful-breasts"),
        ("素人", "amateur"),
        ("乱交", "orgy"),
        ("淫乱", "slut"),
        ("潮吹", "squirting"),
        ("口交", "oral-sex"),
        ("骑乘", "ride"),
        ("NTR", "ntr"),
        ("制服", "uniform"),
        ("角色扮演", "cosplay"),
        ("女子高中生", "high-school-girl"),
        ("娇小", "petite"),
        ("美臀", "big-ass"),
        ("自拍", "selfie"),
        ("FC2PPV", "fc2ppv"),
        ("4K", "4k"),
        ("HD", "hd"),
        ("独家", "exclusive"),
        ("4小时以上", "4-hours-or-more"),
        ("有码", "censored"),
    ]

    def homeContent(self, filter):
        classes = [{"type_name": n, "type_id": t} for (n, t) in self._CLASSES]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        html = self._get(self.HOST + "/tw")
        return {"list": self._cards_from_html(html)}

    # ================= 分类 =================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        slug = str(tid or "").strip().strip("/")
        url = "%s/tw/topics/%s" % (self.HOST, slug)
        if page > 1:
            url += "?page=%d" % page
        html = self._get(url)
        lst = self._cards_from_html(html)
        pc = self._pagecount(html, page)
        return {
            "list": lst,
            "page": page,
            "pagecount": pc,
            "limit": len(lst) or self.LIMIT,
            "total": pc * (len(lst) or self.LIMIT),
        }

    # ================= 详情 =================
    def _norm_ids(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        return str(ids or "").strip()

    def _jsonld_video(self, html):
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            raw = m.group(1).strip()
            try:
                j = json.loads(raw)
            except Exception:
                continue
            cand = j if isinstance(j, list) else [j]
            for obj in cand:
                if isinstance(obj, dict) and obj.get("@type") == "VideoObject":
                    return obj
        return {}

    @staticmethod
    def _dedup_title(name):
        """去掉站点 name 尾部冗余的 ' - {演员}'（标题结尾已含该演员名时会重复附加）。"""
        if not name:
            return name
        idx = name.rfind(" - ")
        if idx > 0:
            head = name[:idx].rstrip()
            tail = name[idx + 3:].strip()
            if tail and tail in head:
                return head
        return name

    @staticmethod
    def _iso_duration(s):
        if not s:
            return ""
        m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s)
        if not m:
            return ""
        h, mi, se = (int(x) if x else 0 for x in m.groups())
        if h:
            return "%d:%02d:%02d" % (h, mi, se)
        return "%d:%02d" % (mi, se)

    def _stem_from_pic(self, pic):
        """由封面 URL 取 CDN 文件名 stem（如 hnds-021-uncensored-leak）。"""
        if not pic:
            return ""
        name = pic.split("?")[0].split("/")[-1]
        return re.sub(r'\.(webp|jpg|jpeg|png)$', '', name, flags=re.I)

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        slug = vid.strip("/")
        if slug.startswith("tw/"):
            slug = slug[3:]
        url = "%s/tw/%s" % (self.HOST, slug)
        html = self._get(url)

        # base slug（去 -uncen 后缀，用于 /watch Referer）
        base_slug = re.sub(r'-uncen$', '', slug)

        # 骨架兜底（法则35）
        skeleton = {
            "vod_id": vid, "vod_name": slug, "vod_pic": "",
            "vod_play_from": self.siteName, "vod_play_url": "正片$ERR",
        }
        if not html:
            return {"list": [skeleton]}

        j = self._jsonld_video(html)
        name = self._dedup_title(self._unescape(j.get("name") or slug))
        pic = j.get("thumbnailUrl") or ""
        if isinstance(pic, list):
            pic = pic[0] if pic else ""
        if not pic:
            mp = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            pic = mp.group(1) if mp else ""
        content = self._unescape(str(j.get("description") or ""))
        if not content:
            mo = re.search(r'<meta property="og:description" content="([^"]+)"', html)
            content = self._unescape(mo.group(1)) if mo else ""
        remark = self._iso_duration(j.get("duration") or "")
        genre = j.get("genre") or []
        type_name = ", ".join(genre[:10]) if isinstance(genre, list) else str(genre)

        # CDN stem：优先封面文件名，兜底 base_slug-uncensored-leak
        stem = self._stem_from_pic(pic)
        if not stem:
            stem = base_slug + "-uncensored-leak"

        # watch 页 URL（API 回退时的 Referer）：优先 JSON-LD embedUrl，兜底重建
        watch = j.get("embedUrl") or ""
        if not watch:
            watch = "%s/watch/%s" % (self.HOST, slug if slug.endswith("-uncen") else slug + "-uncen")

        # 播放 token：stem|watch_url（避免裸 $，法则21）
        tok = base64.b64encode(("%s|%s" % (stem, watch)).encode()).decode()
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_area": "日本",
            "vod_content": content,
            "type_name": type_name,
            "vod_play_from": self.siteName,
            "vod_play_url": "正片$" + tok,
        }
        return {"list": [vod]}

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        kw = str(key or "").strip()
        url = "%s/tw/search/%s" % (self.HOST, quote(kw))
        if page > 1:
            url += "?page=%d" % page
        html = self._get(url)
        return {"list": self._cards_from_html(html), "page": page}

    # ================= 播放 =================
    def playerContent(self, flag, id, vipFlags):
        tok = self._norm_ids(id)
        if not tok or tok == "ERR":
            return {"parse": 0, "url": "", "header": {}}

        stem, watch = "", ""
        try:
            dec = base64.b64decode(tok).decode("utf-8", "ignore")
            if "|" in dec:
                stem, watch = dec.split("|", 1)
            else:
                stem = dec
        except Exception:
            stem = tok
        stem = (stem or "").strip()
        watch = (watch or "").strip()
        if not stem:
            return {"parse": 0, "url": "", "header": {}}

        ua = {"User-Agent": self.UA}

        # 1) 捷径：直拼 CDN playlist（CORS *，无需 UA/Referer）
        #    依次尝试：原 stem、补 -uncensored-leak 后缀（搜索页 slug 常缺后缀）
        cands = []
        s0 = stem
        cands.append(s0)
        if not s0.endswith("-uncensored-leak"):
            cands.append(s0 + "-uncensored-leak")
        for st in cands:
            direct = "%s/%s/playlist.m3u8" % (self.CDN_HOST, st)
            if self._playlist_ok(direct):
                return {"parse": 0, "url": direct, "header": ua}

        # 2) 完整链路：/api/player（带 Referer）-> /play/v/{JWT} -> player 页 -> m3u8
        real = self._resolve_via_api(stem, watch)
        if real:
            return {"parse": 0, "url": real, "header": ua}

        # 兜底：返回最可能的直拼（让盒子自行尝试）
        fallback = "%s/%s/playlist.m3u8" % (self.CDN_HOST, cands[-1])
        return {"parse": 0, "url": fallback, "header": ua}

    def _playlist_ok(self, url):
        try:
            r = self.fetch(url, headers={"User-Agent": self.UA}, timeout=8)
        except Exception:
            return False
        if not r:
            return False
        code = getattr(r, "status_code", 0)
        txt = getattr(r, "text", "") or ""
        return code == 200 and "#EXTM3U" in txt[:64]

    def _resolve_via_api(self, stem, watch):
        watch_ref = watch or ("%s/watch/%s-uncen" % (self.HOST, re.sub(r'-uncensored-leak$', '', stem)))
        api = "%s/api/player/%s" % (self.HOST, stem)
        try:
            r = self.fetch(api, headers={"User-Agent": self.UA, "Referer": watch_ref}, timeout=10)
            j = json.loads(getattr(r, "text", "") or "{}")
        except Exception:
            return ""
        rel = j.get("url") or ""
        if not rel:
            return ""
        play_url = rel if rel.startswith("http") else (self.HOST + rel)
        # /play/v/{JWT} -> 302 ibucket
        try:
            r2 = self.fetch(play_url, headers={"User-Agent": self.UA, "Referer": watch_ref},
                            allow_redirects=False, timeout=10)
        except Exception:
            return ""
        loc = ""
        try:
            loc = r2.headers.get("Location") or r2.headers.get("location") or ""
        except Exception:
            loc = ""
        if not loc:
            return ""
        # player 页提取 m3u8：ibucket 用 playlistUrl；upload18 用 PLAYER_CONFIG.m3u8
        try:
            r3 = self.fetch(loc, headers={"User-Agent": self.UA, "Referer": self.HOST + "/"}, timeout=10)
            ib = getattr(r3, "text", "") or ""
        except Exception:
            return ""
        m = re.search(r'(?:playlistUrl|"m3u8")\s*:\s*"((?:https?:)?[^"]+)"', ib)
        if m:
            return self._clean_url(m.group(1))
        m = re.search(r'https?:[\\/]*[^\s"\'<>]+\.m3u8[^\s"\'<>]*', ib)
        return self._clean_url(m.group(0)) if m else ""

    @staticmethod
    def _clean_url(u):
        if not u:
            return ""
        u = u.replace("\\\\", "\\").replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u
        return u

    # ================= 本地代理（不需要）=================
    def localProxy(self, param):
        return [404, "text/plain", {}]
