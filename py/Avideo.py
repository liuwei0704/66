# coding: utf-8
# 站点：Avideo 导航站  https://avideo1.xyz/
# 类型：成人导航跳转页 -> 真实内容站为标准 MacCMS（mid=3，avideo 主题，伪静态美化 URL）
# 域名机制（已逆向 avideo1.xyz 跳转 JS）：
#   真实落地域 = https://{noncestr(2,2)}.{getName()}.xyz/{getCate()}/
#   - getName() 取自 nameList=["avideo34","avideo35","avideo36"] 随机
#   - 子域前缀为 getBiweeklyArr() 的 2 段 4 字符串拼接（每 15 天换一池）
#   - 实测 *.avideoNN.xyz 为泛解析（任意子域前缀均 200），故固定用 www 前缀即可
#   本源启动时解析 avideo1.xyz 取当前 nameList（未来名字轮换自适应），探测可达域并缓存；
#   解析失败回退硬编码 ["avideo34","avideo35","avideo36"]。
# 路由：分类 /vodtype/{tid}.html、/vodtype/{tid}-{pg}.html
#       详情 /voddetail/{id}.html   播放 /vodplay/{id}-1-1.html
#       搜索 /vodsearch/{wd}----------{pg}---.html
# 列表卡片：<a class="thumb__img" title=".." href="/voddetail/{id}.html"><img data-src="PIC">
#          （首页 grid 为广告卡 class="card"+外链，不含 thumb__img，天然规避）
# 播放：播放页 player_aaaa={..."encrypt":1,"url":"%68%74%74%70..."}；encrypt=1 即 URL 编码，
#       unquote 后得 m3u8 明码直链；m3u8/ts 仅需 UA（实测 200/206），parse:0 直出。
# 分类页无任何筛选项（无 /vodshow、无 screen），filters 全部为空。
# 最后验证：2026-10-11（m3u8 分片 206 可达）
import re
import sys
import html as _htmlmod
from urllib.parse import quote, unquote, urljoin

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    try:
        from spider import Spider as BaseSpider
    except Exception:
        class BaseSpider(object):
            def init(self, extend=""):
                pass

            def log(self, *a):
                pass


