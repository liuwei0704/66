# coding: utf-8
"""
AITIME (AI TIME) - TVBox/FongMi Python Spider
站点: https://221004.aitime.cc
类型: MacCMS 标准 HTML 影视站（成人向 / AI换脸短剧）
主域名: https://221004.aitime.cc
备用/发布: https://aitime.avflcc.top/fulidh
内容类型: AI成人短剧 / AI成人漫剧 / AI换脸 / AI魔改
最后验证: 2026-10-04
来源: 用户提供

【结构】
  分类:   /vodtype/{tid}/            分页 /vodtype/{tid}-{pg}/
  详情:   /vodplay/{vid}-{sid}-{eid}/   （详情+播放在同一页）
  播放器: player_data.url = "{vid}|{eid}", from=huangguo
          -> /huangguo.php?ac=play&id={vid}&ep={eid}  返回 {"code":1,"url":"m3u8"}
  搜索:   /vodsearch/{kw}----------{pg}---/
  播放器: huangguo 源为 ps=0 直连，m3u8 带 auth_key（实时签名）

【m3u8 取证结论】
  非图片流；分片全 .ts；suspicious_ad_dirs 为空；同目录 KEY
  => 直接返回原始直链，不套 localProxy（法则30）
"""
import re
import json
import time
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def __init__(self):
        # 零网络：class/filters 本地写死
        self.host = "https://221004.aitime.cc"
        self.classes = [
            {"type_id": "1", "type_name": "AI成人短剧"},
            {"type_id": "2", "type_name": "AI成人漫剧"},
            {"type_id": "3", "type_name": "AI换脸"},
            {"type_id": "4", "type_name": "AI魔改"},
        ]
        self.filters = {
            "1": [{"key": "by", "name": "排序", "value": [
                {"n": "默认", "v": ""}, {"n": "最新", "v": "time"},
                {"n": "最热", "v": "hits"}]}],
            "2": [{"key": "by", "name": "排序", "value": [
                {"n": "默认", "v": ""}, {"n": "最新", "v": "time"}]}],
            "3": [], "4": [],
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        }
        self.extend = ""

    # ---------------- 基础 ----------------
    def getName(self):
        return "AI TIME"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
        self.extend = extend or ""

    def isVideoFormat(self, url):
        return bool(url) and any(x in url for x in (".m3u8", ".mp4", ".flv"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _fetch(self, url, headers=None, timeout=15):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            r = self.fetch(url, headers=h, timeout=timeout)
        except Exception:
            return ""
        if not r or getattr(r, "status_code", 0) != 200:
            return ""
        return getattr(r, "text", "") or ""

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        # 零网络
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._fetch(self.host + "/home/")
        return {"list": self._parse_cards(html)}
    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                pass
            out = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    out[k.strip()] = v.strip()
            return out
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        # 分页模板: /vodtype/{tid}/ (第1页)  /vodtype/{tid}-{pg}/ (第N页)
        if page in ("1", ""):
            url = "%s/vodtype/%s/" % (self.host, tid)
        else:
            url = "%s/vodtype/%s-%s/" % (self.host, tid, page)
        html = self._fetch(url)
        items = self._parse_cards(html)
        # 尝试解析总页数，兜底 pagecount=25（实测该站分类25页）
        pagecount = self._parse_pagecount(html) or 25
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": len(items) or 20,
            "total": pagecount * 36,
        }

    def _parse_pagecount(self, html):
        if not html:
            return 0
        nums = re.findall(r'/vodtype/\d+-(\d+)/', html)
        if nums:
            try:
                return max(int(n) for n in nums)
            except Exception:
                return 0
        return 0

    # ---------------- 列表卡片解析 ----------------
    def _parse_cards(self, html):
        if not html:
            return []
        out = []
        seen = set()
        # 宽松匹配：只锁定 href，内部块单独提取 title/img
        for m in re.finditer(
            r'<a[^>]+href="(/vodplay/\d+-\d+-\d+/?)"[^>]*>(.*?)</a>',
            html, re.S
        ):
            href, inner = m.group(1), m.group(2)
            vm = re.match(r'/vodplay/(\d+)-', href)
            if not vm:
                continue
            vid = vm.group(1)
            if vid in seen:
                continue
            # 标题：a 标签 title 属性 > 内部 h3/h2/文本
            title = ""
            tm = re.search(r'title="([^"]+)"', m.group(0)[:m.group(0).find('>') + 1])
            if tm:
                title = tm.group(1).strip()
            if not title:
                hm = re.search(r'<h[1-4][^>]*>(.*?)</h[1-4]>', inner, re.S)
                if hm:
                    title = re.sub(r'<[^>]+>', '', hm.group(1)).strip()
            if not title:
                t = re.sub(r'<[^>]+>', ' ', inner)
                t = re.sub(r'\s+', ' ', t).strip()
                t = re.sub(r'^\d{4}/\d{2}/\d{2}\s*', '', t)
                t = re.sub(r'\s*(更新至.*|已完结|全\d+集|\d+集)\s*$', '', t)
                title = t[:40]
            # 封面
            pic = ""
            im = re.search(r'<img[^>]+src="([^"]+)"', inner)
            if im:
                pic = im.group(1)
            if not title and not pic:
                continue
            # 备注
            remark = ""
            rm = re.search(r'(更新至[^<\s]*|已完结|全\d+集|\d+集)', inner)
            if rm:
                remark = rm.group(1)
            seen.add(vid)
            out.append({
                "vod_id": href,
                "vod_name": title or ("视频" + vid),
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out
    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks=""):
        return {"list": [{
            "vod_id": vid, "vod_name": title or "视频", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + str(vid),
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            play_page = raw if raw.startswith("http") else urljoin(self.host + "/", raw.lstrip("/"))
            html = self._fetch(play_page)
            name, pic, content, remarks = self._parse_detail(html)
            # 提取当前 vid 的所有剧集
            episodes = self._parse_episodes(html, raw)
            if episodes:
                play_url = "#".join("%s$%s" % (ep_name, ep_href) for ep_name, ep_href in episodes)
            else:
                # 兜底：只有当前这一集
                play_url = "播放$" + raw
            vod = {
                "vod_id": raw,
                "vod_name": name or "视频",
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_content": content,
                "vod_play_from": "播放",
                "vod_play_url": play_url,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"detail": "exception", "ids": raw, "err": str(e)})
            return self._skeleton(raw)

    def _parse_episodes(self, html, cur_href):
        """从详情页提取同一 vid 的所有剧集，返回 [(集名, 播放页路径), ...]"""
        if not html:
            return []
        m = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)', cur_href)
        if not m:
            return []
        vid, sid = m.group(1), m.group(2)
        out = []
        seen = set()
        for hm in re.finditer(r'href="(/vodplay/%s-%s-(\d+)/?)"' % (vid, sid), html):
            href = hm.group(1)
            ep = int(hm.group(2))
            if ep in seen:
                continue
            seen.add(ep)
            out.append((("第%d集" % ep), href))
        out.sort(key=lambda x: int(re.search(r'-(\d+)/?$', x[1]).group(1)))
        return out
    def _parse_detail(self, html):
        if not html:
            return "", "", "", ""
        # 标题：收集所有 h1，取清理后最长的有效文本（首页/详情页首个 h1 常是注释块）
        name = ""
        cands = []
        for m in re.finditer(r'<h1[^>]*>(.*?)</h1>', html, re.S):
            raw = re.sub(r'<!--.*?-->', '', m.group(1), flags=re.S)
            raw = re.sub(r'<[^>]+>', '', raw)
            raw = raw.replace('-', ' ').replace('>', ' ').replace('<', ' ')
            raw = re.sub(r'\s+', ' ', raw).strip()
            raw = re.sub(r'^[\s\-—>]+', '', raw).strip()
            if len(raw) >= 2 and 'AI TIME' not in raw:
                cands.append(raw)
        if cands:
            name = max(cands, key=len)
        if not name:
            t = re.search(r'<title>(.*?)</title>', html, re.S)
            if t:
                name = re.split(r'[-—]', t.group(1))[0].strip()
        # 封面
        pic = ""
        p = re.search(r'<img[^>]+src="(https?://[^"]+)"', html)
        if p:
            pic = p.group(1)
        # 简介
        content = ""
        c = re.search(r'(?:简介|剧情简介|内容简介)[：:]?\s*</[^>]+>\s*<[^>]*>(.*?)</', html, re.S)
        if not c:
            c = re.search(r'class="[^"]*(?:desc|content|intro)[^"]*"[^>]*>(.*?)</div>', html, re.S)
        if c:
            content = re.sub(r'<[^>]+>', '', c.group(1))
            content = re.sub(r'\s+', ' ', content).strip()[:500]
        # 备注/更新
        remarks = ""
        r = re.search(r'(更新至[^<\s]*|已完结|全\d+集)', html)
        if r:
            remarks = r.group(1)
        return name, pic, content, remarks
    def searchContent(self, key, quick, pg="1"):
        page = str(pg or "1")
        kw = quote(str(key or ""))
        url = "%s/vodsearch/%s----------%s---/" % (self.host, kw, page)
        html = self._fetch(url)
        return {"list": self._parse_cards(html), "page": int(page)}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_id = str(id or "")
        # 若带 "名称$地址" 形态，取地址
        if "$" in play_id:
            play_id = play_id.split("$", 1)[-1]
        # id 形如 /vodplay/{vid}-{sid}-{eid}/
        m = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)', play_id)
        if not m:
            # 兜底：若是直链直接返回
            if re.match(r'^https?://', play_id):
                return {"parse": 0, "url": play_id, "header": {"User-Agent": self.headers["User-Agent"]}}
            return {"parse": 1, "url": urljoin(self.host + "/", play_id.lstrip("/")), "header": self.headers}
        vid, sid, eid = m.group(1), m.group(2), m.group(3)
        play_page = urljoin(self.host + "/", play_id.lstrip("/"))

        # 播放页 player_data.url = "{rid}|{ep}"：rid 是资源库真实 id（≠ vodplay 的 vid）
        # 用 vid 调 API 会返回 1003，必须取 player_data 的 rid
        rid, r_ep = "", ""
        page_html = self._fetch(play_page)
        dm = re.search(r'player_data\s*=\s*(\{.*?\})\s*;?\s*</', page_html, re.S)
        if dm:
            try:
                pd = json.loads(dm.group(1))
                ru = str(pd.get("url") or "")
            except Exception:
                mm = re.search(r'"url"\s*:\s*"([^"]+)"', dm.group(1))
                ru = mm.group(1).replace("\\/", "/") if mm else ""
            if "|" in ru:
                rid, r_ep = ru.split("|", 1)
            elif ru:
                rid = ru
        if not rid:
            rid = vid
        if not r_ep:
            r_ep = eid

        # 请求取流接口：id=rid（资源id），ep=集数（=播放页 eid）
        api = "%s/huangguo.php?ac=play&id=%s&ep=%s&_=%d" % (
            self.host, rid, r_ep, int(time.time() * 1000))
        body = self._fetch(api, headers={
            "Referer": play_page,
            "X-Requested-With": "XMLHttpRequest",
        })
        real = ""
        if body:
            try:
                j = json.loads(body)
                if str(j.get("code")) == "1" and j.get("url"):
                    real = j["url"]
            except Exception:
                mm = re.search(r'"url"\s*:\s*"([^"]+)"', body)
                if mm:
                    real = mm.group(1).replace("\\/", "/")
        if real and re.match(r'^https?://', real):
            # m3u8 带 auth_key，实时签名；取证结论为无广告直链，直接返回
            return {
                "parse": 0,
                "url": real,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                },
            }
        # 兜底：交给嗅探
        return {
            "parse": 1,
            "url": urljoin(self.host + "/", play_id.lstrip("/")),
            "header": self.headers,
        }

    # ---------------- 推荐 ----------------
    def recommendContent(self, ids, pg):
        return {"list": []}

    def liveContent(self, url):
        return []

    def action(self, action):
        return {}

    def localProxy(self, param):
        return [404, "text/plain", b"not implemented"]