class Spider(BaseSpider):

    # ====== 站点信息（换站只改这里）======
    SITE_NAME = "Avideo"
    SEED = "https://avideo1.xyz/"
    PREFIX = "www"                                   # 泛解析，任意子域前缀均可
    NAMES = ["avideo34", "avideo35", "avideo36"]     # 回退用主名列表

    UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/120.0.0.0 Mobile Safari/537.36")

    def __init__(self):
        self._host = ""
        self.headers = {
            "User-Agent": self.UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        # 静态分类（零网络，实采自导航站菜单）
        self.classes = [
            {"type_id": "55", "type_name": "国产精品"},
            {"type_id": "63", "type_name": "华语精品"},
            {"type_id": "58", "type_name": "黑料吃瓜"},
            {"type_id": "60", "type_name": "欧美大屌"},
            {"type_id": "57", "type_name": "动漫禁漫"},
            {"type_id": "65", "type_name": "学生合集"},
            {"type_id": "64", "type_name": "乱伦精品"},
            {"type_id": "61", "type_name": "探花约炮"},
            {"type_id": "80", "type_name": "日本有码"},
            {"type_id": "81", "type_name": "主播网红"},
            {"type_id": "12", "type_name": "国产自拍"},
            {"type_id": "20", "type_name": "主播诱惑"},
            {"type_id": "22", "type_name": "偷拍偷窥"},
            {"type_id": "23", "type_name": "网曝吃瓜"},
            {"type_id": "24", "type_name": "抖阴短片"},
            {"type_id": "69", "type_name": "传媒剧情"},
            {"type_id": "70", "type_name": "日韩主播"},
            {"type_id": "71", "type_name": "日韩无码"},
            {"type_id": "72", "type_name": "中文字幕"},
            {"type_id": "25", "type_name": "AV解说"},
            {"type_id": "26", "type_name": "换脸明星"},
            {"type_id": "88", "type_name": "强奸乱伦"},
            {"type_id": "56", "type_name": "女优明星"},
            {"type_id": "73", "type_name": "欧美激情"},
            {"type_id": "74", "type_name": "重口激情"},
            {"type_id": "75", "type_name": "三级伦理"},
            {"type_id": "76", "type_name": "剧情动漫"},
            {"type_id": "77", "type_name": "SM调教"},
            {"type_id": "78", "type_name": "女同性恋"},
            {"type_id": "84", "type_name": "VR视角"},
            {"type_id": "86", "type_name": "日本无码"},
        ]
        # 分类页无筛选项
        self.filters = {}

    # ====== 基础接口 ======
    def getName(self):
        return self.SITE_NAME

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络，域名解析延迟到首个数据接口
        return

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return (".m3u8" in u) or u.endswith(".mp4")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ====== 域名解析（动态落地域 + 泛解析 + 回退）======
    def _try(self, url):
        try:
            r = self.fetch(url, headers=self.headers)
            if r and getattr(r, "status_code", 0) == 200:
                return getattr(r, "text", "") or ""
        except Exception as e:
            self.log("try fail %s: %s" % (url, e))
        return ""

    def _candidates(self):
        # 优先回退用主名（命中则省去导航站请求，冷启动最快）
        return ["https://%s.%s.xyz" % (self.PREFIX, n) for n in self.NAMES]

    def _seed_candidates(self):
        # 名字轮换自适应：仅当硬编码主名全失效时才请求导航站
        names = []
        try:
            r = self.fetch(self.SEED, headers=self.headers)
            txt = getattr(r, "text", "") or "" if r else ""
            m = re.search(r'nameList\s*=\s*\[([^\]]+)\]', txt)
            if m:
                names = re.findall(r'"([^"]+)"', m.group(1))
        except Exception as e:
            self.log("seed fail: %s" % e)
        return ["https://%s.%s.xyz" % (self.PREFIX, n)
                for n in names if n not in self.NAMES]

    def host(self):
        if self._host:
            return self._host
        # 1) 先探测硬编码主名（泛解析，命中即锁定，常见路径一次请求）
        for base in self._candidates():
            html = self._try(base + "/vodtype/55.html")
            if html and "/voddetail/" in html:
                self._host = base
                return base
        # 2) 主名全失效：从导航站取最新 nameList 再探测
        for base in self._seed_candidates():
            html = self._try(base + "/vodtype/55.html")
            if html and "/voddetail/" in html:
                self._host = base
                return base
        # 3) 兜底：取第一个主名
        self._host = "https://%s.%s.xyz" % (self.PREFIX, self.NAMES[0])
        return self._host

    # ====== 工具方法 ======
    def _html(self, url):
        try:
            r = self.fetch(url, headers=self.headers)
            if not r or getattr(r, "status_code", 0) != 200:
                return ""
            return getattr(r, "text", "") or ""
        except Exception as e:
            self.log("fetch fail %s: %s" % (url, e))
            return ""

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        return urljoin(self.host() + "/", u if u.startswith("/") else "/" + u)

    @staticmethod
    def _first(pattern, text, default=""):
        m = re.search(pattern, text or "", re.S)
        return m.group(1).strip() if m else default

    @staticmethod
    def _clean(s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        try:
            s = _htmlmod.unescape(s)
        except Exception:
            s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
                 .replace("&quot;", '"').replace("&#039;", "'"))
        return re.sub(r"\s+", " ", s).strip()

    # 列表卡片：thumb__img 锚内 title 在前、href 在后，img.data-src 为封面
    _CARD_RE = re.compile(
        r'<a[^>]*class="thumb__img"[^>]*title="([^"]*)"[^>]*'
        r'href="/voddetail/(\d+)\.html"[^>]*>\s*<img[^>]*data-src="([^"]*)"',
        re.S)

    def _parse_cards(self, html, scope_start=None, scope_end=None):
        region = html or ""
        if scope_start:
            i = region.find(scope_start)
            if i >= 0:
                region = region[i:]
        if scope_end:
            j = region.find(scope_end)
            if j > 0:
                region = region[:j]
        vods, seen = [], set()
        for title, vid, pic in self._CARD_RE.findall(region):
            if vid in seen:
                continue
            seen.add(vid)
            name = self._clean(title)
            if not name:
                continue
            vods.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._abs(pic.strip()),
                "vod_remarks": "",
            })
        return vods

    # ====== 首页 ======
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页取第一个分类列表作推荐
        html = self._html("%s/vodtype/55.html" % self.host())
        return {"list": self._parse_cards(html)}

    def getHomeVideoContent(self):
        return self.homeVideoContent()

    # ====== 分类 ======
    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or "").strip()
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        if page > 1:
            url = "%s/vodtype/%s-%d.html" % (self.host(), tid, page)
        else:
            url = "%s/vodtype/%s.html" % (self.host(), tid)
        html = self._html(url)
        vods = self._parse_cards(html, scope_start='thumbs', scope_end='fenye')
        if not vods:
            vods = self._parse_cards(html)

        # pagecount：无总页数展示，依据分页数字 + 是否存在"下页"推进
        nums = [int(x) for x in re.findall(r'/vodtype/%s-(\d+)\.html' % re.escape(tid), html)]
        pagecount = max(nums) if nums else page
        if ('xiayiye' in html) or ('下页' in html) or ('下一页' in html):
            pagecount = max(pagecount, page + 1)
        if pagecount < page:
            pagecount = page
        limit = len(vods) or 48
        return {
            "list": vods,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
        }

    def getCategoryContent(self, tid, pg, filter, extend):
        return self.categoryContent(tid, pg, filter, extend)

    # ====== 详情 ======
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

    def _skeleton(self, vid, title="", pic="", remark="解析中"):
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or self.SITE_NAME,
            "vod_pic": pic or "",
            "vod_remarks": remark,
            "vod_content": "",
            "vod_play_from": "高清线路",
            "vod_play_url": "正片$/vodplay/%s-1-1.html" % str(vid),
        }]}

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        m = re.search(r'(\d+)', vid)
        num = m.group(1) if m else vid
        url = "%s/voddetail/%s.html" % (self.host(), num)
        html = self._html(url)
        if not html:
            return self._skeleton(num)

        # 视频标题：紧邻 <div class="video__details"> 之前的 H1
        name = self._clean(
            self._first(r'<h1[^>]*>([^<]+)</h1>\s*<div class="video__details"', html))
        if not name:
            # 退回页面 title（去掉后缀描述）
            t = self._first(r'<title>([^<]+)</title>', html)
            name = self._clean(t.split("详情介绍", 1)[0]) if t else ""
        pic = self._first(r'class="video-img[^"]*"[^>]*data-src="([^"]*)"', html)
        if not pic:
            pic = self._first(r'id="video__player"[\s\S]{0,400}?data-src="([^"]*)"', html)
        vtype = self._clean(
            self._first(r'Categories:</span>\s*<a[^>]*>([^<]+)</a>', html))

        froms, urls = self._parse_play(html, num)
        if not froms:
            return self._skeleton(num, name, self._abs(pic), "暂无播放源")

        vod = {
            "vod_id": num,
            "vod_name": name or self.SITE_NAME,
            "vod_pic": self._abs(pic),
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": vtype,
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    def getDetailContent(self, ids):
        return self.detailContent(ids)

    def _parse_play(self, html, num):
        """播放源：优先抓 /vodplay/{id}-{sid}-{nid}.html 列表；
        无显式剧集名则用序号命名。单集站多为单条。"""
        plays = re.findall(r'href="(/vodplay/%s-\d+-\d+\.html)"' % re.escape(num), html)
        if not plays:
            plays = re.findall(r'href="(/vodplay/\d+-\d+-\d+\.html)"', html)
        # 去重保序
        uniq = []
        seen = set()
        for p in plays:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        if not uniq:
            return [], []
        parts = []
        for i, p in enumerate(uniq, 1):
            ep = "正片" if len(uniq) == 1 else ("第%02d集" % i)
            parts.append("%s$%s" % (ep, p))
        return ["高清线路"], ["#".join(parts)]

    # ====== 搜索 ======
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        kw = quote(str(key))
        # MacCMS 破折号伪静态：{wd}----------{page}---.html
        url = "%s/vodsearch/%s----------%d---.html" % (self.host(), kw, page)
        html = self._html(url)
        vods = self._parse_cards(html, scope_start='thumbs')
        if not vods:
            vods = self._parse_cards(html)
        return {"list": vods, "page": page}

    def getSearchContent(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ====== 播放 ======
    def playerContent(self, flag, id, vipFlags):
        play_path = id or ""
        if play_path and "$" in play_path:
            play_path = play_path.split("$", 1)[1]
        play_url = self._abs(play_path)
        real = ""
        try:
            html = self._html(play_url)
            raw = self._first(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html)
            if not raw:
                raw = self._first(r'player_aaaa\s*=\s*(\{.*?\})', html)
            if raw:
                u = self._first(r'"url"\s*:\s*"([^"]*)"', raw)
                u = u.replace("\\/", "/")
                encrypt = self._first(r'"encrypt"\s*:\s*(\d+)', raw)
                if u:
                    # encrypt=1 为 URL 编码，unquote 还原；encrypt=2 为 base64
                    if encrypt == "1" or "%" in u:
                        try:
                            u = unquote(u)
                        except Exception:
                            pass
                    elif encrypt == "2":
                        try:
                            import base64
                            u = base64.b64decode(u).decode("utf-8", "ignore")
                        except Exception:
                            pass
                    real = u
            if not real:
                real = self._first(r'(https?:\\?/\\?/[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html).replace("\\/", "/")
            if not real:
                real = self._first(r'(https?:\\?/\\?/[^\s"\'<>]+?\.mp4[^\s"\'<>]*)', html).replace("\\/", "/")
        except Exception as e:
            self.log("player parse fail: %s" % e)

        # 媒体请求头：UA-only + Accept */*（实测 m3u8/ts 200/206 可达）
        hdr = {"User-Agent": self.UA, "Accept": "*/*"}
        if real:
            if not real.startswith("http"):
                real = self._abs(real)
            return {"parse": 0, "url": real, "header": hdr}
        # 降级：交盒子嗅探
        return {"parse": 1, "url": play_url, "header": hdr}

    def getPlayerContent(self, flag, id, vipFlags):
        return self.playerContent(flag, id, vipFlags)

    # ====== 相关推荐 ======
    def recommendContent(self, ids, pg="1"):
        try:
            vid = self._norm_ids(ids)
            m = re.search(r'(\d+)', vid)
            num = m.group(1) if m else vid
            if not num:
                return {"list": []}
            html = self._html("%s/voddetail/%s.html" % (self.host(), num))
            # "相关内容" 区块复用卡片解析器
            cards = self._parse_cards(html, scope_start='相关内容')
            if not cards:
                cards = self._parse_cards(html, scope_start='相关')
            out = [v for v in cards if v.get("vod_id") != num][:18]
            return {"list": out}
        except Exception as e:
            self.log("recommend fail: %s" % e)
            return {"list": []}

    def getRecommendContent(self, ids, pg="1"):
        return self.recommendContent(ids, pg)

    def localProxy(self, param):
        return [200, "text/plain", b""]
